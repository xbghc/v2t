"""v2t Web API 服务"""

import asyncio
import logging
import uuid
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Annotated
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import init_db, get_db
from app.models import User
from app.services.video_downloader import download_video, DownloadError
from app.services.transcribe import extract_audio_async, TranscribeError
from app.services.gitcode_ai import generate_outline, generate_article, GitCodeAIError
from app.services.auth import (
    send_code,
    verify_and_login,
    verify_token,
    get_user_by_id,
)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    logger.info("数据库初始化完成")
    yield
    # 关闭时的清理工作（如果需要）


app = FastAPI(
    title="v2t - 视频转文字",
    description="输入视频链接，获取视频、音频、大纲和详细文字",
    lifespan=lifespan,
)


# ============== 认证相关 ==============

class SendCodeRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: int
    email: str
    nickname: str
    balance: int


async def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """获取当前登录用户（可选）"""
    if not authorization:
        return None

    # 支持 "Bearer token" 格式
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    payload = verify_token(token)
    if not payload:
        return None

    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None

    return await get_user_by_id(db, user_id)


async def require_user(
    user: Annotated[Optional[User], Depends(get_current_user)]
) -> User:
    """要求用户必须登录"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


@app.post("/api/auth/send-code", response_model=AuthResponse)
async def api_send_code(
    request: SendCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """发送验证码"""
    success, message = await send_code(db, request.email)
    return AuthResponse(success=success, message=message)


@app.post("/api/auth/login", response_model=AuthResponse)
async def api_login(
    request: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """验证码登录"""
    success, message, token = await verify_and_login(db, request.email, request.code)
    return AuthResponse(success=success, message=message, token=token)


@app.get("/api/user/profile", response_model=UserProfileResponse)
async def api_get_profile(user: User = Depends(require_user)):
    """获取用户信息"""
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        balance=user.balance,
    )


# ============== 任务相关 ==============


class ProcessRequest(BaseModel):
    url: str
    download_only: bool = False  # 仅下载，不转录


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


async def process_video_task(task_id: str, url: str, download_only: bool = False):
    """后台处理视频任务"""
    task = tasks.get(task_id)
    if not task:
        return

    logger.info("任务 %s 开始处理: %s (仅下载: %s)", task_id, url, download_only)

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

        # 仅下载模式：提取音频后直接完成
        if download_only:
            task.status = TaskStatus.TRANSCRIBING
            task.progress = "正在提取音频..."
            audio_path = await extract_audio_async(video_result.path)
            task.audio_path = audio_path

            task.status = TaskStatus.COMPLETED
            task.progress = "下载完成"
            logger.info("任务 %s 下载完成: %s", task_id, task.title)
            return

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 2. 提取音频
        task.status = TaskStatus.TRANSCRIBING
        task.progress = "正在提取音频..."

        audio_path = await extract_audio_async(video_result.path)
        task.audio_path = audio_path
        task.progress = "正在转录音频..."

        # 3. 转录音频
        from app.services.transcribe import transcribe_audio
        transcript = await transcribe_audio(audio_path)
        task.transcript = transcript
        task.progress = "转录完成"

        # 4. 生成 AI 内容
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
        logger.info("任务 %s 处理完成: %s", task_id, task.title)

    except DownloadError as e:
        task.status = TaskStatus.FAILED
        task.error = f"下载失败: {e}"
        task.progress = task.error
        logger.warning("任务 %s 下载失败: %s", task_id, e)
    except TranscribeError as e:
        task.status = TaskStatus.FAILED
        task.error = f"转录失败: {e}"
        task.progress = task.error
        logger.warning("任务 %s 转录失败: %s", task_id, e)
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.progress = f"处理失败: {e}"
        logger.exception("任务 %s 处理异常", task_id)


@app.post("/api/process", response_model=TaskResponse)
async def create_task(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
):
    """创建视频处理任务（需要登录）"""
    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = TaskResult(task_id=task_id)
    tasks[task_id] = task

    # 在后台执行处理
    background_tasks.add_task(process_video_task, task_id, request.url, request.download_only)

    logger.info("用户 %s 创建任务 %s", user.email, task_id)

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
