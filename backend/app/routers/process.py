"""任务创建路由"""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.entities import PodcastTask, VideoTask
from app.models.schemas import (
    PodcastTaskResponse,
    ProcessRequest,
    TextToPodcastRequest,
    VideoTaskResponse,
)
from app.state import cleanup_old_tasks, register_task
from app.tasks import process_text_to_podcast_task, process_video_task

router = APIRouter(prefix="/api", tags=["process"])


@router.post("/process-video", response_model=VideoTaskResponse)
async def create_task(
    request: ProcessRequest, background_tasks: BackgroundTasks
) -> VideoTaskResponse:
    """创建视频处理任务"""
    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = VideoTask(task_id=task_id)
    register_task(task)

    # 在后台执行处理
    background_tasks.add_task(
        process_video_task,
        task_id,
        request.url,
    )

    return VideoTaskResponse(
        task_id=task_id,
        status=task.status.value,
        progress=task.progress,
    )


@router.post("/text-to-podcast", response_model=PodcastTaskResponse)
async def create_text_to_podcast_task(
    request: TextToPodcastRequest, background_tasks: BackgroundTasks
) -> PodcastTaskResponse:
    """创建文本转播客任务"""
    # 验证文本内容
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文本内容过短")

    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = PodcastTask(task_id=task_id)
    register_task(task)

    # 在后台执行处理
    background_tasks.add_task(
        process_text_to_podcast_task,
        task_id,
        request.text,
        request.title,
        request.podcast_system_prompt,
        request.podcast_user_prompt,
    )

    return PodcastTaskResponse(
        task_id=task_id,
        status=task.status.value,
        progress=task.progress,
    )
