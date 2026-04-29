"""Whisper / OpenAI 兼容 API（含 Groq、自托管 Qwen3-ASR）的单 chunk Provider

并发与 fallback 由 router 控制；本 provider 只负责转录单个切片，
撞 RateLimitError 时把 retry-after 转译为 ProviderRateLimited 抛给 router。
"""

import logging

import openai

from app.services.transcribe import (
    _transcribe_audio_whisper_raw,
    check_whisper_api,
)

from .base import (
    AudioChunk,
    ProviderRateLimited,
    TranscribeContext,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_COOLDOWN = 60.0  # retry-after 缺失时的兜底 cooldown


class WhisperProvider:
    """OpenAI/Groq/Qwen3-ASR 等 Whisper 兼容端点 — 单 chunk HTTP 调用"""

    name = "whisper"

    async def is_available(self) -> tuple[bool, str]:
        return await check_whisper_api()

    async def transcribe_chunk(
        self,
        chunk: AudioChunk,
        context: TranscribeContext,
    ) -> list[TranscriptSegment]:
        try:
            response = await _transcribe_audio_whisper_raw(
                chunk.path, context.language
            )
        except openai.RateLimitError as e:
            raise ProviderRateLimited(
                retry_after=_extract_retry_after(e),
                provider_name=self.name,
            ) from e
        return _response_to_segments(response, chunk)


def _extract_retry_after(error: openai.RateLimitError) -> float:
    """从 RateLimitError 拿 Retry-After header；缺失时用兜底"""
    response = getattr(error, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None) or {}
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
    return DEFAULT_RATE_LIMIT_COOLDOWN


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
