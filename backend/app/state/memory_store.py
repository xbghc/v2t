"""内存存储和状态管理"""

import logging
import time

from app.models.entities import PodcastTask, Resource, Task, VideoTask

logger = logging.getLogger(__name__)

# 资源存储（按哈希索引）
resources: dict[str, Resource] = {}

# 内存存储任务（小规模使用足够）
tasks: dict[str, Task] = {}

# 资源过期时间（2小时）
RESOURCE_EXPIRE_SECONDS = 7200

# 任务过期时间（1小时）
TASK_EXPIRE_SECONDS = 3600


def get_task(task_id: str) -> Task | None:
    """获取任务"""
    return tasks.get(task_id)


def get_resource(resource_id: str) -> Resource | None:
    """获取资源"""
    return resources.get(resource_id)


def register_task(task: Task) -> None:
    """注册任务"""
    tasks[task.task_id] = task


def register_resource(resource: Resource) -> None:
    """注册资源"""
    resources[resource.resource_id] = resource


def get_resource_urls(resource_id: str | None) -> tuple[str | None, str | None]:
    """根据资源 ID 获取视频和音频 URL"""
    if not resource_id or resource_id not in resources:
        return None, None
    resource = resources[resource_id]
    video_url = (
        f"/api/resource/{resource_id}/video"
        if resource.video_path and resource.video_path.exists()
        else None
    )
    audio_url = (
        f"/api/resource/{resource_id}/audio"
        if resource.audio_path and resource.audio_path.exists()
        else None
    )
    return video_url, audio_url


def cleanup_old_resources() -> None:
    """清理过期资源"""
    now = time.time()
    expired = [
        rid
        for rid, res in resources.items()
        if now - res.created_at > RESOURCE_EXPIRE_SECONDS and res.ref_count <= 0
    ]
    for rid in expired:
        res = resources.pop(rid, None)
        if res:
            if res.video_path and res.video_path.exists():
                try:
                    res.video_path.unlink()
                except OSError as e:
                    logger.warning("清理视频资源失败 %s: %s", res.video_path, e)
            if res.audio_path and res.audio_path.exists():
                try:
                    res.audio_path.unlink()
                except OSError as e:
                    logger.warning("清理音频资源失败 %s: %s", res.audio_path, e)


def cleanup_old_tasks() -> None:
    """清理过期任务"""
    now = time.time()
    expired = [
        tid for tid, task in tasks.items() if now - task.created_at > TASK_EXPIRE_SECONDS
    ]
    for tid in expired:
        task = tasks.pop(tid, None)
        if task:
            # VideoTask: 减少资源引用计数
            if isinstance(task, VideoTask) and task.resource_id and task.resource_id in resources:
                resources[task.resource_id].ref_count -= 1
            # PodcastTask: 删除播客临时文件
            if isinstance(task, PodcastTask) and task.podcast_audio_path and task.podcast_audio_path.exists():
                try:
                    task.podcast_audio_path.unlink()
                except OSError as e:
                    logger.warning("清理播客文件失败 %s: %s", task.podcast_audio_path, e)
    # 清理无引用的资源
    cleanup_old_resources()
