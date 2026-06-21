"""内容生成后台任务（outline / article / podcast）

与 HTTP 请求生命周期完全解耦：worker 一边从 LLM 拿 chunk 一边 XADD 到
Redis Stream，无论前端有没有在听都跑完整个流程。SSE 端点只负责消费 Stream。
"""

import logging
import uuid

from app.config import get_settings
from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceName, ResourceType
from app.services.llm import (
    LLMError,
    generate_article,
    generate_outline,
    generate_podcast_script_stream,
)
from app.services.podcast_tts import PodcastTTSError, generate_podcast_audio
from app.storage import (
    add_workspace_resource,
    get_file_storage,
    get_gen_task,
    get_redis,
    get_workspace,
    update_gen_task,
)
from app.storage.gen_stream import (
    xadd_chunk,
    xadd_done_and_finalize,
    xadd_error_and_finalize,
    xadd_event,
)

logger = logging.getLogger(__name__)


# 内容类型 → resource name 映射。注意 podcast 的脚本落成 PODCAST_SCRIPT，
# 音频另存为 PODCAST_AUDIO（见 _save_podcast_audio）——历史错位，用 Enum 显式化。
_RESOURCE_NAME = {
    "outline": ResourceName.OUTLINE,
    "article": ResourceName.ARTICLE,
    "podcast": ResourceName.PODCAST_SCRIPT,
}


async def _save_text_resource(
    workspace: Workspace, name: str, content: str, prompt: str
) -> WorkspaceResource:
    """落盘文本资源，返回 resource（用原子追加，避免并发覆盖）。"""
    storage = get_file_storage()
    resource_id = str(uuid.uuid4())[:8]
    storage_key = f"{workspace.workspace_id}/{name}_{resource_id}.txt"
    await storage.save_bytes(storage_key, content.encode("utf-8"))

    resource = WorkspaceResource(
        resource_id=resource_id,
        name=name,
        resource_type=ResourceType.TEXT,
        storage_key=storage_key,
        prompt=prompt,
        ready=True,
    )
    await add_workspace_resource(workspace.workspace_id, resource)
    return resource


async def _save_podcast_audio(
    workspace: Workspace, script_content: str
) -> WorkspaceResource:
    """合成播客音频并落盘，抛 PodcastTTSError 由调用方分类处理。"""
    settings = get_settings()
    storage = get_file_storage()
    audio_resource_id = str(uuid.uuid4())[:8]
    audio_path = (
        settings.temp_path
        / f"{workspace.workspace_id}_podcast_{audio_resource_id}.mp3"
    )
    await generate_podcast_audio(script_content, audio_path, temp_dir=settings.temp_path)

    audio_key = f"{workspace.workspace_id}/podcast_{audio_resource_id}.mp3"
    await storage.save_file(audio_key, audio_path)

    resource = WorkspaceResource(
        resource_id=audio_resource_id,
        name=ResourceName.PODCAST_AUDIO,
        resource_type=ResourceType.AUDIO,
        storage_key=audio_key,
        ready=True,
    )
    await add_workspace_resource(workspace.workspace_id, resource)
    return resource


def _llm_stream(content_type: str, transcript: str, system_prompt: str, user_prompt: str):
    sys_p = system_prompt or None
    user_p = user_prompt or None
    if content_type == "outline":
        return generate_outline(transcript, system_prompt=sys_p, user_prompt=user_p)
    if content_type == "article":
        return generate_article(transcript, system_prompt=sys_p, user_prompt=user_p)
    if content_type == "podcast":
        return generate_podcast_script_stream(
            transcript, system_prompt=sys_p, user_prompt=user_p
        )
    raise ValueError(f"未知 content_type: {content_type}")


async def run_generate_content(ctx: dict, task_id: str) -> None:
    """arq 入口：执行一次内容生成。

    Stream 的"显式终结"是协议契约——前端依赖 done/error sentinel 判断结束，
    所以无论成功失败都必须在 finally 之前写入对应的终结 entry。
    """
    redis = get_redis()
    task = await get_gen_task(task_id)
    if not task:
        logger.error("生成任务不存在: %s", task_id)
        return

    # 已终结：arq 重复 enqueue 或 worker 重启捡到已完成任务时跳过。
    # 跑到一半被中断的（status=running）不能简单续跑——LLM 已经写过 chunk 到
    # stream，重跑会 append 一份新的、前端会看到内容跳变。直接 fail 让用户重启
    # 新任务，新 task_id 对应新 stream，不污染旧的。
    if task.status == "running":
        logger.warning("任务 %s 状态为 running（前次中断），标记 failed", task_id)
        await update_gen_task(task_id, status="failed", error="任务被中断")
        await xadd_error_and_finalize(redis, task_id, "任务被中断")
        return
    if task.status in ("done", "failed"):
        logger.info("任务 %s 已是终态 %s，跳过", task_id, task.status)
        return

    workspace = await get_workspace(task.workspace_id)
    if not workspace:
        msg = "工作区不存在或已过期"
        await update_gen_task(task_id, status="failed", error=msg)
        await xadd_error_and_finalize(redis, task_id, msg)
        return

    transcript_resource = workspace.get_resource(ResourceName.TRANSCRIPT)
    if not transcript_resource or not transcript_resource.storage_key:
        msg = "转录内容不存在"
        await update_gen_task(task_id, status="failed", error=msg)
        await xadd_error_and_finalize(redis, task_id, msg)
        return

    try:
        storage = get_file_storage()
        content_bytes = await storage.get_bytes(transcript_resource.storage_key)
        transcript = content_bytes.decode("utf-8")
    except Exception as e:
        msg = f"读取转录内容失败: {e}"
        await update_gen_task(task_id, status="failed", error=msg)
        await xadd_error_and_finalize(redis, task_id, msg)
        return

    if not transcript:
        msg = "转录内容为空"
        await update_gen_task(task_id, status="failed", error=msg)
        await xadd_error_and_finalize(redis, task_id, msg)
        return

    await update_gen_task(task_id, status="running")
    logger.info(
        "任务 %s (%s) 开始执行: workspace=%s",
        task_id, task.content_type, task.workspace_id,
    )

    chunks: list[str] = []
    prompt_record = f"system: {task.system_prompt}\nuser: {task.user_prompt}"
    try:
        async for chunk in _llm_stream(
            task.content_type, transcript, task.system_prompt, task.user_prompt
        ):
            chunks.append(chunk)
            await xadd_chunk(redis, task_id, chunk)

        content = "".join(chunks)
        resource_name = _RESOURCE_NAME[task.content_type]
        text_resource = await _save_text_resource(
            workspace, resource_name, content, prompt_record
        )

        if task.content_type != "podcast":
            await update_gen_task(
                task_id, status="done", resource_id=text_resource.resource_id
            )
            await xadd_done_and_finalize(
                redis, task_id, {"resource_id": text_resource.resource_id}
            )
            return

        # podcast：脚本流结束 → 进 TTS 阶段
        await xadd_event(redis, task_id, {"type": "script_done"})
        await xadd_event(redis, task_id, {"type": "synthesizing"})
        try:
            audio_resource = await _save_podcast_audio(workspace, content)
            await update_gen_task(
                task_id,
                status="done",
                resource_id=text_resource.resource_id,
                audio_resource_id=audio_resource.resource_id,
            )
            await xadd_done_and_finalize(redis, task_id, {
                "resource_id": text_resource.resource_id,
                "has_audio": "1",
                "audio_resource_id": audio_resource.resource_id,
            })
        except PodcastTTSError as e:
            logger.warning("任务 %s 播客 TTS 失败: %s", task_id, e)
            # 脚本本身成功 → task 仍标 done，单独记 audio_error
            await update_gen_task(
                task_id,
                status="done",
                resource_id=text_resource.resource_id,
                audio_error=str(e),
            )
            await xadd_done_and_finalize(redis, task_id, {
                "resource_id": text_resource.resource_id,
                "has_audio": "0",
                "audio_error": str(e),
            })
    except LLMError as e:
        logger.warning("任务 %s LLM 失败: %s", task_id, e)
        await update_gen_task(task_id, status="failed", error=str(e))
        await xadd_error_and_finalize(redis, task_id, str(e))
    except Exception as e:
        logger.exception("任务 %s 未预期错误", task_id)
        await update_gen_task(task_id, status="failed", error=str(e))
        await xadd_error_and_finalize(redis, task_id, str(e))
