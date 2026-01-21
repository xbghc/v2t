"""文本转播客后台任务"""

import logging

from app.config import get_settings
from app.models.entities import PodcastTask
from app.models.enums import TaskStatus
from app.services.llm import LLMError, generate_podcast_script
from app.services.podcast_tts import PodcastTTSError, generate_podcast_audio
from app.state import get_task

logger = logging.getLogger(__name__)


async def process_text_to_podcast_task(
    task_id: str,
    text: str,
    title: str = "",
    podcast_system_prompt: str = "",
    podcast_user_prompt: str = "",
) -> None:
    """后台处理文本转播客任务"""
    task = get_task(task_id)
    if not task or not isinstance(task, PodcastTask):
        return

    logger.info("任务 %s 开始处理文本转播客", task_id)

    settings = get_settings()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    # 设置标题
    task.title = title or "文本转播客"
    task.transcript = text

    try:
        # 1. 生成播客脚本
        task.status = TaskStatus.READY
        task.progress = "正在生成播客脚本..."

        podcast_script = await generate_podcast_script(
            text,
            system_prompt=podcast_system_prompt or None,
            user_prompt=podcast_user_prompt or None,
        )
        if not podcast_script or len(podcast_script.strip()) < 50:
            raise LLMError("生成的播客脚本内容过短")

        task.podcast_script = podcast_script

        # 2. 合成播客音频
        task.progress = "正在合成播客音频..."

        podcast_audio_path = output_dir / f"{task_id}_podcast.mp3"
        await generate_podcast_audio(
            podcast_script,
            podcast_audio_path,
            temp_dir=output_dir,
        )
        task.podcast_audio_path = podcast_audio_path

        # 完成
        task.status = TaskStatus.COMPLETED
        task.progress = "处理完成"
        logger.info("任务 %s 文本转播客完成: %s", task_id, task.title)

    except LLMError as e:
        task.status = TaskStatus.FAILED
        task.error = f"播客脚本生成失败: {e}"
        task.progress = task.error
        logger.warning("任务 %s 播客脚本生成失败: %s", task_id, e)
    except PodcastTTSError as e:
        task.status = TaskStatus.FAILED
        task.error = f"播客音频合成失败: {e}"
        task.progress = task.error
        logger.warning("任务 %s 播客音频合成失败: %s", task_id, e)
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.progress = f"处理失败: {e}"
        logger.exception("任务 %s 处理异常", task_id)
