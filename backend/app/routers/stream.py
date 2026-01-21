"""流式生成路由"""

import logging
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.entities import TaskResult
from app.services.llm import (
    LLMError,
    generate_article,
    generate_outline,
    generate_podcast_script_stream,
)
from app.services.podcast_tts import PodcastTTSError, generate_podcast_audio
from app.state import get_task
from app.utils.sse import sse_data, sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task/{task_id}/stream", tags=["stream"])


def get_task_with_transcript(task_id: str) -> TaskResult:
    """获取带转录内容的任务，不存在或无转录则抛异常"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.transcript:
        raise HTTPException(status_code=400, detail="转录内容不存在")
    return task


async def stream_llm_content(
    task_id: str,
    task: TaskResult,
    request: Request,
    llm_generator: Callable[[], AsyncIterator[str]],
    result_attr: str,
    error_prefix: str,
) -> AsyncIterator[str]:
    """通用的流式 LLM 内容生成"""
    chunks = []
    try:
        async for chunk in llm_generator():
            if await request.is_disconnected():
                return
            chunks.append(chunk)
            yield sse_data({"content": chunk})

        setattr(task, result_attr, "".join(chunks))
        yield sse_data({"done": True})
    except LLMError as e:
        logger.warning("任务 %s %s失败: %s", task_id, error_prefix, e)
        yield sse_data({"error": str(e)})


@router.get("/outline")
async def stream_outline(task_id: str, request: Request) -> StreamingResponse:
    """流式生成大纲"""
    task = get_task_with_transcript(task_id)

    async def generate():
        async for chunk in stream_llm_content(
            task_id,
            task,
            request,
            lambda: generate_outline(
                task.transcript,
                system_prompt=task.outline_system_prompt or None,
                user_prompt=task.outline_user_prompt or None,
            ),
            "outline",
            "大纲生成",
        ):
            yield chunk

    return sse_response(generate)


@router.get("/article")
async def stream_article(task_id: str, request: Request) -> StreamingResponse:
    """流式生成文章"""
    task = get_task_with_transcript(task_id)

    async def generate():
        async for chunk in stream_llm_content(
            task_id,
            task,
            request,
            lambda: generate_article(
                task.transcript,
                system_prompt=task.article_system_prompt or None,
                user_prompt=task.article_user_prompt or None,
            ),
            "article",
            "文章生成",
        ):
            yield chunk

    return sse_response(generate)


@router.get("/podcast")
async def stream_podcast(task_id: str, request: Request) -> StreamingResponse:
    """流式生成播客脚本，完成后自动合成音频"""
    task = get_task_with_transcript(task_id)
    settings = get_settings()

    async def generate():
        chunks = []
        try:
            # 流式生成脚本
            async for chunk in generate_podcast_script_stream(
                task.transcript,
                system_prompt=task.podcast_system_prompt or None,
                user_prompt=task.podcast_user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            task.podcast_script = "".join(chunks)
            yield sse_data({"script_done": True})

            # 合成音频
            yield sse_data({"synthesizing": True})
            try:
                audio_path = settings.temp_path / f"{task_id}_podcast.mp3"
                await generate_podcast_audio(
                    task.podcast_script, audio_path, temp_dir=settings.temp_path
                )
                task.podcast_audio_path = audio_path
                yield sse_data({"done": True, "has_audio": True})
            except PodcastTTSError as e:
                task.podcast_error = str(e)
                logger.warning("任务 %s 播客音频合成失败: %s", task_id, e)
                yield sse_data({"done": True, "has_audio": False, "audio_error": str(e)})
        except LLMError as e:
            logger.warning("任务 %s 播客脚本生成失败: %s", task_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)
