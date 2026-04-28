"""Whisper / OpenAI 兼容 API（含 Groq、自托管 Qwen3-ASR）的切片伪流式 Provider"""

import logging
from collections.abc import AsyncIterator

from app.services.transcribe import (
    _transcribe_audio_whisper_raw,
    check_whisper_api,
)

from ._pool import concurrent_transcribe_chunks
from .base import AudioChunk, TranscribeContext, TranscriptSegment

# TranscribeError 直接复用 transcribe.py 的定义（在 _transcribe_audio_whisper_raw 中抛出）

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 4


class WhisperProvider:
    """切片 + 并发 HTTP API 调用（伪流式）"""

    name = "whisper"

    # 1h 软上限：Groq free 等限额端点 RPM/quota 保护；自托管 Qwen3-ASR 等可在
    # 配置层覆盖。超过此值的音频会路由到下一个 candidate（DashScope）或拒绝。
    max_audio_duration: int | None = 3600

    def __init__(self, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        self.max_concurrency = max_concurrency

    async def is_available(self) -> tuple[bool, str]:
        return await check_whisper_api()

    async def transcribe_stream(
        self,
        chunks: AsyncIterator[AudioChunk],
        context: TranscribeContext,
    ) -> AsyncIterator[TranscriptSegment]:
        async def _transcribe_one(chunk: AudioChunk) -> list[TranscriptSegment]:
            response = await _transcribe_audio_whisper_raw(
                chunk.path, context.language
            )
            return _response_to_segments(response, chunk)

        async for seg in concurrent_transcribe_chunks(
            chunks, _transcribe_one, max_concurrency=self.max_concurrency
        ):
            yield seg


def _response_to_segments(response, chunk: AudioChunk) -> list[TranscriptSegment]:
    """把 Whisper verbose_json 响应转换为绝对时间戳的 TranscriptSegment"""
    segments_attr = getattr(response, "segments", None)
    if segments_attr:
        results: list[TranscriptSegment] = []
        for s in segments_attr:
            text = (getattr(s, "text", None) or "").strip()
            if not text:
                continue
            rel_start = float(getattr(s, "start", 0.0) or 0.0)
            rel_end = float(getattr(s, "end", rel_start) or rel_start)
            results.append(
                TranscriptSegment(
                    start=chunk.start + rel_start,
                    end=chunk.start + rel_end,
                    text=text,
                    chunk_index=chunk.index,
                )
            )
        if results:
            return results

    text = (getattr(response, "text", None) or "").strip()
    if text:
        return [
            TranscriptSegment(
                start=chunk.start,
                end=chunk.end,
                text=text,
                chunk_index=chunk.index,
            )
        ]
    return []
