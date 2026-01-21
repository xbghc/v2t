"""SSE (Server-Sent Events) 辅助函数"""

import json
from collections.abc import AsyncIterable, Callable
from typing import Any

from fastapi.responses import StreamingResponse


def sse_data(data: dict[str, Any]) -> str:
    """将数据格式化为 SSE 数据行"""
    return f"data: {json.dumps(data)}\n\n"


def sse_heartbeat() -> str:
    """生成 SSE 心跳"""
    return ": heartbeat\n\n"


def sse_response(
    generator: Callable[[], AsyncIterable[str]],
) -> StreamingResponse:
    """创建 SSE 响应"""
    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
