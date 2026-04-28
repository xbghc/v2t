"""工作区后台任务（流式：下载 → VAD 切片 → 并发转录 → 边走边推 SSE）

SSE 消息体使用 envelope 格式：
    {"type": "workspace", "data": <WorkspaceResponse>}        全量状态/资源变更
    {"type": "transcript.append", "data": <segment>}           单段转录增量
"""

import asyncio
import json
import logging
import uuid

from app.config import get_settings
from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus
from app.services.downloader import DownloadError, download_video
from app.services.streaming_pipeline import (
    SegmentationState,
    StreamingPipelineError,
    stream_audio_chunks,
)
from app.services.stt import TranscribeError, TranscriptSegment, transcribe_stream
from app.services.transcribe import _get_duration, format_timestamp
from app.storage import get_file_storage, get_redis, get_workspace, save_workspace
from app.utils.response import build_workspace_response

logger = logging.getLogger(__name__)


def _channel(workspace_id: str) -> str:
    return f"workspace:{workspace_id}:status"


async def _publish_workspace(workspace: Workspace) -> None:
    """推送整体状态/资源变化（type=workspace envelope）"""
    redis = get_redis()
    response = await build_workspace_response(workspace)
    payload = {"type": "workspace", "data": response.model_dump(mode="json")}
    await redis.publish(_channel(workspace.workspace_id), json.dumps(payload))


async def _publish_transcript_segment(
    workspace_id: str, segment: TranscriptSegment
) -> None:
    """推送单段转录（type=transcript.append envelope）"""
    redis = get_redis()
    payload = {
        "type": "transcript.append",
        "data": {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "chunk_index": segment.chunk_index,
        },
    }
    await redis.publish(_channel(workspace_id), json.dumps(payload))


async def update_workspace_status(
    workspace: Workspace, status: WorkspaceStatus, progress: str
) -> None:
    """更新工作区状态/进度并推送"""
    workspace.status = status
    workspace.progress = progress
    await save_workspace(workspace)
    await _publish_workspace(workspace)
    logger.info(
        "工作区 %s → %s (%s)",
        workspace.workspace_id, status.value, progress,
    )


class _VideoTooLongError(Exception):
    """视频时长超过限制（用户输入问题，重试无意义）"""

    def __init__(self, video_minutes: int, max_minutes: int) -> None:
        self.video_minutes = video_minutes
        self.max_minutes = max_minutes
        super().__init__(
            f"video {video_minutes}min > limit {max_minutes}min"
        )


async def _mark_failed(
    workspace: Workspace, kind: str, user_message: str,
) -> None:
    """统一失败收尾：error 写友好消息（前端直接展示），error_kind 给前端分类用

    技术细节由调用方自己 logger 记。
    """
    workspace.status = WorkspaceStatus.FAILED
    workspace.error = user_message
    workspace.error_kind = kind
    workspace.progress = user_message
    await save_workspace(workspace)
    await _publish_workspace(workspace)


async def _emit_resource(
    workspace: Workspace,
    name: str,
    resource_type: ResourceType,
    storage_key: str,
) -> WorkspaceResource:
    """添加 ready=True 资源并触发推送"""
    resource = WorkspaceResource(
        resource_id=str(uuid.uuid4())[:8],
        name=name,
        resource_type=resource_type,
        storage_key=storage_key,
        ready=True,
    )
    workspace.add_resource(resource)
    await save_workspace(workspace)
    await _publish_workspace(workspace)
    return resource


async def process_workspace(workspace_id: str, url: str) -> None:
    """流式视频处理（下载 → 抽音频 → VAD 切片 → 并发转录 → 落盘）"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        return

    logger.info("工作区 %s 开始处理: %s", workspace_id, url)

    settings = get_settings()
    storage = get_file_storage()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ===== Stage 1: 下载 =====
        await update_workspace_status(
            workspace, WorkspaceStatus.PROCESSING, "正在下载视频..."
        )

        # 节流：相同百分比不重复推。Provider 拿到字节进度时回调，频率不限。
        last_pct = -1

        async def on_download_progress(downloaded: int, total: int) -> None:
            nonlocal last_pct
            if total <= 0:
                return
            pct = int(downloaded * 100 / total)
            if pct == last_pct:
                return
            last_pct = pct
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            await update_workspace_status(
                workspace,
                WorkspaceStatus.PROCESSING,
                f"正在下载 {pct}% ({mb_done:.1f}MB/{mb_total:.1f}MB)",
            )

        video = await download_video(
            url, output_dir=output_dir, progress_callback=on_download_progress
        )
        workspace.title = video.title
        url_hash = video.url_hash

        duration = await asyncio.to_thread(_get_duration, video.path)
        if duration and duration > settings.max_video_duration:
            raise _VideoTooLongError(
                video_minutes=int(duration // 60),
                max_minutes=settings.max_video_duration // 60,
            )

        video_key = f"{url_hash}/video.mp4"
        await storage.save_file(video_key, video.path)
        await _emit_resource(workspace, "video", ResourceType.VIDEO, video_key)

        # ===== Stage 2: 流式转录（VAD + 切片 + STT 并行） =====
        # 抽取音频是转录链路的内部细节（stream_audio_chunks 内部按需 ffmpeg 抽 audio.mp3），
        # 不再单独推状态 / emit audio 资源。
        await update_workspace_status(
            workspace, WorkspaceStatus.PROCESSING,
            "正在转录...",
        )

        seg_state = SegmentationState()
        chunks_iter = stream_audio_chunks(video, seg_state)

        transcript_lines: list[str] = []
        last_pushed_chunk = -1

        audio_duration_hint = int(duration) if duration else None
        async for seg in transcribe_stream(
            chunks_iter, language=None, audio_duration=audio_duration_hint
        ):
            transcript_lines.append(f"[{format_timestamp(seg.start)}] {seg.text}")
            await _publish_transcript_segment(workspace_id, seg)

            if seg.chunk_index > last_pushed_chunk:
                last_pushed_chunk = seg.chunk_index
                total = seg_state.audio_duration or duration or 0
                completed = seg.end
                pct = int(completed / total * 100) if total else 0
                await update_workspace_status(
                    workspace, WorkspaceStatus.PROCESSING,
                    f"正在转录 {pct}% ({int(completed)}s/{int(total)}s)",
                )

        # ===== Stage 5: 落盘 transcript =====
        transcript_text = "\n".join(transcript_lines)
        transcript_key = f"{url_hash}/transcript.txt"
        await storage.save_bytes(transcript_key, transcript_text.encode("utf-8"))
        await _emit_resource(
            workspace, "transcript", ResourceType.TEXT, transcript_key,
        )

        await update_workspace_status(
            workspace, WorkspaceStatus.READY, "转录完成，准备生成内容",
        )
        logger.info("工作区 %s 转录完成", workspace_id)

    except _VideoTooLongError as e:
        await _mark_failed(
            workspace,
            "video_too_long",
            f"视频时长 {e.video_minutes} 分钟，超过最大限制 {e.max_minutes} 分钟。"
            "请使用更短的视频。",
        )
        logger.warning(
            "工作区 %s 视频时长超限: %dmin > %dmin",
            workspace_id, e.video_minutes, e.max_minutes,
        )
    except DownloadError as e:
        await _mark_failed(
            workspace,
            "download_failed",
            "视频下载失败：链接可能已失效，或上游解析服务暂时不可用。"
            "请确认链接可正常访问，或稍后重试。",
        )
        logger.warning("工作区 %s 下载失败: %s", workspace_id, e)
    except (TranscribeError, StreamingPipelineError) as e:
        await _mark_failed(
            workspace,
            "transcribe_failed",
            "音频转录失败：语音识别服务暂时不可用。请稍后重试。",
        )
        logger.warning("工作区 %s 转录失败: %s", workspace_id, e)
    except Exception:
        await _mark_failed(
            workspace,
            "unknown",
            "处理过程中出现未知错误，请稍后重试。",
        )
        logger.exception("工作区 %s 处理异常", workspace_id)
