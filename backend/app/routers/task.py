"""任务查询路由"""

import asyncio
import json
from asyncio import Queue

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.entities import ArticleTask, OutlineTask, PodcastTask, VideoTask
from app.models.enums import TaskStatus
from app.models.schemas import (
    ArticleTaskResponse,
    OutlineTaskResponse,
    PodcastTaskResponse,
    VideoTaskResponse,
)
from app.state import get_resource_urls, get_task
from app.utils.sse import sse_heartbeat, sse_response

router = APIRouter(prefix="/api", tags=["task"])

# 响应类型联合
TaskResponse = VideoTaskResponse | OutlineTaskResponse | ArticleTaskResponse | PodcastTaskResponse


@router.get("/task/{task_id}")
async def get_task_status(task_id: str) -> TaskResponse:
    """获取任务状态"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if isinstance(task, VideoTask):
        video_url, audio_url = get_resource_urls(task.resource_id)
        return VideoTaskResponse(
            task_id=task.task_id,
            status=task.status.value,
            progress=task.progress,
            title=task.title,
            resource_id=task.resource_id,
            video_url=video_url,
            audio_url=audio_url,
            transcript=task.transcript,
            error=task.error,
        )
    elif isinstance(task, OutlineTask):
        return OutlineTaskResponse(
            task_id=task.task_id,
            status=task.status.value,
            progress=task.progress,
            outline=task.outline,
            error=task.error,
        )
    elif isinstance(task, ArticleTask):
        return ArticleTaskResponse(
            task_id=task.task_id,
            status=task.status.value,
            progress=task.progress,
            article=task.article,
            error=task.error,
        )
    elif isinstance(task, PodcastTask):
        return PodcastTaskResponse(
            task_id=task.task_id,
            status=task.status.value,
            progress=task.progress,
            title=task.title,
            podcast_script=task.podcast_script,
            has_podcast_audio=task.podcast_audio_path is not None
            and task.podcast_audio_path.exists(),
            podcast_error=task.podcast_error,
            error=task.error,
        )
    else:
        raise HTTPException(status_code=500, detail="未知任务类型")


@router.get("/task/{task_id}/status-stream")
async def stream_task_status(task_id: str, request: Request) -> StreamingResponse:
    """SSE 推送任务状态变化（仅支持 VideoTask 和 PodcastTask）"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 只有 VideoTask 和 PodcastTask 支持 SSE
    if not isinstance(task, (VideoTask, PodcastTask)):
        raise HTTPException(status_code=400, detail="该任务类型不支持状态流")

    # 创建队列（如果不存在）
    if not task.status_queue:
        task.status_queue = Queue()

    async def generate():
        # VideoTask: 发送当前状态
        if isinstance(task, VideoTask):
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
        # PodcastTask: 发送当前状态
        elif isinstance(task, PodcastTask):
            yield f"data: {json.dumps({
                'status': task.status.value,
                'progress': task.progress,
                'title': task.title,
                'podcast_script': task.podcast_script,
                'has_podcast_audio': task.podcast_audio_path is not None and task.podcast_audio_path.exists(),
                'podcast_error': task.podcast_error,
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
