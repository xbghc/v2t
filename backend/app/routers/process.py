"""任务创建路由"""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.entities import TaskResult
from app.models.schemas import ProcessRequest, TaskResponse, TextToPodcastRequest
from app.state import cleanup_old_tasks, register_task
from app.tasks import VideoTaskOptions, process_text_task, process_video_task

router = APIRouter(prefix="/api", tags=["process"])


@router.post("/process", response_model=TaskResponse)
async def create_task(
    request: ProcessRequest, background_tasks: BackgroundTasks
) -> TaskResponse:
    """创建视频处理任务"""
    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = TaskResult(task_id=task_id)
    register_task(task)

    # 封装选项
    options = VideoTaskOptions(
        generate_outline=request.generate_outline,
        generate_article=request.generate_article,
        generate_podcast=request.generate_podcast,
        outline_system_prompt=request.outline_system_prompt,
        outline_user_prompt=request.outline_user_prompt,
        article_system_prompt=request.article_system_prompt,
        article_user_prompt=request.article_user_prompt,
        podcast_system_prompt=request.podcast_system_prompt,
        podcast_user_prompt=request.podcast_user_prompt,
    )

    # 在后台执行处理
    background_tasks.add_task(
        process_video_task,
        task_id,
        request.url,
        options,
    )

    return TaskResponse(
        task_id=task_id,
        status=task.status.value,
        progress=task.progress,
    )


@router.post("/text-to-podcast", response_model=TaskResponse)
async def create_text_to_podcast_task(
    request: TextToPodcastRequest, background_tasks: BackgroundTasks
) -> TaskResponse:
    """创建文本转播客任务"""
    # 验证文本内容
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文本内容过短")

    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = TaskResult(task_id=task_id)
    register_task(task)

    # 在后台执行处理
    background_tasks.add_task(
        process_text_task,
        task_id,
        request.text,
        request.title,
        request.podcast_system_prompt,
        request.podcast_user_prompt,
    )

    return TaskResponse(
        task_id=task_id,
        status=task.status.value,
        progress=task.progress,
    )
