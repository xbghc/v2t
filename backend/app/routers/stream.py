"""流式生成路由"""

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType
from app.models.schemas import StreamRequest
from app.services.llm import (
    LLMError,
    generate_article,
    generate_outline,
    generate_podcast_script_stream,
    generate_zhihu_article,
)
from app.services.podcast_tts import PodcastTTSError, generate_podcast_audio
from app.storage import get_file_storage, get_workspace, save_workspace
from app.utils.sse import sse_data, sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces/{workspace_id}/stream", tags=["stream"])


async def get_workspace_with_transcript(workspace_id: str) -> tuple[Workspace, str]:
    """获取带转录内容的工作区，不存在或无转录则抛异常"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在或已过期")

    # 获取转录内容
    transcript_resource = workspace.get_resource("transcript")
    if not transcript_resource or not transcript_resource.storage_key:
        raise HTTPException(status_code=400, detail="转录内容不存在")

    try:
        storage = get_file_storage()
        content_bytes = await storage.get_bytes(transcript_resource.storage_key)
        transcript = content_bytes.decode("utf-8")
        if not transcript:
            raise HTTPException(status_code=400, detail="转录内容为空")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取转录内容失败: {e}")

    return workspace, transcript


async def save_text_resource(
    workspace: Workspace,
    name: str,
    content: str,
    prompt: str = "",
) -> WorkspaceResource:
    """保存文本资源（纯文本），prompt 存储在元数据中"""
    storage = get_file_storage()
    resource_id = str(uuid.uuid4())[:8]
    storage_key = f"{workspace.workspace_id}/{name}_{resource_id}.txt"

    # 保存纯文本到本地存储
    await storage.save_bytes(storage_key, content.encode("utf-8"))

    resource = WorkspaceResource(
        resource_id=resource_id,
        name=name,
        resource_type=ResourceType.TEXT,
        storage_key=storage_key,
        prompt=prompt,
    )
    workspace.add_resource(resource)
    # 持久化到存储
    await save_workspace(workspace)
    return resource


@router.post("/outline")
async def stream_outline(
    workspace_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成大纲"""
    workspace, transcript = await get_workspace_with_transcript(workspace_id)
    resource_id = str(uuid.uuid4())[:8]

    async def generate() -> AsyncIterator[str]:
        yield sse_data({"resource_id": resource_id})

        chunks = []
        try:
            async for chunk in generate_outline(
                transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            # 保存资源
            content = "".join(chunks)
            prompt = f"system: {body.system_prompt}\nuser: {body.user_prompt}"
            await save_text_resource(workspace, "outline", content, prompt)
            yield sse_data({"done": True})
        except LLMError as e:
            logger.warning("工作区 %s 大纲生成失败: %s", workspace_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)


@router.post("/article")
async def stream_article(
    workspace_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成文章"""
    workspace, transcript = await get_workspace_with_transcript(workspace_id)
    resource_id = str(uuid.uuid4())[:8]

    async def generate() -> AsyncIterator[str]:
        yield sse_data({"resource_id": resource_id})

        chunks = []
        try:
            async for chunk in generate_article(
                transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            content = "".join(chunks)
            prompt = f"system: {body.system_prompt}\nuser: {body.user_prompt}"
            await save_text_resource(workspace, "article", content, prompt)
            yield sse_data({"done": True})
        except LLMError as e:
            logger.warning("工作区 %s 文章生成失败: %s", workspace_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)


@router.post("/podcast")
async def stream_podcast(
    workspace_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成播客脚本，完成后自动合成音频"""
    workspace, transcript = await get_workspace_with_transcript(workspace_id)
    settings = get_settings()
    storage = get_file_storage()
    resource_id = str(uuid.uuid4())[:8]

    async def generate() -> AsyncIterator[str]:
        yield sse_data({"resource_id": resource_id})

        chunks = []
        try:
            # 流式生成脚本
            async for chunk in generate_podcast_script_stream(
                transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            script_content = "".join(chunks)
            prompt = f"system: {body.system_prompt}\nuser: {body.user_prompt}"
            await save_text_resource(workspace, "podcast_script", script_content, prompt)
            yield sse_data({"script_done": True})

            # 合成音频
            yield sse_data({"synthesizing": True})
            try:
                audio_resource_id = str(uuid.uuid4())[:8]
                # 先生成到本地临时文件
                audio_path = settings.temp_path / f"{workspace_id}_podcast_{audio_resource_id}.mp3"
                await generate_podcast_audio(
                    script_content, audio_path, temp_dir=settings.temp_path
                )
                # 保存音频文件
                audio_key = f"{workspace_id}/podcast_{audio_resource_id}.mp3"
                await storage.save_file(audio_key, audio_path)

                # 添加播客音频资源
                audio_resource = WorkspaceResource(
                    resource_id=audio_resource_id,
                    name="podcast",
                    resource_type=ResourceType.AUDIO,
                    storage_key=audio_key,
                )
                workspace.add_resource(audio_resource)
                # 持久化到存储
                await save_workspace(workspace)
                yield sse_data({"done": True, "has_audio": True, "audio_resource_id": audio_resource_id})
            except PodcastTTSError as e:
                logger.warning("工作区 %s 播客音频合成失败: %s", workspace_id, e)
                yield sse_data({"done": True, "has_audio": False, "audio_error": str(e)})
        except LLMError as e:
            logger.warning("工作区 %s 播客脚本生成失败: %s", workspace_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)


@router.post("/zhihu-article")
async def stream_zhihu_article(
    workspace_id: str, request: Request, body: StreamRequest
) -> StreamingResponse:
    """流式生成知乎文章"""
    workspace, transcript = await get_workspace_with_transcript(workspace_id)
    resource_id = str(uuid.uuid4())[:8]

    async def generate() -> AsyncIterator[str]:
        yield sse_data({"resource_id": resource_id})

        chunks = []
        try:
            async for chunk in generate_zhihu_article(
                transcript,
                system_prompt=body.system_prompt or None,
                user_prompt=body.user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield sse_data({"content": chunk})

            content = "".join(chunks)
            prompt = f"system: {body.system_prompt}\nuser: {body.user_prompt}"
            await save_text_resource(workspace, "zhihu", content, prompt)
            yield sse_data({"done": True})
        except LLMError as e:
            logger.warning("工作区 %s 知乎文章生成失败: %s", workspace_id, e)
            yield sse_data({"error": str(e)})

    return sse_response(generate)
