"""v2t Web API 服务"""

import asyncio
import hashlib
import logging
import os
import time
import uuid
from asyncio import Queue
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# 配置日志（支持 LOG_LEVEL 环境变量：DEBUG/INFO/WARNING/ERROR）
log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

import json

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm import (
    DEFAULT_ARTICLE_SYSTEM_PROMPT,
    DEFAULT_ARTICLE_USER_PROMPT,
    DEFAULT_OUTLINE_SYSTEM_PROMPT,
    DEFAULT_OUTLINE_USER_PROMPT,
    DEFAULT_PODCAST_SYSTEM_PROMPT,
    DEFAULT_PODCAST_USER_PROMPT,
    LLMError,
    generate_article,
    generate_outline,
    generate_podcast_script,
)
from app.services.podcast_tts import PodcastTTSError, generate_podcast_audio
from app.services.transcribe import TranscribeError, extract_audio_async
from app.services.video_downloader import DownloadError, download_video


class TaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    READY = "ready"  # 转录完成，可以开始生成（前端并行调用各生成端点）
    COMPLETED = "completed"
    FAILED = "failed"


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """计算文件内容哈希值"""
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]  # 取前 16 位作为 ID


@dataclass
class Resource:
    """资源（视频/音频文件）"""
    resource_id: str  # 文件内容哈希
    video_path: Path | None = None
    audio_path: Path | None = None
    title: str = ""
    created_at: float = field(default_factory=time.time)
    ref_count: int = 1  # 引用计数


# 资源存储（按哈希索引）
resources: dict[str, Resource] = {}

# 资源过期时间（2小时）
RESOURCE_EXPIRE_SECONDS = 7200


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    title: str = ""
    resource_id: str | None = None  # 关联的资源 ID（文件哈希）
    transcript: str = ""
    outline: str = ""
    article: str = ""
    podcast_script: str = ""
    podcast_audio_path: Path | None = None
    podcast_error: str = ""  # 播客生成失败的错误信息
    error: str = ""
    created_at: float = field(default_factory=time.time)
    # 生成选项（用于 SSE 流式生成）
    generate_outline_flag: bool = False
    generate_article_flag: bool = False
    generate_podcast_flag: bool = False
    # 自定义提示词
    outline_system_prompt: str = ""
    outline_user_prompt: str = ""
    article_system_prompt: str = ""
    article_user_prompt: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""
    # SSE 状态推送队列
    status_queue: Queue | None = field(default=None, repr=False)


# 内存存储任务（小规模使用足够）
tasks: dict[str, TaskResult] = {}

# 任务过期时间（1小时）
TASK_EXPIRE_SECONDS = 3600

app = FastAPI(title="v2t - 视频转文字", description="输入视频链接，获取视频、音频、大纲和详细文字")

class ProcessRequest(BaseModel):
    url: str
    # 生成选项（替代 download_only）
    generate_outline: bool = True
    generate_article: bool = True
    generate_podcast: bool = False
    # 自定义提示词，空字符串表示使用默认
    outline_system_prompt: str = ""
    outline_user_prompt: str = ""
    article_system_prompt: str = ""
    article_user_prompt: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""


class TextToPodcastRequest(BaseModel):
    """文本转播客请求"""
    text: str
    title: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""


class PromptsResponse(BaseModel):
    """默认提示词响应"""
    outline_system: str
    outline_user: str
    article_system: str
    article_user: str
    podcast_system: str
    podcast_user: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: str
    title: str = ""
    resource_id: str | None = None
    video_url: str | None = None  # 视频下载路径
    audio_url: str | None = None  # 音频下载路径
    transcript: str = ""
    outline: str = ""
    article: str = ""
    podcast_script: str = ""
    has_podcast_audio: bool = False
    podcast_error: str = ""  # 播客生成失败的错误信息
    error: str = ""


def get_resource_urls(resource_id: str | None) -> tuple[str | None, str | None]:
    """根据资源 ID 获取视频和音频 URL"""
    if not resource_id or resource_id not in resources:
        return None, None
    resource = resources[resource_id]
    video_url = f"/api/resource/{resource_id}/video" if resource.video_path and resource.video_path.exists() else None
    audio_url = f"/api/resource/{resource_id}/audio" if resource.audio_path and resource.audio_path.exists() else None
    return video_url, audio_url


def cleanup_old_resources():
    """清理过期资源"""
    now = time.time()
    expired = [
        rid for rid, res in resources.items()
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
            # 减少资源引用计数
            if task.resource_id and task.resource_id in resources:
                resources[task.resource_id].ref_count -= 1
            # 删除播客临时文件
            if task.podcast_audio_path and task.podcast_audio_path.exists():
                try:
                    task.podcast_audio_path.unlink()
                except OSError as e:
                    logger.warning("清理播客文件失败 %s: %s", task.podcast_audio_path, e)
    # 清理无引用的资源
    cleanup_old_resources()


async def update_task_status(task: TaskResult, status: TaskStatus, progress: str):
    """更新任务状态并推送 SSE 事件"""
    task.status = status
    task.progress = progress
    if task.status_queue:
        video_url, audio_url = get_resource_urls(task.resource_id)
        await task.status_queue.put({
            "status": status.value,
            "progress": progress,
            "title": task.title,
            "resource_id": task.resource_id,
            "video_url": video_url,
            "audio_url": audio_url,
            "transcript": task.transcript,
            "error": task.error,
        })


async def process_video_task(
    task_id: str,
    url: str,
    generate_outline_flag: bool = True,
    generate_article_flag: bool = True,
    generate_podcast_flag: bool = False,
    outline_system_prompt: str = "",
    outline_user_prompt: str = "",
    article_system_prompt: str = "",
    article_user_prompt: str = "",
    podcast_system_prompt: str = "",
    podcast_user_prompt: str = "",
):
    """后台处理视频任务（下载和转录阶段）"""
    task = tasks.get(task_id)
    if not task:
        return

    # 保存生成选项和提示词到任务中
    task.generate_outline_flag = generate_outline_flag
    task.generate_article_flag = generate_article_flag
    task.generate_podcast_flag = generate_podcast_flag
    task.outline_system_prompt = outline_system_prompt
    task.outline_user_prompt = outline_user_prompt
    task.article_system_prompt = article_system_prompt
    task.article_user_prompt = article_user_prompt
    task.podcast_system_prompt = podcast_system_prompt
    task.podcast_user_prompt = podcast_user_prompt

    # 判断是否需要转录（任一生成选项开启则需要转录）
    need_transcribe = generate_outline_flag or generate_article_flag or generate_podcast_flag
    logger.info(
        "任务 %s 开始处理: %s (大纲: %s, 文章: %s, 播客: %s)",
        task_id, url, generate_outline_flag, generate_article_flag, generate_podcast_flag
    )

    settings = get_settings()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 下载视频
        await update_task_status(task, TaskStatus.DOWNLOADING, "正在下载视频...")

        video_result = await download_video(url, output_dir=output_dir)
        task.title = video_result.title

        # 2. 计算视频哈希并创建/复用资源
        resource_id = compute_file_hash(video_result.path)
        if resource_id in resources:
            # 复用已有资源
            resource = resources[resource_id]
            resource.ref_count += 1
            logger.info("任务 %s 复用资源 %s", task_id, resource_id)
        else:
            # 创建新资源
            resource = Resource(
                resource_id=resource_id,
                video_path=video_result.path,
                title=video_result.title,
            )
            resources[resource_id] = resource
            logger.info("任务 %s 创建资源 %s", task_id, resource_id)

        task.resource_id = resource_id
        await update_task_status(task, TaskStatus.DOWNLOADING, f"下载完成: {video_result.title}")

        # 3. 提取音频（始终执行，如果资源中没有音频）
        await update_task_status(task, TaskStatus.TRANSCRIBING, "正在提取音频...")
        if not resource.audio_path or not resource.audio_path.exists():
            audio_path = await extract_audio_async(video_result.path)
            resource.audio_path = audio_path
        else:
            audio_path = resource.audio_path
            logger.info("任务 %s 复用音频资源", task_id)

        # 仅下载模式：不需要转录，直接完成
        if not need_transcribe:
            await update_task_status(task, TaskStatus.COMPLETED, "下载完成")
            logger.info("任务 %s 下载完成: %s", task_id, task.title)
            return

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 4. 转录音频
        await update_task_status(task, TaskStatus.TRANSCRIBING, "正在转录音频...")
        from app.services.transcribe import transcribe_audio
        transcript = await transcribe_audio(audio_path)
        task.transcript = transcript

        # 4. 设置为等待流式生成状态
        await update_task_status(task, TaskStatus.READY, "转录完成，准备生成内容")
        logger.info("任务 %s 转录完成，等待流式生成", task_id)

    except DownloadError as e:
        task.error = f"下载失败: {e}"
        await update_task_status(task, TaskStatus.FAILED, task.error)
        logger.warning("任务 %s 下载失败: %s", task_id, e)
    except TranscribeError as e:
        task.error = f"转录失败: {e}"
        await update_task_status(task, TaskStatus.FAILED, task.error)
        logger.warning("任务 %s 转录失败: %s", task_id, e)
    except Exception as e:
        task.error = str(e)
        await update_task_status(task, TaskStatus.FAILED, f"处理失败: {e}")
        logger.exception("任务 %s 处理异常", task_id)


async def process_text_task(
    task_id: str,
    text: str,
    title: str = "",
    podcast_system_prompt: str = "",
    podcast_user_prompt: str = "",
):
    """后台处理文本转播客任务"""
    task = tasks.get(task_id)
    if not task:
        return

    logger.info("任务 %s 开始处理文本转播客", task_id)

    settings = get_settings()
    output_dir = settings.temp_path
    output_dir.mkdir(parents=True, exist_ok=True)

    # 设置标题
    task.title = title or "文本转播客"
    task.transcript = text

    try:
        # 1. 生成播客脚本
        task.status = TaskStatus.READY
        task.progress = "正在生成播客脚本..."

        podcast_script = await generate_podcast_script(
            text,
            system_prompt=podcast_system_prompt or None,
            user_prompt=podcast_user_prompt or None,
        )
        if not podcast_script or len(podcast_script.strip()) < 50:
            raise LLMError("生成的播客脚本内容过短")

        task.podcast_script = podcast_script

        # 2. 合成播客音频
        task.progress = "正在合成播客音频..."

        podcast_audio_path = output_dir / f"{task_id}_podcast.mp3"
        await generate_podcast_audio(
            podcast_script,
            podcast_audio_path,
            temp_dir=output_dir,
        )
        task.podcast_audio_path = podcast_audio_path

        # 完成
        task.status = TaskStatus.COMPLETED
        task.progress = "处理完成"
        logger.info("任务 %s 文本转播客完成: %s", task_id, task.title)

    except LLMError as e:
        task.status = TaskStatus.FAILED
        task.error = f"播客脚本生成失败: {e}"
        task.progress = task.error
        logger.warning("任务 %s 播客脚本生成失败: %s", task_id, e)
    except PodcastTTSError as e:
        task.status = TaskStatus.FAILED
        task.error = f"播客音频合成失败: {e}"
        task.progress = task.error
        logger.warning("任务 %s 播客音频合成失败: %s", task_id, e)
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.progress = f"处理失败: {e}"
        logger.exception("任务 %s 处理异常", task_id)


@app.get("/api/task/{task_id}/stream/outline")
async def stream_outline(task_id: str, request: Request):
    """流式生成大纲"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.transcript:
        raise HTTPException(status_code=400, detail="转录内容不存在")

    async def generate():
        chunks = []
        try:
            async for chunk in generate_outline(
                task.transcript,
                system_prompt=task.outline_system_prompt or None,
                user_prompt=task.outline_user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            task.outline = "".join(chunks)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except LLMError as e:
            logger.warning("任务 %s 大纲生成失败: %s", task_id, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/task/{task_id}/stream/article")
async def stream_article(task_id: str, request: Request):
    """流式生成文章"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.transcript:
        raise HTTPException(status_code=400, detail="转录内容不存在")

    async def generate():
        chunks = []
        try:
            async for chunk in generate_article(
                task.transcript,
                system_prompt=task.article_system_prompt or None,
                user_prompt=task.article_user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            task.article = "".join(chunks)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except LLMError as e:
            logger.warning("任务 %s 文章生成失败: %s", task_id, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/task/{task_id}/stream/podcast")
async def stream_podcast(task_id: str, request: Request):
    """流式生成播客脚本，完成后自动合成音频"""
    from app.services.llm import generate_podcast_script_stream

    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.transcript:
        raise HTTPException(status_code=400, detail="转录内容不存在")

    settings = get_settings()

    async def generate():
        chunks = []
        try:
            # 流式生成脚本
            async for chunk in generate_podcast_script_stream(
                task.transcript,
                system_prompt=task.podcast_system_prompt or None,
                user_prompt=task.podcast_user_prompt or None,
            ):
                if await request.is_disconnected():
                    return
                chunks.append(chunk)
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            task.podcast_script = "".join(chunks)
            yield f"data: {json.dumps({'script_done': True})}\n\n"

            # 合成音频
            yield f"data: {json.dumps({'synthesizing': True})}\n\n"
            try:
                audio_path = settings.temp_path / f"{task_id}_podcast.mp3"
                await generate_podcast_audio(task.podcast_script, audio_path, temp_dir=settings.temp_path)
                task.podcast_audio_path = audio_path
                yield f"data: {json.dumps({'done': True, 'has_audio': True})}\n\n"
            except PodcastTTSError as e:
                task.podcast_error = str(e)
                logger.warning("任务 %s 播客音频合成失败: %s", task_id, e)
                yield f"data: {json.dumps({'done': True, 'has_audio': False, 'audio_error': str(e)})}\n\n"
        except LLMError as e:
            logger.warning("任务 %s 播客脚本生成失败: %s", task_id, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/prompts", response_model=PromptsResponse)
async def get_prompts():
    """获取默认提示词"""
    return PromptsResponse(
        outline_system=DEFAULT_OUTLINE_SYSTEM_PROMPT,
        outline_user=DEFAULT_OUTLINE_USER_PROMPT,
        article_system=DEFAULT_ARTICLE_SYSTEM_PROMPT,
        article_user=DEFAULT_ARTICLE_USER_PROMPT,
        podcast_system=DEFAULT_PODCAST_SYSTEM_PROMPT,
        podcast_user=DEFAULT_PODCAST_USER_PROMPT,
    )


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
    background_tasks.add_task(
        process_video_task,
        task_id,
        request.url,
        request.generate_outline,
        request.generate_article,
        request.generate_podcast,
        request.outline_system_prompt,
        request.outline_user_prompt,
        request.article_system_prompt,
        request.article_user_prompt,
        request.podcast_system_prompt,
        request.podcast_user_prompt,
    )

    return TaskResponse(
        task_id=task_id,
        status=task.status.value,
        progress=task.progress,
    )


@app.post("/api/text-to-podcast", response_model=TaskResponse)
async def create_text_to_podcast_task(request: TextToPodcastRequest, background_tasks: BackgroundTasks):
    """创建文本转播客任务"""
    # 验证文本内容
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文本内容过短")

    # 清理过期任务
    cleanup_old_tasks()

    # 创建新任务
    task_id = str(uuid.uuid4())[:8]
    task = TaskResult(task_id=task_id)
    tasks[task_id] = task

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


@app.get("/api/task/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取任务状态"""
    task = tasks.get(task_id)
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
        has_podcast_audio=task.podcast_audio_path is not None and task.podcast_audio_path.exists(),
        podcast_error=task.podcast_error,
        error=task.error,
    )


@app.get("/api/task/{task_id}/status-stream")
async def stream_task_status(task_id: str, request: Request):
    """SSE 推送任务状态变化"""
    task = tasks.get(task_id)
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
                if event.get('status') in ('completed', 'failed', 'ready'):
                    break
            except TimeoutError:
                # 发送心跳
                yield ": heartbeat\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/resource/{resource_id}/video")
async def download_resource_video(resource_id: str):
    """下载视频资源"""
    resource = resources.get(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    if not resource.video_path or not resource.video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(
        resource.video_path,
        filename=resource.video_path.name,
        media_type="video/mp4",
    )


@app.get("/api/resource/{resource_id}/audio")
async def download_resource_audio(resource_id: str):
    """下载音频资源"""
    resource = resources.get(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    if not resource.audio_path or not resource.audio_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        resource.audio_path,
        filename=f"{resource.title}.mp3" if resource.title else "audio.mp3",
        media_type="audio/mpeg",
    )


@app.get("/api/task/{task_id}/podcast")
async def download_task_podcast(task_id: str):
    """下载播客音频文件"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.podcast_audio_path or not task.podcast_audio_path.exists():
        raise HTTPException(status_code=404, detail="播客音频文件不存在")

    return FileResponse(
        task.podcast_audio_path,
        filename=f"{task.title}_podcast.mp3" if task.title else "podcast.mp3",
        media_type="audio/mpeg",
    )


async def check_api_connections() -> bool:
    """检测所有 API 连接，返回是否全部成功"""
    from app.services.llm import check_llm_api
    from app.services.podcast_tts import check_tts_api
    from app.services.transcribe import check_whisper_api

    checks = [
        ("LLM", check_llm_api()),
        ("Whisper", check_whisper_api()),
        ("TTS", check_tts_api()),
    ]

    all_ok = True
    for name, coro in checks:
        ok, msg = await coro
        if ok:
            logger.info("✓ %s API: %s", name, msg)
        else:
            logger.error("✗ %s API: %s", name, msg)
            all_ok = False

    return all_ok


def run_server(host: str = "0.0.0.0", port: int = 8101):
    """启动服务器"""
    import asyncio

    from app.deps import check_dependencies, get_install_hint

    missing = check_dependencies()
    if missing:
        deps_str = ", ".join(f"{cmd} ({desc})" for cmd, desc in missing)
        logger.error("缺少系统依赖: %s", deps_str)
        logger.error(get_install_hint())
        raise SystemExit(1)

    # 检测 API 连接
    if not asyncio.run(check_api_connections()):
        logger.error("API 检测失败，服务无法启动")
        raise SystemExit(1)

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
