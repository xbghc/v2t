"""资源下载路由"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.state import get_resource, get_task

router = APIRouter(prefix="/api", tags=["resource"])


@router.get("/resource/{resource_id}/video")
async def download_resource_video(resource_id: str) -> FileResponse:
    """下载视频资源"""
    resource = get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    if not resource.video_path or not resource.video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(
        resource.video_path,
        filename=resource.video_path.name,
        media_type="video/mp4",
    )


@router.get("/resource/{resource_id}/audio")
async def download_resource_audio(resource_id: str) -> FileResponse:
    """下载音频资源"""
    resource = get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    if not resource.audio_path or not resource.audio_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        resource.audio_path,
        filename=f"{resource.title}.mp3" if resource.title else "audio.mp3",
        media_type="audio/mpeg",
    )


@router.get("/task/{task_id}/podcast")
async def download_task_podcast(task_id: str) -> FileResponse:
    """下载播客音频文件"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.podcast_audio_path or not task.podcast_audio_path.exists():
        raise HTTPException(status_code=404, detail="播客音频文件不存在")

    return FileResponse(
        task.podcast_audio_path,
        filename=f"{task.title}_podcast.mp3" if task.title else "podcast.mp3",
        media_type="audio/mpeg",
    )
