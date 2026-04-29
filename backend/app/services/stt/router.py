"""STT Provider Router — 优先级链 + circuit breaker

设计语义：
    - providers 按优先级排序，越前越优先
    - 任意 chunk 撞 ProviderRateLimited → 该 provider 进入 cooldown N 秒，
      Router 立刻把这个 chunk 转给链中下一个可用的 provider
    - cooldown 过期后 provider 自动恢复，新 chunk 优先回到它
    - 所有 provider 都 cooldown / 不可用时抛 TranscribeError 中止整个流
    - 状态保留在进程内（每个 worker 各自学习），不跨进程共享
"""

import logging
import time
from collections.abc import AsyncIterator

from app.services.transcribe import TranscribeError

from ._pool import concurrent_transcribe_chunks
from .base import (
    AudioChunk,
    ProviderRateLimited,
    STTProvider,
    TranscribeContext,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 4


class ProviderRouter:
    """按优先级在多 STT provider 间路由，单 chunk 撞限自动切换

    线程安全：cooldown dict 仅在 asyncio 单事件循环内读写（无跨线程共享）。
    """

    def __init__(self, providers: list[STTProvider]) -> None:
        self._providers = providers
        self._cooldown_until: dict[str, float] = {}

    def pick_available(self) -> STTProvider | None:
        """按优先级返回首个可用 provider；全 cooldown 返回 None"""
        for p in self._providers:
            if self._is_available(p):
                return p
        return None

    def mark_cooldown(self, provider_name: str, retry_after: float) -> None:
        """标记 provider 在 retry_after 秒内不可用"""
        until = time.monotonic() + retry_after
        # 已在 cooldown 时取较晚的 deadline（避免缩短）
        existing = self._cooldown_until.get(provider_name)
        if existing is None or until > existing:
            self._cooldown_until[provider_name] = until
        logger.info(
            "STT provider %s 进入 cooldown，%.1fs 后恢复",
            provider_name, retry_after,
        )

    def _is_available(self, provider: STTProvider) -> bool:
        until = self._cooldown_until.get(provider.name)
        if until is None:
            return True
        if time.monotonic() >= until:
            del self._cooldown_until[provider.name]
            logger.info("STT provider %s cooldown 期满，恢复可用", provider.name)
            return True
        return False

    async def transcribe_stream(
        self,
        chunks: AsyncIterator[AudioChunk],
        context: TranscribeContext,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> AsyncIterator[TranscriptSegment]:
        """流式转录：单 chunk 失败时按链切换 provider

        Raises:
            TranscribeError: 未配置任何 provider，或当前 chunk 触达所有 provider 后仍失败
        """
        if not self._providers:
            raise TranscribeError(
                "未配置任何 STT provider：请设置 WHISPER_* 或 DASHSCOPE_API_KEY"
            )

        async def _transcribe_one_with_fallback(
            chunk: AudioChunk,
        ) -> list[TranscriptSegment]:
            attempted: set[str] = set()
            while True:
                provider = self.pick_available()
                if provider is None:
                    raise TranscribeError(
                        "所有 STT provider 都 rate-limited 或不可用"
                    )
                if provider.name in attempted:
                    # 同一 chunk 在 cooldown 间隙又拿到刚被 mark 的 provider —
                    # 防止本地循环，让该 chunk 失败、整个流中止
                    raise TranscribeError(
                        f"STT provider {provider.name} 反复触发限流，本片放弃"
                    )
                attempted.add(provider.name)
                try:
                    return await provider.transcribe_chunk(chunk, context)
                except ProviderRateLimited as e:
                    self.mark_cooldown(provider.name, e.retry_after)
                    continue

        async for seg in concurrent_transcribe_chunks(
            chunks,
            _transcribe_one_with_fallback,
            max_concurrency=max_concurrency,
        ):
            yield seg


# ============ singleton ============

_router: ProviderRouter | None = None


def get_router() -> ProviderRouter:
    """模块级 singleton；首次调用按当前配置构建链"""
    global _router
    if _router is None:
        _router = ProviderRouter(_build_candidates())
    return _router


def reset_router() -> None:
    """测试用：清掉 singleton 让下次 get_router 重建"""
    global _router
    _router = None


def _build_candidates() -> list[STTProvider]:
    """按配置优先级构建 provider 列表

    顺序：
        1. Whisper 兼容（OpenAI/Groq/自托管 Qwen3-ASR 等，配置 WHISPER_*）
        2. DashScope（DASHSCOPE_API_KEY）
    """
    from app.config import get_settings

    settings = get_settings()
    out: list[STTProvider] = []
    if settings.whisper_api_key and settings.whisper_base_url:
        from .whisper import WhisperProvider

        out.append(WhisperProvider())
    if settings.dashscope_api_key:
        from .dashscope import DashScopeProvider

        out.append(DashScopeProvider())
    return out
