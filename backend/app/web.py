"""v2t Web API 服务"""

import logging
import os
import time
import uuid
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
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
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
    READY_TO_STREAM = "ready_to_stream"  # 转录完成，等待流式生成
    GENERATING = "generating"
    GENERATING_PODCAST = "generating_podcast"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    title: str = ""
    video_path: Path | None = None
    audio_path: Path | None = None
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


# 内存存储任务（小规模使用足够）
tasks: dict[str, TaskResult] = {}

# 任务过期时间（1小时）
TASK_EXPIRE_SECONDS = 3600

app = FastAPI(title="v2t - 视频转文字", description="输入视频链接，获取视频、音频、大纲和详细文字")

# 挂载静态资源目录
static_path = Path(__file__).parent / "static" / "assets"
if static_path.exists():
    app.mount("/assets", StaticFiles(directory=static_path), name="assets")


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
    has_video: bool = False
    has_audio: bool = False
    transcript: str = ""
    outline: str = ""
    article: str = ""
    podcast_script: str = ""
    has_podcast_audio: bool = False
    podcast_error: str = ""  # 播客生成失败的错误信息
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
                except OSError as e:
                    logger.warning("清理视频文件失败 %s: %s", task.video_path, e)
            if task.audio_path and task.audio_path.exists():
                try:
                    task.audio_path.unlink()
                except OSError as e:
                    logger.warning("清理音频文件失败 %s: %s", task.audio_path, e)
            if task.podcast_audio_path and task.podcast_audio_path.exists():
                try:
                    task.podcast_audio_path.unlink()
                except OSError as e:
                    logger.warning("清理播客文件失败 %s: %s", task.podcast_audio_path, e)


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
        task.status = TaskStatus.DOWNLOADING
        task.progress = "正在下载视频..."

        video_result = await download_video(url, output_dir=output_dir)
        task.title = video_result.title
        task.video_path = video_result.path
        task.progress = f"下载完成: {video_result.title}"

        # 2. 提取音频（始终执行）
        task.status = TaskStatus.TRANSCRIBING
        task.progress = "正在提取音频..."
        audio_path = await extract_audio_async(video_result.path)
        task.audio_path = audio_path

        # 仅下载模式：不需要转录，直接完成
        if not need_transcribe:
            task.status = TaskStatus.COMPLETED
            task.progress = "下载完成"
            logger.info("任务 %s 下载完成: %s", task_id, task.title)
            return

        # 检查视频时长
        if video_result.duration and video_result.duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = video_result.duration // 60
            raise ValueError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

        # 3. 转录音频
        task.progress = "正在转录音频..."
        from app.services.transcribe import transcribe_audio
        transcript = await transcribe_audio(audio_path)
        task.transcript = transcript
        task.progress = "转录完成，准备生成内容"

        # 4. 设置为等待流式生成状态
        task.status = TaskStatus.READY_TO_STREAM
        logger.info("任务 %s 转录完成，等待流式生成", task_id)

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
        task.status = TaskStatus.GENERATING_PODCAST
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
        task.status = TaskStatus.SYNTHESIZING
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


async def process_podcast_task(task_id: str):
    """处理播客生成任务（在流式生成完成后调用）"""
    task = tasks.get(task_id)
    if not task or not task.generate_podcast_flag:
        return

    settings = get_settings()
    output_dir = settings.temp_path

    try:
        # 生成播客脚本
        task.status = TaskStatus.GENERATING_PODCAST
        task.progress = "正在生成播客脚本..."

        podcast_script = await generate_podcast_script(
            task.transcript,
            system_prompt=task.podcast_system_prompt or None,
            user_prompt=task.podcast_user_prompt or None,
        )
        if podcast_script and len(podcast_script.strip()) >= 50:
            task.podcast_script = podcast_script

            # 合成播客音频
            task.status = TaskStatus.SYNTHESIZING
            task.progress = "正在合成播客音频..."
            try:
                podcast_audio_path = output_dir / f"{task_id}_podcast.mp3"
                await generate_podcast_audio(
                    podcast_script,
                    podcast_audio_path,
                    temp_dir=output_dir,
                )
                task.podcast_audio_path = podcast_audio_path
            except PodcastTTSError as e:
                logger.warning("任务 %s 播客音频合成失败: %s", task_id, e)
                task.podcast_error = str(e)
    except LLMError as e:
        logger.warning("任务 %s 播客脚本生成失败: %s", task_id, e)


@app.get("/api/task/{task_id}/stream")
async def stream_task_content(task_id: str, request: Request):
    """SSE 流式传输 LLM 生成内容"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if task.status != TaskStatus.READY_TO_STREAM:
        raise HTTPException(status_code=400, detail=f"任务状态不正确: {task.status.value}")

    if not task.transcript:
        raise HTTPException(status_code=400, detail="转录内容不存在")

    async def event_generator():
        """生成 SSE 事件流"""
        try:
            task.status = TaskStatus.GENERATING
            task.progress = "正在生成内容..."

            # 流式生成大纲
            if task.generate_outline_flag:
                task.progress = "正在生成大纲..."
                outline_chunks = []
                try:
                    async for chunk in generate_outline(
                        task.transcript,
                        system_prompt=task.outline_system_prompt or None,
                        user_prompt=task.outline_user_prompt or None,
                    ):
                        # 检查客户端是否断开连接
                        if await request.is_disconnected():
                            logger.info("任务 %s 客户端断开连接", task_id)
                            return
                        outline_chunks.append(chunk)
                        yield f"event: outline\ndata: {json.dumps({'content': chunk, 'done': False})}\n\n"

                    # 保存完整大纲
                    full_outline = "".join(outline_chunks)
                    if full_outline and len(full_outline.strip()) >= 50:
                        task.outline = full_outline
                    yield f"event: outline\ndata: {json.dumps({'content': '', 'done': True})}\n\n"
                except LLMError as e:
                    logger.warning("任务 %s 大纲生成失败: %s", task_id, e)
                    yield f"event: error\ndata: {json.dumps({'type': 'outline', 'message': str(e)})}\n\n"

            # 流式生成文章
            if task.generate_article_flag:
                task.progress = "正在生成详细内容..."
                article_chunks = []
                try:
                    async for chunk in generate_article(
                        task.transcript,
                        system_prompt=task.article_system_prompt or None,
                        user_prompt=task.article_user_prompt or None,
                    ):
                        if await request.is_disconnected():
                            logger.info("任务 %s 客户端断开连接", task_id)
                            return
                        article_chunks.append(chunk)
                        yield f"event: article\ndata: {json.dumps({'content': chunk, 'done': False})}\n\n"

                    # 保存完整文章
                    full_article = "".join(article_chunks)
                    if full_article and len(full_article.strip()) >= 50:
                        task.article = full_article
                    yield f"event: article\ndata: {json.dumps({'content': '', 'done': True})}\n\n"
                except LLMError as e:
                    logger.warning("任务 %s 文章生成失败: %s", task_id, e)
                    yield f"event: error\ndata: {json.dumps({'type': 'article', 'message': str(e)})}\n\n"

            # 处理播客（非流式，在后台进行）
            if task.generate_podcast_flag:
                task.progress = "正在生成播客..."
                yield f"event: podcast_start\ndata: {json.dumps({'message': '开始生成播客'})}\n\n"
                await process_podcast_task(task_id)
                yield f"event: podcast_done\ndata: {json.dumps({'script': task.podcast_script, 'has_audio': task.podcast_audio_path is not None, 'error': task.podcast_error})}\n\n"

            # 完成
            task.status = TaskStatus.COMPLETED
            task.progress = "处理完成"
            logger.info("任务 %s 流式生成完成", task_id)
            yield f"event: complete\ndata: {json.dumps({'status': 'completed'})}\n\n"

        except Exception as e:
            logger.exception("任务 %s 流式生成异常", task_id)
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.progress = f"生成失败: {e}"
            yield f"event: error\ndata: {json.dumps({'type': 'fatal', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
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
        podcast_script=task.podcast_script,
        has_podcast_audio=task.podcast_audio_path is not None and task.podcast_audio_path.exists(),
        podcast_error=task.podcast_error,
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
    from app.deps import check_dependencies, get_install_hint

    missing = check_dependencies()
    if missing:
        deps_str = ", ".join(f"{cmd} ({desc})" for cmd, desc in missing)
        logger.error("缺少系统依赖: %s", deps_str)
        logger.error(get_install_hint())
        raise SystemExit(1)

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
