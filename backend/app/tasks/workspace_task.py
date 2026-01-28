"""工作区后台任务"""

import json
import logging
import uuid

from app.config import get_settings
from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus
from app.services.transcribe import TranscribeError, extract_audio_async, transcribe_audio
from app.services.video_downloader import DownloadError, download_video
from app.state import get_workspace, save_workspace

logger = logging.getLogger(__name__)


async def update_workspace_status(
    workspace: Workspace, status: WorkspaceStatus, progress: str
) -> None:
    """更新工作区状态并推送 SSE 事件"""
    workspace.status = status
    workspace.progress = progress

    # 持久化到存储
    await save_workspace(workspace)

    if workspace.status_queue:
        # 构建资源响应
        resources = []
        for res in workspace.resources:
            res_data = {
                "resource_id": res.resource_id,
                "name": res.name,
                "resource_type": res.resource_type.value,
                "download_url": f"/api/workspaces/{workspace.workspace_id}/resources/{res.resource_id}"
                if res.resource_type in (ResourceType.VIDEO, ResourceType.AUDIO)
                else None,
                "content": None,
                "created_at": res.created_at,
            }
            # TEXT 类型读取内容
            if res.resource_type == ResourceType.TEXT and res.resource_path and res.resource_path.exists():
                try:
                    data = json.loads(res.resource_path.read_text(encoding="utf-8"))
                    res_data["content"] = data.get("content", "")
                except (json.JSONDecodeError, OSError):
                    pass
            resources.append(res_data)

        await workspace.status_queue.put(
            {
                "workspace_id": workspace.workspace_id,
                "url": workspace.url,
                "title": workspace.title,
                "status": status.value,
                "progress": progress,
                "error": workspace.error,
                "resources": resources,
                "created_at": workspace.created_at,
                "last_accessed_at": workspace.last_accessed_at,
            }
        )


async def process_workspace(workspace_id: str, url: str) -> None:
    """
    后台处理工作区任务（下载和转录）。

    资源文件组织结构：
        {temp_dir}/{url_hash}/
            meta.json         # 元数据
            video.mp4         # 视频
            audio.mp3         # 音频
            transcript.json   # 转录文本

    支持文件复用：如果资源文件已存在，跳过对应处理步骤。
    """
    workspace = await get_workspace(workspace_id)
    if not workspace:
        return

    logger.info("工作区 %s 开始处理: %s", workspace_id, url)

    settings = get_settings()
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

        # 添加视频资源
        video_resource = WorkspaceResource(
            resource_id=str(uuid.uuid4())[:8],
            name="video",
            resource_type=ResourceType.VIDEO,
            resource_path=video_result.path,
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

        # 添加音频资源
        audio_resource = WorkspaceResource(
            resource_id=str(uuid.uuid4())[:8],
            name="audio",
            resource_type=ResourceType.AUDIO,
            resource_path=audio_path,
        )
        workspace.add_resource(audio_resource)

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 3. 转录音频
        transcript_path = resource_dir / "transcript.json"

        # 检查转录是否已存在（复用）
        if transcript_path.exists():
            try:
                data = json.loads(transcript_path.read_text(encoding="utf-8"))
                transcript = data.get("content", "")
                logger.info("复用已有转录: %s", url_hash)
            except (json.JSONDecodeError, OSError):
                transcript = None
        else:
            transcript = None

        if not transcript:
            await update_workspace_status(
                workspace, WorkspaceStatus.TRANSCRIBING, "正在转录音频..."
            )
            transcript = await transcribe_audio(audio_path)

            # 保存转录结果
            transcript_path.write_text(
                json.dumps({"prompt": "", "content": transcript}, ensure_ascii=False),
                encoding="utf-8",
            )

        # 添加转录资源（TEXT 类型）
        transcript_resource = WorkspaceResource(
            resource_id=str(uuid.uuid4())[:8],
            name="transcript",
            resource_type=ResourceType.TEXT,
            resource_path=transcript_path,
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
