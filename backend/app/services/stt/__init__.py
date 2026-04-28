"""STT 流式转录统一入口

调用方只关心：
    async for seg in transcribe_stream(chunks, language=...):
        ...

具体走哪个 Provider 由 select_provider 决定（按配置回退）。
"""

from collections.abc import AsyncIterator

from app.config import get_settings
from app.services.transcribe import TranscribeError

from .base import (
    AudioChunk,
    STTProvider,
    TranscribeContext,
    TranscriptSegment,
)


def _candidates() -> list[STTProvider]:
    """按配置优先级返回 Provider 候选列表

    顺序：
        1. Whisper 兼容（OPENAI/Groq/自托管 Qwen3-ASR 等，配置 WHISPER_*）
        2. DashScope（DASHSCOPE_API_KEY）
    """
    settings = get_settings()
    out: list[STTProvider] = []
    if settings.whisper_api_key and settings.whisper_base_url:
        from .whisper import WhisperProvider

        out.append(WhisperProvider())
    if settings.dashscope_api_key:
        from .dashscope import DashScopeProvider

        out.append(DashScopeProvider())
    return out


def select_provider(audio_duration: int | None = None) -> STTProvider:
    """按配置优先级 + 时长能力路由 Provider

    audio_duration（秒）非空时按 first-fit：从优先级高到低找首个能容纳的 Provider；
    都装不下时抛 TranscribeError。这是防止长视频打到 Groq free 等限额端点的核心闸门。

    audio_duration 为 None 时退化为旧行为：返回首个可用 Provider。
    """
    candidates = _candidates()
    if not candidates:
        raise TranscribeError(
            "未配置任何 STT provider：请设置 WHISPER_* 或 DASHSCOPE_API_KEY"
        )

    if audio_duration is None:
        return candidates[0]

    for p in candidates:
        cap = p.max_audio_duration
        if cap is None or audio_duration <= cap:
            return p

    caps = ", ".join(
        f"{p.name}={p.max_audio_duration // 60}min"
        if p.max_audio_duration
        else f"{p.name}=∞"
        for p in candidates
    )
    raise TranscribeError(
        f"音频时长 {audio_duration // 60}min 超过所有 STT provider 上限（{caps}）"
    )


async def transcribe_stream(
    chunks: AsyncIterator[AudioChunk],
    language: str | None = None,
    audio_duration: int | None = None,
) -> AsyncIterator[TranscriptSegment]:
    """统一的流式转录入口

    Args:
        chunks: 音频切片异步迭代器
        language: 语言提示，None 为自动
        audio_duration: 音频总时长（秒），用于按 Provider 能力路由；
            None 时不做时长路由，返回首个可用 Provider

    Yields:
        TranscriptSegment: 按时间顺序的转录段（已做绝对时间重映射）
    """
    provider = select_provider(audio_duration)
    context = TranscribeContext(language=language)
    async for seg in provider.transcribe_stream(chunks, context):
        yield seg


__all__ = [
    "AudioChunk",
    "STTProvider",
    "TranscribeContext",
    "TranscribeError",
    "TranscriptSegment",
    "select_provider",
    "transcribe_stream",
]
