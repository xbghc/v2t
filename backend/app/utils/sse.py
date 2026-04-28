"""SSE (Server-Sent Events) 辅助函数"""

import asyncio
import json
import logging
from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Any

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


def sse_data(data: dict[str, Any]) -> str:
    """将数据格式化为 SSE 数据行"""
    return f"data: {json.dumps(data)}\n\n"


def sse_heartbeat() -> str:
    """生成 SSE 心跳（comment line，前端 onmessage 不会触发）"""
    return ": heartbeat\n\n"


async def _with_heartbeat(
    inner: AsyncIterator[str], interval: float
) -> AsyncIterator[str]:
    """包装 SSE generator：长时间无 yield 时自动插入心跳保连接。

    场景：LLM thinking 阶段无 TextEvent 输出，业务 generator 不 yield
    任何 SSE data 行；nginx (proxy_read_timeout 默认 60s) 或浏览器可能
    误判超时断连。心跳是 SSE comment，不触发前端 onmessage。

    inner 抛出的异常会原样向上传播。
    """
    q: asyncio.Queue = asyncio.Queue()
    sentinel = object()
    error_holder: list[BaseException] = []

    async def feed() -> None:
        try:
            async for chunk in inner:
                await q.put(chunk)
        except BaseException as e:
            error_holder.append(e)
        finally:
            await q.put(sentinel)

    feed_task = asyncio.create_task(feed())
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=interval)
            except TimeoutError:
                yield sse_heartbeat()
                continue
            if item is sentinel:
                if error_holder:
                    raise error_holder[0]
                return
            yield item
    finally:
        if not feed_task.done():
            feed_task.cancel()
            try:
                await feed_task
            except (asyncio.CancelledError, Exception):
                pass


def sse_response(
    generator: Callable[[], AsyncIterable[str]],
    heartbeat_interval: float = 15.0,
) -> StreamingResponse:
    """创建 SSE 响应。

    heartbeat_interval：业务 generator 多久无 yield 时插入一次心跳保活。
    设 0 或负数关闭心跳。
    """
    async def wrapped() -> AsyncIterator[str]:
        if heartbeat_interval > 0:
            async for chunk in _with_heartbeat(
                _aiter(generator()), heartbeat_interval,
            ):
                yield chunk
        else:
            async for chunk in _aiter(generator()):
                yield chunk

    return StreamingResponse(
        wrapped(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _aiter(it: AsyncIterable[str]) -> AsyncIterator[str]:
    """AsyncIterable → AsyncIterator（generator 写法兼容）"""
    async for x in it:
        yield x
