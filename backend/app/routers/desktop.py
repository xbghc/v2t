"""桌面端服务路由。

⚠️ 安全注意：阶段一不加鉴权，所有人都能匿名调用消耗后端配额。
生产前必须接入 Email OTP / OAuth 等用户身份验证，否则会沦为公开的
DashScope 调用代理。
"""

import logging
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import get_settings
from app.services.transcribe import TranscribeError, transcribe_audio
from app.services.xiazaitool import XiazaitoolError, parse_video_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/desktop", tags=["desktop"])

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com"

# 上游链接超时较短，整体超时给到 5 分钟覆盖大文件转录
_PROXY_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=300.0, pool=10.0)

# 不向上游透传的 hop-by-hop / 客户端专属 header
_HOP_BY_HOP_HEADERS = frozenset(
    {
        "host",
        "authorization",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


def _filter_request_headers(request: Request, bearer_token: str) -> dict[str, str]:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP_HEADERS
    }
    headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


def _filter_response_headers(upstream: httpx.Response) -> dict[str, str]:
    return {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP_HEADERS
    }


async def _proxy_post(
    request: Request,
    target_url: str,
    bearer_token: str,
) -> Response:
    headers = _filter_request_headers(request, bearer_token)
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=_PROXY_TIMEOUT) as client:
            upstream = await client.post(
                target_url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
    except httpx.HTTPError as e:
        logger.warning("透传到 %s 失败: %s", target_url, e)
        raise HTTPException(status_code=502, detail=f"上游连接失败: {e}")

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_filter_response_headers(upstream),
        media_type=upstream.headers.get("content-type"),
    )


class TranscribeResponse(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(None),
) -> TranscribeResponse:
    """统一转录端点。后端按已配置的 STT 引擎选择（Whisper 优先，否则 DashScope）。

    桌面端不感知具体提供商，只需 multipart 上传音频文件。
    """
    settings = get_settings()
    suffix = Path(file.filename or "audio").suffix or ".mp3"

    with tempfile.NamedTemporaryFile(
        suffix=suffix, dir=settings.temp_path, delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)

    try:
        text = await transcribe_audio(tmp_path, language=language)
        return TranscribeResponse(text=text)
    except TranscribeError as e:
        logger.warning("desktop /transcribe 失败: %s", e)
        raise HTTPException(status_code=502, detail=f"转录失败: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/dashscope/{path:path}")
async def dashscope_proxy(path: str, request: Request) -> Response:
    """透传任意 path 到 DashScope（阿里云百炼）。"""
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise HTTPException(status_code=503, detail="DashScope API 未配置")

    target = f"{DASHSCOPE_BASE}/{path}"
    return await _proxy_post(request, target, settings.dashscope_api_key)


class ParseVideoRequest(BaseModel):
    url: str


class ParseVideoResponse(BaseModel):
    direct_url: str
    title: str
    duration: float | None = None
    thumbnail: str | None = None


@router.post("/parse-video", response_model=ParseVideoResponse)
async def parse_video(body: ParseVideoRequest) -> ParseVideoResponse:
    """解析视频链接拿到直链。仅返回标准化字段，不创建 workspace。"""
    try:
        info = await parse_video_url(body.url)
    except XiazaitoolError as e:
        logger.warning("parse-video 失败: %s", e)
        raise HTTPException(status_code=502, detail=f"解析失败: {e}")

    if not info.video_url:
        raise HTTPException(status_code=422, detail="链接未返回视频直链（可能是图文内容）")

    return ParseVideoResponse(
        direct_url=info.video_url,
        title=info.title,
        thumbnail=info.cover_url or None,
    )
