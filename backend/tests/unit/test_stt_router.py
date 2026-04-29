"""ProviderRouter 的关键不变量：
1. 正常路径 → 走优先级最高的 provider
2. 单 provider 撞 ProviderRateLimited → 切链中下一个；后续 chunks 也走 fallback
3. 全部 cooldown → 抛 TranscribeError 中止流
4. 未配置 provider → 抛 TranscribeError
5. mark_cooldown 取较晚的 deadline 不缩短现有 cooldown
6. attempted set 防同一 chunk 反复在 cooldown 间隙撞同一 provider
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.services.stt.base import (
    AudioChunk,
    ProviderRateLimited,
    TranscribeContext,
    TranscriptSegment,
)
from app.services.stt.router import ProviderRouter
from app.services.transcribe import TranscribeError


class _RecordingProvider:
    """记录每次调用 chunk index 的假 provider，可注入失败行为"""

    def __init__(self, name: str, behavior=None) -> None:
        self.name = name
        self.calls: list[int] = []
        self._behavior = behavior

    async def is_available(self) -> tuple[bool, str]:
        return True, "OK"

    async def transcribe_chunk(
        self, chunk: AudioChunk, context: TranscribeContext
    ) -> list[TranscriptSegment]:
        self.calls.append(chunk.index)
        if self._behavior is not None:
            result = self._behavior(chunk, len(self.calls))
            if isinstance(result, BaseException):
                raise result
            return result
        return [
            TranscriptSegment(
                start=chunk.start, end=chunk.end,
                text=f"{self.name}-{chunk.index}",
                chunk_index=chunk.index,
            )
        ]


def _mk_chunk(i: int) -> AudioChunk:
    return AudioChunk(
        path=Path("/tmp/dummy.mp3"),
        index=i, start=float(i * 30), end=float((i + 1) * 30),
    )


async def _chunks_iter(chunks: list[AudioChunk]) -> AsyncIterator[AudioChunk]:
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_normal_path_uses_highest_priority_provider():
    """两个 provider 都健康 → 全走第一个，第二个零调用"""
    a = _RecordingProvider("a")
    b = _RecordingProvider("b")
    router = ProviderRouter([a, b])

    segs = [
        s
        async for s in router.transcribe_stream(
            _chunks_iter([_mk_chunk(0), _mk_chunk(1)]),
            TranscribeContext(),
            max_concurrency=1,
        )
    ]

    assert [s.text for s in segs] == ["a-0", "a-1"]
    assert a.calls == [0, 1]
    assert b.calls == []


@pytest.mark.asyncio
async def test_rate_limited_provider_falls_back_to_next():
    """a 第一次调用撞限 → 切 b；后续 chunks 也走 b（a 在 cooldown 中）"""

    def a_behavior(chunk: AudioChunk, attempt_count: int):
        if attempt_count == 1:
            return ProviderRateLimited(retry_after=999, provider_name="a")
        # 不会到这里，因为撞限后 a 永远 cooldown
        return []

    a = _RecordingProvider("a", a_behavior)
    b = _RecordingProvider("b")
    router = ProviderRouter([a, b])

    segs = [
        s
        async for s in router.transcribe_stream(
            _chunks_iter([_mk_chunk(0), _mk_chunk(1)]),
            TranscribeContext(),
            max_concurrency=1,
        )
    ]

    assert [s.text for s in segs] == ["b-0", "b-1"]
    assert a.calls == [0]      # a 只被试了 chunk 0
    assert b.calls == [0, 1]   # b 接管了 chunk 0（fallback）和 chunk 1（cooldown 中 a 跳过）


@pytest.mark.asyncio
async def test_all_providers_rate_limited_raises():
    """两个 provider 都撞限 → router 中止整个流"""

    def fail_with_rate_limit(name: str):
        def behavior(chunk, attempt_count):
            return ProviderRateLimited(retry_after=999, provider_name=name)
        return behavior

    a = _RecordingProvider("a", fail_with_rate_limit("a"))
    b = _RecordingProvider("b", fail_with_rate_limit("b"))
    router = ProviderRouter([a, b])

    with pytest.raises(TranscribeError, match="rate-limited|不可用"):
        async for _ in router.transcribe_stream(
            _chunks_iter([_mk_chunk(0)]),
            TranscribeContext(),
            max_concurrency=1,
        ):
            pass


@pytest.mark.asyncio
async def test_empty_provider_list_raises():
    """未配置任何 provider → 立刻抛 TranscribeError"""
    router = ProviderRouter([])

    with pytest.raises(TranscribeError, match="未配置任何 STT provider"):
        async for _ in router.transcribe_stream(
            _chunks_iter([_mk_chunk(0)]),
            TranscribeContext(),
        ):
            pass


@pytest.mark.asyncio
async def test_non_rate_limit_error_propagates():
    """非 ProviderRateLimited 异常 → 不切 fallback，整个流冒泡中止"""

    def boom(chunk, attempt_count):
        return RuntimeError(f"boom on {chunk.index}")

    a = _RecordingProvider("a", boom)
    b = _RecordingProvider("b")
    router = ProviderRouter([a, b])

    with pytest.raises(RuntimeError, match="boom"):
        async for _ in router.transcribe_stream(
            _chunks_iter([_mk_chunk(0), _mk_chunk(1)]),
            TranscribeContext(),
            max_concurrency=1,
        ):
            pass

    assert a.calls == [0]
    assert b.calls == []  # 非限流错误不切 fallback


def test_mark_cooldown_takes_later_deadline():
    """同 provider 短 cooldown 后再长 cooldown → 取较晚的；反向不缩短"""
    router = ProviderRouter([])

    router.mark_cooldown("x", 1.0)
    short_until = router._cooldown_until["x"]

    router.mark_cooldown("x", 60.0)
    long_until = router._cooldown_until["x"]
    assert long_until > short_until

    # 长 cooldown 后再短 cooldown 不应缩短
    router.mark_cooldown("x", 0.5)
    assert router._cooldown_until["x"] == long_until


def test_pick_available_skips_cooldown():
    """cooldown 中的 provider 被跳过；按优先级返回首个可用的"""
    a = _RecordingProvider("a")
    b = _RecordingProvider("b")
    c = _RecordingProvider("c")
    router = ProviderRouter([a, b, c])

    assert router.pick_available() is a

    router.mark_cooldown("a", 999)
    assert router.pick_available() is b

    router.mark_cooldown("b", 999)
    assert router.pick_available() is c

    router.mark_cooldown("c", 999)
    assert router.pick_available() is None
