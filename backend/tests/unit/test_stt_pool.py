"""验证 concurrent_transcribe_chunks 的关键不变量：
1. 输出顺序 = chunk 入队顺序，即使后到的 chunk 更快完成
2. 并发度受 max_concurrency 限制
3. 单 chunk 失败会让整个流抛错
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.services.stt._pool import concurrent_transcribe_chunks
from app.services.stt.base import AudioChunk, TranscriptSegment


def _mk_chunk(i: int, total: int) -> AudioChunk:
    return AudioChunk(
        path=Path("/tmp/dummy.mp3"),
        index=i,
        start=float(i * 30),
        end=float((i + 1) * 30),
        is_last=(i == total - 1),
    )


async def _chunks_iter(n: int) -> AsyncIterator[AudioChunk]:
    for i in range(n):
        yield _mk_chunk(i, n)


@pytest.mark.asyncio
async def test_preserves_order_when_first_is_slowest():
    """chunk 0 慢、chunk 1/2 快 → yield 仍是 0,1,2"""
    delays = {0: 0.20, 1: 0.02, 2: 0.02}

    async def transcribe_one(c: AudioChunk):
        await asyncio.sleep(delays[c.index])
        return [TranscriptSegment(
            start=c.start, end=c.end, text=f"c{c.index}", chunk_index=c.index,
        )]

    indices = []
    async for s in concurrent_transcribe_chunks(
        _chunks_iter(3), transcribe_one, max_concurrency=4
    ):
        indices.append(s.chunk_index)

    assert indices == [0, 1, 2]


@pytest.mark.asyncio
async def test_concurrency_limit_respected():
    """max_concurrency=2 → 同时在跑的 task 不超过 2"""
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def transcribe_one(c: AudioChunk):
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return [TranscriptSegment(
            start=c.start, end=c.end, text="x", chunk_index=c.index,
        )]

    async for _ in concurrent_transcribe_chunks(
        _chunks_iter(8), transcribe_one, max_concurrency=2
    ):
        pass

    assert peak <= 2


@pytest.mark.asyncio
async def test_failure_in_single_chunk_propagates():
    """某个 chunk 抛错应让整个流冒泡"""

    async def transcribe_one(c: AudioChunk):
        if c.index == 1:
            raise RuntimeError("boom")
        return [TranscriptSegment(
            start=c.start, end=c.end, text="ok", chunk_index=c.index,
        )]

    with pytest.raises(RuntimeError, match="boom"):
        async for _ in concurrent_transcribe_chunks(
            _chunks_iter(3), transcribe_one, max_concurrency=4
        ):
            pass
