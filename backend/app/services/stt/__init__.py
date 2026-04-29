"""STT 流式转录统一入口

调用方只关心：
    async for seg in transcribe_stream(chunks, language=...):
        ...

具体走哪个 provider 由 ProviderRouter 决定（按配置优先级 + 健康状态动态切换）。
撞限流的 provider 自动进入 cooldown，期满恢复。
"""

from collections.abc import AsyncIterator

from app.services.transcribe import TranscribeError

from .base import (
    AudioChunk,
    ProviderRateLimited,
    STTProvider,
    TranscribeContext,
    TranscriptSegment,
)
from .router import ProviderRouter, get_router, reset_router


async def transcribe_stream(
    chunks: AsyncIterator[AudioChunk],
    language: str | None = None,
) -> AsyncIterator[TranscriptSegment]:
    """统一的流式转录入口

    Args:
        chunks: 音频切片异步迭代器
        language: 语言提示，None 为自动

    Yields:
        TranscriptSegment: 按时间顺序的转录段（已做绝对时间重映射）
    """
    router = get_router()
    context = TranscribeContext(language=language)
    async for seg in router.transcribe_stream(chunks, context):
        yield seg


__all__ = [
    "AudioChunk",
    "ProviderRateLimited",
    "ProviderRouter",
    "STTProvider",
    "TranscribeContext",
    "TranscribeError",
    "TranscriptSegment",
    "get_router",
    "reset_router",
    "transcribe_stream",
]
