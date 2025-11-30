"""v2t Web API 服务"""

import asyncio
import uuid
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from app.config import get_settings
from app.services.video_downloader import download_video, DownloadError
from app.services.transcribe import transcribe_video, extract_audio_async, TranscribeError
from app.services.gitcode_ai import generate_outline, generate_article, GitCodeAIError


class TaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    title: str = ""
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    transcript: str = ""
    outline: str = ""
    article: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)


# 内存存储任务（小规模使用足够）
tasks: dict[str, TaskResult] = {}

# 任务过期时间（1小时）
TASK_EXPIRE_SECONDS = 3600

app = FastAPI(title="v2t - 视频转文字", description="输入视频链接，获取视频、音频、大纲和详细文字")


class ProcessRequest(BaseModel):
    url: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: str
    title: str = ""
    has_video: bool = False
    has_audio: bool = False
    transcript: str = ""
    outline: str = ""
    article: str = ""
    error: str = ""


def cleanup_old_tasks():
    """清理过期任务"""
    now = time.time()
    expired = [
        tid for tid, task in tasks.items()
        if now - task.created_at > TASK_EXPIRE_SECONDS
    ]
    for tid in expired:
        task = tasks.pop(tid, None)
        if task:
            # 删除临时文件
            if task.video_path and task.video_path.exists():
                try:
                    task.video_path.unlink()
                except OSError:
                    pass
            if task.audio_path and task.audio_path.exists():
                try:
                    task.audio_path.unlink()
                except OSError:
                    pass


async def process_video_task(task_id: str, url: str):
    """后台处理视频任务"""
    task = tasks.get(task_id)
    if not task:
        return

    settings = get_settings()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 下载视频
        task.status = TaskStatus.DOWNLOADING
        task.progress = "正在下载视频..."

        video_result = await download_video(url, output_dir=output_dir)
        task.title = video_result.title
        task.video_path = video_result.path
        task.progress = f"下载完成: {video_result.title}"

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 2. 转录音频
        task.status = TaskStatus.TRANSCRIBING
        task.progress = "正在转录音频..."

        transcript, audio_path = await transcribe_video(video_result.path)
        task.audio_path = audio_path
        task.transcript = transcript
        task.progress = "转录完成"

        # 3. 生成 AI 内容
        task.status = TaskStatus.GENERATING

        # 生成大纲
        task.progress = "正在生成大纲..."
        try:
            outline = await generate_outline(transcript)
            if outline and len(outline.strip()) >= 50:
                task.outline = outline
        except GitCodeAIError:
            task.outline = ""  # 大纲生成失败，跳过

        # 生成详细文章
        task.progress = "正在生成详细内容..."
        try:
            article = await generate_article(transcript)
            if article and len(article.strip()) >= 50:
                task.article = article
        except GitCodeAIError:
            task.article = ""  # 文章生成失败，跳过

        # 完成
        task.status = TaskStatus.COMPLETED
        task.progress = "处理完成"

    except DownloadError as e:
        task.status = TaskStatus.FAILED
        task.error = f"下载失败: {e}"
        task.progress = task.error
    except TranscribeError as e:
        task.status = TaskStatus.FAILED
        task.error = f"转录失败: {e}"
        task.progress = task.error
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.progress = f"处理失败: {e}"


@app.post("/api/process", response_model=TaskResponse)
async def create_task(request: ProcessRequest, background_tasks: BackgroundTasks):
    """创建视频处理任务"""
    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = TaskResult(task_id=task_id)
    tasks[task_id] = task

    # 在后台执行处理
    background_tasks.add_task(process_video_task, task_id, request.url)

    return TaskResponse(
        task_id=task_id,
        status=task.status.value,
        progress=task.progress,
    )


@app.get("/api/task/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取任务状态"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    return TaskResponse(
        task_id=task.task_id,
        status=task.status.value,
        progress=task.progress,
        title=task.title,
        has_video=task.video_path is not None and task.video_path.exists(),
        has_audio=task.audio_path is not None and task.audio_path.exists(),
        transcript=task.transcript,
        outline=task.outline,
        article=task.article,
        error=task.error,
    )


@app.get("/api/task/{task_id}/video")
async def download_task_video(task_id: str):
    """下载视频文件"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.video_path or not task.video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(
        task.video_path,
        filename=task.video_path.name,
        media_type="video/mp4",
    )


@app.get("/api/task/{task_id}/audio")
async def download_task_audio(task_id: str):
    """下载音频文件"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.audio_path or not task.audio_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        task.audio_path,
        filename=f"{task.title}.mp3" if task.title else "audio.mp3",
        media_type="audio/mpeg",
    )


# 前端页面
@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>v2t Web</h1><p>前端文件未找到</p>")


def run_server(host: str = "0.0.0.0", port: int = 8100):
    """启动服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
