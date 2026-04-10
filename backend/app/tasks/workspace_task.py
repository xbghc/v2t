"""工作区后台任务"""

import logging
import uuid

from app.config import get_settings
from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus
from app.services.transcribe import TranscribeError, extract_audio_async, transcribe_audio
from app.services.video_downloader import DownloadError, download_video
from app.state import get_workspace, save_workspace
from app.storage import get_file_storage, get_redis
from app.utils.response import build_workspace_response

logger = logging.getLogger(__name__)


async def update_workspace_status(
    workspace: Workspace, status: WorkspaceStatus, progress: str
) -> None:
    """更新工作区状态并通过 Redis Pub/Sub 推送 SSE 事件"""
    workspace.status = status
    workspace.progress = progress

    # 持久化到 Redis
    await save_workspace(workspace)

    # 通过 Redis Pub/Sub 发布状态
    redis = get_redis()
    response = await build_workspace_response(workspace)
    channel = f"workspace:{workspace.workspace_id}:status"
    await redis.publish(channel, response.model_dump_json())


async def process_workspace(workspace_id: str, url: str) -> None:
    """
    后台处理工作区任务（下载和转录）。

    资源文件组织结构：
        {url_hash}/
            video.mp4         # 视频
            audio.mp3         # 音频
            transcript.txt    # 转录文本
    """
    workspace = await get_workspace(workspace_id)
    if not workspace:
        return

    logger.info("工作区 %s 开始处理: %s", workspace_id, url)

    settings = get_settings()
    storage = get_file_storage()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 下载视频
        await update_workspace_status(
            workspace, WorkspaceStatus.DOWNLOADING, "正在下载视频..."
        )

        video_result = await download_video(url, output_dir=output_dir)
        workspace.title = video_result.title
        url_hash = video_result.url_hash
        resource_dir = output_dir / url_hash

        # 保存视频
        video_key = f"{url_hash}/video.mp4"
        await storage.save_file(video_key, video_result.path)

        video_resource = WorkspaceResource(
            resource_id=str(uuid.uuid4())[:8],
            name="video",
            resource_type=ResourceType.VIDEO,
            storage_key=video_key,
        )
        workspace.add_resource(video_resource)

        await update_workspace_status(
            workspace, WorkspaceStatus.DOWNLOADING, f"下载完成: {video_result.title}"
        )

        # 2. 提取音频
        await update_workspace_status(
            workspace, WorkspaceStatus.TRANSCRIBING, "正在提取音频..."
        )
        audio_path = resource_dir / "audio.mp3"
        audio_path = await extract_audio_async(video_result.path, audio_path=audio_path)

        # 保存音频
        audio_key = f"{url_hash}/audio.mp3"
        await storage.save_file(audio_key, audio_path)

        audio_resource = WorkspaceResource(
            resource_id=str(uuid.uuid4())[:8],
            name="audio",
            resource_type=ResourceType.AUDIO,
            storage_key=audio_key,
        )
        workspace.add_resource(audio_resource)

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 3. 转录音频
        await update_workspace_status(
            workspace, WorkspaceStatus.TRANSCRIBING, "正在转录音频..."
        )
        transcript = await transcribe_audio(audio_path)

        # 保存转录文本
        transcript_key = f"{url_hash}/transcript.txt"
        await storage.save_bytes(transcript_key, transcript.encode("utf-8"))

        transcript_resource = WorkspaceResource(
            resource_id=str(uuid.uuid4())[:8],
            name="transcript",
            resource_type=ResourceType.TEXT,
            storage_key=transcript_key,
        )
        workspace.add_resource(transcript_resource)

        # 4. 完成
        await update_workspace_status(
            workspace, WorkspaceStatus.READY, "转录完成，准备生成内容"
        )
        logger.info("工作区 %s 转录完成", workspace_id)

    except DownloadError as e:
        workspace.error = f"下载失败: {e}"
        await update_workspace_status(workspace, WorkspaceStatus.FAILED, workspace.error)
        logger.warning("工作区 %s 下载失败: %s", workspace_id, e)
    except TranscribeError as e:
        workspace.error = f"转录失败: {e}"
        await update_workspace_status(workspace, WorkspaceStatus.FAILED, workspace.error)
        logger.warning("工作区 %s 转录失败: %s", workspace_id, e)
    except Exception as e:
        workspace.error = str(e)
        await update_workspace_status(
            workspace, WorkspaceStatus.FAILED, f"处理失败: {e}"
        )
        logger.exception("工作区 %s 处理异常", workspace_id)
