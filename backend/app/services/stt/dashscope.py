"""DashScope Paraformer 单 chunk Provider

注：DashScope paraformer-realtime-v2 本身基于 WebSocket，原生支持流式。
当前实现走整文件 SDK call 的伪流式路径（与 Whisper 行为一致），
未来切原生流式只需替换本文件，对外 API 不变。

并发与 fallback 由 router 控制；本 provider 只转录单 chunk，
撞 HTTP 429 时抛 ProviderRateLimited（默认 60s cooldown，
DashScope SDK 不暴露 Retry-After header）。
"""

import asyncio
import logging
from http import HTTPStatus

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from app.config import get_settings
from app.services.dashscope_stt import check_dashscope_stt
from app.services.transcribe import TranscribeError

from .base import (
    AudioChunk,
    ProviderRateLimited,
    TranscribeContext,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_COOLDOWN = 60.0  # DashScope SDK 不暴露 Retry-After，统一用 60s


class _NoopCallback(RecognitionCallback):
    """Recognition 要求 callback；同步 .call() 不会用到"""

    def on_event(self, result):
        pass

    def on_error(self, result):
        pass


class DashScopeProvider:
    """阿里云 Paraformer 同步整文件识别 — 单 chunk 接口"""

    name = "dashscope"

    async def is_available(self) -> tuple[bool, str]:
        return await check_dashscope_stt()

    async def transcribe_chunk(
        self,
        chunk: AudioChunk,
        context: TranscribeContext,
    ) -> list[TranscriptSegment]:
        return await asyncio.to_thread(_call_recognition, chunk, context.language)


def _call_recognition(
    chunk: AudioChunk, language: str | None
) -> list[TranscriptSegment]:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise TranscribeError("DASHSCOPE_API_KEY 未配置")

    dashscope.api_key = settings.dashscope_api_key

    audio_format = chunk.path.suffix.lstrip(".")
    language_hints = [language] if language else ["zh", "en"]

    recognition = Recognition(
        model=settings.dashscope_stt_model,
        callback=_NoopCallback(),
        format=audio_format,
        sample_rate=16000,
        language_hints=language_hints,
    )
    result = recognition.call(str(chunk.path))

    if result.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        raise ProviderRateLimited(
            retry_after=RATE_LIMIT_COOLDOWN,
            provider_name="dashscope",
        )
    if result.status_code != HTTPStatus.OK:
        raise TranscribeError(
            f"DashScope STT 失败 (HTTP {result.status_code}): {result.message}"
        )

    sentences = result.get_sentence() or []
    if isinstance(sentences, dict):
        sentences = [sentences]

    out: list[TranscriptSegment] = []
    for sent in sentences:
        text = (sent.get("text") or "").strip()
        if not text:
            continue
        rel_start = (sent.get("begin_time") or 0) / 1000.0
        rel_end = (sent.get("end_time") or 0) / 1000.0
        if rel_end < rel_start:
            rel_end = rel_start
        out.append(
            TranscriptSegment(
                start=chunk.start + rel_start,
                end=chunk.start + rel_end,
                text=text,
                chunk_index=chunk.index,
            )
        )
    return out
