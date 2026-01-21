"""任务查询路由"""

import asyncio
import json
from asyncio import Queue

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.enums import TaskStatus
from app.models.schemas import TaskResponse
from app.state import get_resource_urls, get_task
from app.utils.sse import sse_heartbeat, sse_response

router = APIRouter(prefix="/api", tags=["task"])


@router.get("/task/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str) -> TaskResponse:
    """获取任务状态"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    video_url, audio_url = get_resource_urls(task.resource_id)
    return TaskResponse(
        task_id=task.task_id,
        status=task.status.value,
        progress=task.progress,
        title=task.title,
        resource_id=task.resource_id,
        video_url=video_url,
        audio_url=audio_url,
        transcript=task.transcript,
        outline=task.outline,
        article=task.article,
        podcast_script=task.podcast_script,
        has_podcast_audio=task.podcast_audio_path is not None
        and task.podcast_audio_path.exists(),
        podcast_error=task.podcast_error,
        error=task.error,
    )


@router.get("/task/{task_id}/status-stream")
async def stream_task_status(task_id: str, request: Request) -> StreamingResponse:
    """SSE 推送任务状态变化"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 创建队列（如果不存在）
    if not task.status_queue:
        task.status_queue = Queue()

    async def generate():
        # 先发送当前状态
        video_url, audio_url = get_resource_urls(task.resource_id)
        yield f"data: {json.dumps({
            'status': task.status.value,
            'progress': task.progress,
            'title': task.title,
            'resource_id': task.resource_id,
            'video_url': video_url,
            'audio_url': audio_url,
            'transcript': task.transcript,
            'error': task.error,
        })}\n\n"

        # 如果任务已完成或失败，直接返回
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return

        # 持续监听状态变化
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(task.status_queue.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in ("completed", "failed", "ready"):
                    break
            except TimeoutError:
                # 发送心跳
                yield sse_heartbeat()

    return sse_response(generate)
