"""切片伪流式的共享并发执行框架

供 Whisper / DashScope 等无原生流式 API 的 Provider 复用。
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from .base import AudioChunk, TranscriptSegment

logger = logging.getLogger(__name__)

ChunkTranscriber = Callable[[AudioChunk], Awaitable[list[TranscriptSegment]]]


async def concurrent_transcribe_chunks(
    chunks: AsyncIterator[AudioChunk],
    transcribe_one: ChunkTranscriber,
    max_concurrency: int = 4,
) -> AsyncIterator[TranscriptSegment]:
    """对切片流做受限并发转录，按 chunk 到达顺序 yield 结果

    设计：
        - feeder 协程按到达顺序读取 chunks 并启动转录 task（受 semaphore 限制）
        - 主循环按入队顺序 await 每个 task → 保证输出顺序与 chunk index 一致
        - 单 task 失败会让整个流中止，feeder 与未完成 tasks 全部取消
    """
    sem = asyncio.Semaphore(max_concurrency)
    queue: asyncio.Queue[asyncio.Task[list[TranscriptSegment]] | None] = asyncio.Queue()

    async def _run_one(chunk: AudioChunk) -> list[TranscriptSegment]:
        async with sem:
            logger.debug("转录切片 %d 启动", chunk.index)
            segs = await transcribe_one(chunk)
            logger.debug("转录切片 %d 完成（%d 段）", chunk.index, len(segs))
            return segs

    async def feeder() -> None:
        try:
            async for chunk in chunks:
                task = asyncio.create_task(
                    _run_one(chunk), name=f"transcribe_chunk_{chunk.index}"
                )
                await queue.put(task)
        finally:
            await queue.put(None)

    feeder_task = asyncio.create_task(feeder(), name="stt_chunks_feeder")
    pending_tasks: list[asyncio.Task] = []

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            pending_tasks.append(item)
            try:
                segs = await item
            except Exception:
                raise
            pending_tasks.remove(item)
            for seg in segs:
                yield seg
    finally:
        feeder_task.cancel()
        await asyncio.gather(feeder_task, return_exceptions=True)
        while True:
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item is not None:
                pending_tasks.append(item)
        for t in pending_tasks:
            if not t.done():
                t.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
