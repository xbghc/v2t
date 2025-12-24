"""v2t Web API 服务 - 资源导向 + SSE"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.database import (
    init_db,
    create_video, get_video, update_video, delete_video,
    create_transcript, get_transcript, get_transcript_by_video, update_transcript,
    create_outline, get_outline, get_outline_by_transcript, update_outline,
    create_article, get_article, get_article_by_transcript, update_article,
    Video, Transcript, Outline, Article,
)
from app.services.video_downloader import download_video, DownloadError
from app.services.transcribe import extract_audio_async, transcribe_audio, TranscribeError
from app.services.gitcode_ai import generate_outline as ai_generate_outline, generate_article as ai_generate_article, GitCodeAIError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="v2t - 视频转文字", description="资源导向的视频转文字 API")

# 挂载静态资源目录
static_path = Path(__file__).parent / "static" / "assets"
if static_path.exists():
    app.mount("/assets", StaticFiles(directory=static_path), name="assets")

# SSE 事件队列 - 用于实时推送进度
# key: resource_type:resource_id, value: asyncio.Queue
sse_queues: dict[str, asyncio.Queue] = {}


# ============ Pydantic Models ============

class VideoCreateRequest(BaseModel):
    url: str


class VideoResponse(BaseModel):
    id: str
    url: Optional[str] = None
    title: Optional[str] = None
    status: str
    has_video: bool = False
    has_audio: bool = False
    created: bool = False
    created_at: str


class TranscriptCreateRequest(BaseModel):
    video_id: str


class TranscriptResponse(BaseModel):
    id: str
    video_id: Optional[str] = None
    status: str
    content: Optional[str] = None
    created_at: str


class OutlineResponse(BaseModel):
    id: str
    transcript_id: str
    status: str
    content: Optional[str] = None
    created_at: str


class ArticleResponse(BaseModel):
    id: str
    transcript_id: str
    status: str
    content: Optional[str] = None
    created_at: str


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


# ============ SSE Helpers ============

def get_sse_key(resource_type: str, resource_id: str) -> str:
    return f"{resource_type}:{resource_id}"


async def send_sse_event(resource_type: str, resource_id: str, event: str, data: dict):
    """发送 SSE 事件到对应的队列"""
    key = get_sse_key(resource_type, resource_id)
    if key in sse_queues:
        await sse_queues[key].put({"event": event, "data": data})


async def sse_generator(resource_type: str, resource_id: str) -> AsyncGenerator[str, None]:
    """SSE 事件生成器"""
    key = get_sse_key(resource_type, resource_id)

    # 创建队列
    queue = asyncio.Queue()
    sse_queues[key] = queue

    try:
        while True:
            try:
                # 等待事件，超时 30 秒发送心跳
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                event = msg["event"]
                data = json.dumps(msg["data"], ensure_ascii=False)
                yield f"event: {event}\ndata: {data}\n\n"

                # done 事件后退出
                if event == "done" or event == "error":
                    break
            except asyncio.TimeoutError:
                # 发送心跳
                yield ": heartbeat\n\n"
    finally:
        # 清理队列
        sse_queues.pop(key, None)


# ============ Startup ============

@app.on_event("startup")
async def startup():
    """应用启动时初始化数据库"""
    await init_db()
    logger.info("数据库初始化完成")


# ============ Videos API ============

@app.post("/api/videos", response_model=VideoResponse)
async def api_create_video(request: VideoCreateRequest, background_tasks: BackgroundTasks):
    """创建视频资源并开始下载"""
    video, created = await create_video(request.url)

    if created:
        # 新建，启动后台下载任务
        background_tasks.add_task(process_video_download, video.id)

    video_path = Path(video.video_path) if video.video_path else None
    audio_path = Path(video.audio_path) if video.audio_path else None

    return VideoResponse(
        id=video.id,
        url=video.normalized_url,
        title=video.title,
        status=video.status,
        has_video=video_path is not None and video_path.exists(),
        has_audio=audio_path is not None and audio_path.exists(),
        created=created,
        created_at=video.created_at,
    )


@app.get("/api/videos/{video_id}", response_model=VideoResponse)
async def api_get_video(video_id: str):
    """获取视频状态"""
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    video_path = Path(video.video_path) if video.video_path else None
    audio_path = Path(video.audio_path) if video.audio_path else None

    return VideoResponse(
        id=video.id,
        url=video.normalized_url,
        title=video.title,
        status=video.status,
        has_video=video_path is not None and video_path.exists(),
        has_audio=audio_path is not None and audio_path.exists(),
        created=False,
        created_at=video.created_at,
    )


@app.get("/api/videos/{video_id}/events")
async def api_video_events(video_id: str):
    """SSE 订阅视频下载进度"""
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    return StreamingResponse(
        sse_generator("video", video_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.delete("/api/videos/{video_id}", response_model=MessageResponse)
async def api_delete_video(video_id: str):
    """删除视频及关联文件"""
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    # 删除文件
    if video.video_path:
        try:
            Path(video.video_path).unlink(missing_ok=True)
        except OSError:
            pass
    if video.audio_path:
        try:
            Path(video.audio_path).unlink(missing_ok=True)
        except OSError:
            pass

    await delete_video(video_id)
    return MessageResponse(message="视频已删除")


@app.get("/api/videos/{video_id}/file")
async def api_download_video_file(video_id: str):
    """下载视频文件"""
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if not video.video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    video_path = Path(video.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(
        video_path,
        filename=video_path.name,
        media_type="video/mp4",
    )


@app.get("/api/videos/{video_id}/audio")
async def api_download_audio_file(video_id: str):
    """下载音频文件"""
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if not video.audio_path:
        raise HTTPException(status_code=404, detail="音频文件不存在")

    audio_path = Path(video.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    filename = f"{video.title}.mp3" if video.title else "audio.mp3"
    return FileResponse(
        audio_path,
        filename=filename,
        media_type="audio/mpeg",
    )


# ============ Transcripts API ============

@app.post("/api/transcripts", response_model=TranscriptResponse, status_code=201)
async def api_create_transcript(request: TranscriptCreateRequest, background_tasks: BackgroundTasks):
    """创建转录"""
    # 检查视频是否存在且已完成
    video = await get_video(request.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if video.status != "completed":
        raise HTTPException(status_code=409, detail="视频尚未下载完成")

    # 创建转录记录
    transcript = await create_transcript(video_id=request.video_id)

    # 启动后台转录任务
    background_tasks.add_task(process_transcript, transcript.id, video)

    return TranscriptResponse(
        id=transcript.id,
        video_id=transcript.video_id,
        status="processing",
        content=transcript.content,
        created_at=transcript.created_at,
    )


@app.get("/api/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def api_get_transcript(transcript_id: str):
    """获取转录状态"""
    transcript = await get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="转录不存在")

    return TranscriptResponse(
        id=transcript.id,
        video_id=transcript.video_id,
        status=transcript.status,
        content=transcript.content,
        created_at=transcript.created_at,
    )


@app.get("/api/transcripts/{transcript_id}/events")
async def api_transcript_events(transcript_id: str):
    """SSE 订阅转录进度"""
    transcript = await get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="转录不存在")

    return StreamingResponse(
        sse_generator("transcript", transcript_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ Outlines API ============

@app.post("/api/transcripts/{transcript_id}/outline", response_model=OutlineResponse, status_code=201)
async def api_create_outline(transcript_id: str, background_tasks: BackgroundTasks):
    """创建大纲"""
    transcript = await get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="转录不存在")
    if transcript.status != "completed":
        raise HTTPException(status_code=409, detail="转录尚未完成")

    # 创建大纲记录
    outline = await create_outline(transcript_id=transcript_id)

    # 启动后台生成任务
    background_tasks.add_task(process_outline, outline.id, transcript.content)

    return OutlineResponse(
        id=outline.id,
        transcript_id=outline.transcript_id,
        status="processing",
        content=outline.content,
        created_at=outline.created_at,
    )


@app.get("/api/transcripts/{transcript_id}/outline", response_model=OutlineResponse)
async def api_get_outline(transcript_id: str):
    """获取大纲"""
    outline = await get_outline_by_transcript(transcript_id)
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在，请先调用 POST 创建")

    return OutlineResponse(
        id=outline.id,
        transcript_id=outline.transcript_id,
        status=outline.status,
        content=outline.content,
        created_at=outline.created_at,
    )


@app.get("/api/transcripts/{transcript_id}/outline/events")
async def api_outline_events(transcript_id: str):
    """SSE 订阅大纲生成进度"""
    outline = await get_outline_by_transcript(transcript_id)
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")

    return StreamingResponse(
        sse_generator("outline", outline.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ Articles API ============

@app.post("/api/transcripts/{transcript_id}/article", response_model=ArticleResponse, status_code=201)
async def api_create_article(transcript_id: str, background_tasks: BackgroundTasks):
    """创建文章"""
    transcript = await get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="转录不存在")
    if transcript.status != "completed":
        raise HTTPException(status_code=409, detail="转录尚未完成")

    # 创建文章记录
    article = await create_article(transcript_id=transcript_id)

    # 启动后台生成任务
    background_tasks.add_task(process_article, article.id, transcript.content)

    return ArticleResponse(
        id=article.id,
        transcript_id=article.transcript_id,
        status="processing",
        content=article.content,
        created_at=article.created_at,
    )


@app.get("/api/transcripts/{transcript_id}/article", response_model=ArticleResponse)
async def api_get_article(transcript_id: str):
    """获取文章"""
    article = await get_article_by_transcript(transcript_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在，请先调用 POST 创建")

    return ArticleResponse(
        id=article.id,
        transcript_id=article.transcript_id,
        status=article.status,
        content=article.content,
        created_at=article.created_at,
    )


@app.get("/api/transcripts/{transcript_id}/article/events")
async def api_article_events(transcript_id: str):
    """SSE 订阅文章生成进度"""
    article = await get_article_by_transcript(transcript_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    return StreamingResponse(
        sse_generator("article", article.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ Background Tasks ============

async def process_video_download(video_id: str):
    """后台任务：下载视频"""
    logger.info("开始下载视频: %s", video_id)

    try:
        await update_video(video_id, status="downloading")
        await send_sse_event("video", video_id, "status", {"status": "downloading", "progress": "开始下载..."})

        video = await get_video(video_id)
        settings = get_settings()
        output_dir = settings.temp_path

        # 下载视频
        result = await download_video(video.original_url, output_dir=output_dir)

        await send_sse_event("video", video_id, "status", {"status": "downloading", "progress": "下载完成，提取音频..."})

        # 提取音频
        audio_path = await extract_audio_async(result.path)

        # 更新数据库
        await update_video(
            video_id,
            status="completed",
            title=result.title,
            download_url=result.url if hasattr(result, 'url') else None,
            video_path=str(result.path),
            audio_path=str(audio_path),
        )

        await send_sse_event("video", video_id, "status", {"status": "completed", "title": result.title})
        await send_sse_event("video", video_id, "done", {})

        logger.info("视频下载完成: %s - %s", video_id, result.title)

    except DownloadError as e:
        logger.warning("视频下载失败: %s - %s", video_id, e)
        await send_sse_event("video", video_id, "error", {"detail": f"下载失败: {e}"})
    except Exception as e:
        logger.exception("视频下载异常: %s", video_id)
        await send_sse_event("video", video_id, "error", {"detail": f"处理失败: {e}"})


async def process_transcript(transcript_id: str, video: Video):
    """后台任务：转录音频"""
    logger.info("开始转录: %s", transcript_id)

    try:
        await update_transcript(transcript_id, status="processing")
        await send_sse_event("transcript", transcript_id, "status", {"status": "processing", "progress": "开始转录..."})

        if not video.audio_path:
            raise TranscribeError("音频文件不存在")

        audio_path = Path(video.audio_path)
        if not audio_path.exists():
            raise TranscribeError("音频文件不存在")

        # 转录
        await send_sse_event("transcript", transcript_id, "status", {"status": "processing", "progress": "转录中..."})
        content = await transcribe_audio(audio_path)

        # 更新数据库
        await update_transcript(transcript_id, status="completed", content=content)

        await send_sse_event("transcript", transcript_id, "status", {"status": "completed"})
        await send_sse_event("transcript", transcript_id, "done", {})

        logger.info("转录完成: %s", transcript_id)

    except TranscribeError as e:
        logger.warning("转录失败: %s - %s", transcript_id, e)
        await send_sse_event("transcript", transcript_id, "error", {"detail": f"转录失败: {e}"})
    except Exception as e:
        logger.exception("转录异常: %s", transcript_id)
        await send_sse_event("transcript", transcript_id, "error", {"detail": f"处理失败: {e}"})


async def process_outline(outline_id: str, transcript_content: str):
    """后台任务：生成大纲"""
    logger.info("开始生成大纲: %s", outline_id)

    try:
        await update_outline(outline_id, status="processing")
        await send_sse_event("outline", outline_id, "status", {"status": "processing", "progress": "生成大纲中..."})

        # 生成大纲
        content = await ai_generate_outline(transcript_content)

        if not content or len(content.strip()) < 50:
            raise GitCodeAIError("生成的大纲内容过短")

        # 更新数据库
        await update_outline(outline_id, status="completed", content=content)

        await send_sse_event("outline", outline_id, "status", {"status": "completed"})
        await send_sse_event("outline", outline_id, "done", {})

        logger.info("大纲生成完成: %s", outline_id)

    except GitCodeAIError as e:
        logger.warning("大纲生成失败: %s - %s", outline_id, e)
        await send_sse_event("outline", outline_id, "error", {"detail": f"生成失败: {e}"})
    except Exception as e:
        logger.exception("大纲生成异常: %s", outline_id)
        await send_sse_event("outline", outline_id, "error", {"detail": f"处理失败: {e}"})


async def process_article(article_id: str, transcript_content: str):
    """后台任务：生成文章"""
    logger.info("开始生成文章: %s", article_id)

    try:
        await update_article(article_id, status="processing")
        await send_sse_event("article", article_id, "status", {"status": "processing", "progress": "生成文章中..."})

        # 生成文章
        content = await ai_generate_article(transcript_content)

        if not content or len(content.strip()) < 50:
            raise GitCodeAIError("生成的文章内容过短")

        # 更新数据库
        await update_article(article_id, status="completed", content=content)

        await send_sse_event("article", article_id, "status", {"status": "completed"})
        await send_sse_event("article", article_id, "done", {})

        logger.info("文章生成完成: %s", article_id)

    except GitCodeAIError as e:
        logger.warning("文章生成失败: %s - %s", article_id, e)
        await send_sse_event("article", article_id, "error", {"detail": f"生成失败: {e}"})
    except Exception as e:
        logger.exception("文章生成异常: %s", article_id)
        await send_sse_event("article", article_id, "error", {"detail": f"处理失败: {e}"})


# ============ Frontend ============

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
