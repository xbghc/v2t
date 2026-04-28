"""DashScope Paraformer 切片伪流式 Provider

注：DashScope paraformer-realtime-v2 本身基于 WebSocket，原生支持流式（帧推送 + 增量回调）。
当前实现走切片 + 整文件 SDK call 的伪流式路径，与 Whisper 行为一致；
未来若要切到原生流式，替换本文件即可，对外 API 不变。
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from http import HTTPStatus

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from app.config import get_settings
from app.services.dashscope_stt import check_dashscope_stt
from app.services.transcribe import TranscribeError

from ._pool import concurrent_transcribe_chunks
from .base import AudioChunk, TranscribeContext, TranscriptSegment

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 4


class _NoopCallback(RecognitionCallback):
    """Recognition 要求 callback；同步 .call() 不会用到"""

    def on_event(self, result):
        pass

    def on_error(self, result):
        pass


class DashScopeProvider:
    """切片 + 阿里云 Paraformer 同步整文件识别"""

    name = "dashscope"

    # paraformer 长录音离线接口可处理多小时音频，阿里云配额按调用付费，无单次时长上限
    max_audio_duration: int | None = None

    def __init__(self, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        self.max_concurrency = max_concurrency

    async def is_available(self) -> tuple[bool, str]:
        return await check_dashscope_stt()

    async def transcribe_stream(
        self,
        chunks: AsyncIterator[AudioChunk],
        context: TranscribeContext,
    ) -> AsyncIterator[TranscriptSegment]:
        async def _transcribe_one(chunk: AudioChunk) -> list[TranscriptSegment]:
            return await asyncio.to_thread(
                _call_recognition, chunk, context.language
            )

        async for seg in concurrent_transcribe_chunks(
            chunks, _transcribe_one, max_concurrency=self.max_concurrency
        ):
            yield seg


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
