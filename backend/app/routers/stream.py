"""流式生成路由"""

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.entities import ArticleTask, OutlineTask, PodcastTask, VideoTask, ZhihuArticleTask
from app.models.enums import TaskStatus
from app.models.schemas import StreamRequest
from app.services.llm import (
    LLMError,
    generate_article,
    generate_outline,
    generate_podcast_script_stream,
    generate_zhihu_article,
)
from app.services.podcast_tts import PodcastTTSError, generate_podcast_audio
from app.state import get_task, register_task
from app.utils.sse import sse_data, sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task/{video_task_id}/stream", tags=["stream"])


def get_video_task_with_transcript(video_task_id: str) -> VideoTask:
    """获取带转录内容的视频任务，不存在或无转录则抛异常"""
    task = get_task(video_task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not isinstance(task, VideoTask):
        raise HTTPException(status_code=400, detail="任务类型错误")
    if not task.transcript:
        raise HTTPException(status_code=400, detail="转录内容不存在")
    return task


@router.post("/outline")
async def stream_outline(
    video_task_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成大纲，创建新的 OutlineTask"""
    video_task = get_video_task_with_transcript(video_task_id)

    # 创建大纲任务
    task_id = str(uuid.uuid4())[:8]
    outline_task = OutlineTask(
        task_id=task_id,
        status=TaskStatus.READY,
        progress="正在生成大纲...",
        transcript=video_task.transcript,
    )
    register_task(outline_task)

    async def generate() -> AsyncIterator[str]:
        # 先返回新任务 ID
        yield sse_data({"task_id": task_id})

        chunks = []
        try:
            async for chunk in generate_outline(
                video_task.transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            outline_task.outline = "".join(chunks)
            outline_task.status = TaskStatus.COMPLETED
            outline_task.progress = "生成完成"
            yield sse_data({"done": True})
        except LLMError as e:
            outline_task.status = TaskStatus.FAILED
            outline_task.error = str(e)
            outline_task.progress = "生成失败"
            logger.warning("大纲任务 %s 生成失败: %s", task_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)


@router.post("/article")
async def stream_article(
    video_task_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成文章，创建新的 ArticleTask"""
    video_task = get_video_task_with_transcript(video_task_id)

    # 创建文章任务
    task_id = str(uuid.uuid4())[:8]
    article_task = ArticleTask(
        task_id=task_id,
        status=TaskStatus.READY,
        progress="正在生成文章...",
        transcript=video_task.transcript,
    )
    register_task(article_task)

    async def generate() -> AsyncIterator[str]:
        # 先返回新任务 ID
        yield sse_data({"task_id": task_id})

        chunks = []
        try:
            async for chunk in generate_article(
                video_task.transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            article_task.article = "".join(chunks)
            article_task.status = TaskStatus.COMPLETED
            article_task.progress = "生成完成"
            yield sse_data({"done": True})
        except LLMError as e:
            article_task.status = TaskStatus.FAILED
            article_task.error = str(e)
            article_task.progress = "生成失败"
            logger.warning("文章任务 %s 生成失败: %s", task_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)


@router.post("/podcast")
async def stream_podcast(
    video_task_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成播客脚本，完成后自动合成音频，创建新的 PodcastTask"""
    video_task = get_video_task_with_transcript(video_task_id)
    settings = get_settings()

    # 创建播客任务
    task_id = str(uuid.uuid4())[:8]
    podcast_task = PodcastTask(
        task_id=task_id,
        status=TaskStatus.READY,
        progress="正在生成播客脚本...",
        title=video_task.title,
        transcript=video_task.transcript,
    )
    register_task(podcast_task)

    async def generate() -> AsyncIterator[str]:
        # 先返回新任务 ID
        yield sse_data({"task_id": task_id})

        chunks = []
        try:
            # 流式生成脚本
            async for chunk in generate_podcast_script_stream(
                video_task.transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            podcast_task.podcast_script = "".join(chunks)
            yield sse_data({"script_done": True})

            # 合成音频
            podcast_task.progress = "正在合成音频..."
            yield sse_data({"synthesizing": True})
            try:
                audio_path = settings.temp_path / f"{task_id}_podcast.mp3"
                await generate_podcast_audio(
                    podcast_task.podcast_script, audio_path, temp_dir=settings.temp_path
                )
                podcast_task.podcast_audio_path = audio_path
                podcast_task.status = TaskStatus.COMPLETED
                podcast_task.progress = "生成完成"
                yield sse_data({"done": True, "has_audio": True})
            except PodcastTTSError as e:
                podcast_task.podcast_error = str(e)
                podcast_task.status = TaskStatus.COMPLETED
                podcast_task.progress = "脚本生成完成，音频合成失败"
                logger.warning("播客任务 %s 音频合成失败: %s", task_id, e)
                yield sse_data({"done": True, "has_audio": False, "audio_error": str(e)})
        except LLMError as e:
            podcast_task.status = TaskStatus.FAILED
            podcast_task.error = str(e)
            podcast_task.progress = "生成失败"
            logger.warning("播客任务 %s 脚本生成失败: %s", task_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)


@router.post("/zhihu-article")
async def stream_zhihu_article(
    video_task_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成知乎文章，创建新的 ZhihuArticleTask"""
    video_task = get_video_task_with_transcript(video_task_id)

    # 创建知乎文章任务
    task_id = str(uuid.uuid4())[:8]
    zhihu_task = ZhihuArticleTask(
        task_id=task_id,
        status=TaskStatus.READY,
        progress="正在生成知乎文章...",
        transcript=video_task.transcript,
    )
    register_task(zhihu_task)

    async def generate() -> AsyncIterator[str]:
        # 先返回新任务 ID
        yield sse_data({"task_id": task_id})

        chunks = []
        try:
            async for chunk in generate_zhihu_article(
                video_task.transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            zhihu_task.zhihu_article = "".join(chunks)
            zhihu_task.status = TaskStatus.COMPLETED
            zhihu_task.progress = "生成完成"
            yield sse_data({"done": True})
        except LLMError as e:
            zhihu_task.status = TaskStatus.FAILED
            zhihu_task.error = str(e)
            zhihu_task.progress = "生成失败"
            logger.warning("知乎文章任务 %s 生成失败: %s", task_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)
