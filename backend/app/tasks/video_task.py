"""视频处理后台任务"""

import logging
from dataclasses import dataclass

from app.config import get_settings
from app.models.entities import Resource, TaskResult
from app.models.enums import TaskStatus
from app.services.transcribe import TranscribeError, extract_audio_async
from app.services.video_downloader import DownloadError, download_video
from app.state import get_resource_urls, get_task, register_resource, resources
from app.utils.hash import compute_file_hash

logger = logging.getLogger(__name__)


@dataclass
class VideoTaskOptions:
    """视频任务选项"""

    generate_outline: bool = True
    generate_article: bool = True
    generate_podcast: bool = False
    outline_system_prompt: str = ""
    outline_user_prompt: str = ""
    article_system_prompt: str = ""
    article_user_prompt: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""


async def update_task_status(task: TaskResult, status: TaskStatus, progress: str) -> None:
    """更新任务状态并推送 SSE 事件"""
    task.status = status
    task.progress = progress
    if task.status_queue:
        video_url, audio_url = get_resource_urls(task.resource_id)
        await task.status_queue.put(
            {
                "status": status.value,
                "progress": progress,
                "title": task.title,
                "resource_id": task.resource_id,
                "video_url": video_url,
                "audio_url": audio_url,
                "transcript": task.transcript,
                "error": task.error,
            }
        )


async def process_video_task(
    task_id: str,
    url: str,
    options: VideoTaskOptions,
) -> None:
    """后台处理视频任务（下载和转录阶段）"""
    task = get_task(task_id)
    if not task:
        return

    # 保存生成选项和提示词到任务中
    task.generate_outline_flag = options.generate_outline
    task.generate_article_flag = options.generate_article
    task.generate_podcast_flag = options.generate_podcast
    task.outline_system_prompt = options.outline_system_prompt
    task.outline_user_prompt = options.outline_user_prompt
    task.article_system_prompt = options.article_system_prompt
    task.article_user_prompt = options.article_user_prompt
    task.podcast_system_prompt = options.podcast_system_prompt
    task.podcast_user_prompt = options.podcast_user_prompt

    # 判断是否需要转录（任一生成选项开启则需要转录）
    need_transcribe = (
        options.generate_outline or options.generate_article or options.generate_podcast
    )
    logger.info(
        "任务 %s 开始处理: %s (大纲: %s, 文章: %s, 播客: %s)",
        task_id,
        url,
        options.generate_outline,
        options.generate_article,
        options.generate_podcast,
    )

    settings = get_settings()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 下载视频
        await update_task_status(task, TaskStatus.DOWNLOADING, "正在下载视频...")

        video_result = await download_video(url, output_dir=output_dir)
        task.title = video_result.title

        # 2. 计算视频哈希并创建/复用资源
        resource_id = compute_file_hash(video_result.path)
        if resource_id in resources:
            # 复用已有资源
            resource = resources[resource_id]
            resource.ref_count += 1
            logger.info("任务 %s 复用资源 %s", task_id, resource_id)
        else:
            # 创建新资源
            resource = Resource(
                resource_id=resource_id,
                video_path=video_result.path,
                title=video_result.title,
            )
            register_resource(resource)
            logger.info("任务 %s 创建资源 %s", task_id, resource_id)

        task.resource_id = resource_id
        await update_task_status(
            task, TaskStatus.DOWNLOADING, f"下载完成: {video_result.title}"
        )

        # 3. 提取音频（始终执行，如果资源中没有音频）
        await update_task_status(task, TaskStatus.TRANSCRIBING, "正在提取音频...")
        if not resource.audio_path or not resource.audio_path.exists():
            audio_path = await extract_audio_async(video_result.path)
            resource.audio_path = audio_path
        else:
            audio_path = resource.audio_path
            logger.info("任务 %s 复用音频资源", task_id)

        # 仅下载模式：不需要转录，直接完成
        if not need_transcribe:
            await update_task_status(task, TaskStatus.COMPLETED, "下载完成")
            logger.info("任务 %s 下载完成: %s", task_id, task.title)
            return

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 4. 转录音频
        await update_task_status(task, TaskStatus.TRANSCRIBING, "正在转录音频...")
        from app.services.transcribe import transcribe_audio

        transcript = await transcribe_audio(audio_path)
        task.transcript = transcript

        # 5. 设置为等待流式生成状态
        await update_task_status(task, TaskStatus.READY, "转录完成，准备生成内容")
        logger.info("任务 %s 转录完成，等待流式生成", task_id)

    except DownloadError as e:
        task.error = f"下载失败: {e}"
        await update_task_status(task, TaskStatus.FAILED, task.error)
        logger.warning("任务 %s 下载失败: %s", task_id, e)
    except TranscribeError as e:
        task.error = f"转录失败: {e}"
        await update_task_status(task, TaskStatus.FAILED, task.error)
        logger.warning("任务 %s 转录失败: %s", task_id, e)
    except Exception as e:
        task.error = str(e)
        await update_task_status(task, TaskStatus.FAILED, f"处理失败: {e}")
        logger.exception("任务 %s 处理异常", task_id)
