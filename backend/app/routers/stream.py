"""生成任务的启动与消费端点

设计：把"启动生成"和"订阅 SSE"拆成两个独立端点。
  - POST /api/workspaces/{ws_id}/stream/{type}      启动（幂等），返回 task_id
  - GET  /api/workspaces/{ws_id}/generations/{task_id}/stream  消费 SSE

worker 在后台跑 LLM、写 Redis Stream，不依赖任何 HTTP 连接。SSE 端点用
XREAD BLOCK 同时完成"回放历史 chunk"和"跟读新 chunk"——按 Last-Event-ID
头部续读，前端断开重连自然续传。
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator

from arq.connections import ArqRedis
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.entities import GenerationTask
from app.models.enums import GenerationContentType
from app.models.schemas import GenerationTaskResponse, StreamRequest
from app.storage import (
    get_active_gen_task,
    get_gen_task,
    get_redis,
    get_workspace,
    save_gen_task,
)
from app.storage.gen_stream import read_stream
from app.utils.response import build_gen_task_response
from app.utils.sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["stream"])

# 内容类型白名单从 Enum 派生——GenerationContentType 是唯一权威来源
_VALID_CONTENT_TYPES = {e.value for e in GenerationContentType}


@router.post("/stream/{content_type}", response_model=GenerationTaskResponse)
async def start_generation(
    workspace_id: str, content_type: str, body: StreamRequest
) -> GenerationTaskResponse:
    """启动一次内容生成（幂等）。

    pending/running 状态的活跃 task 直接复用——避免用户重复点按钮或刷新
    时重复 enqueue。done/failed 视为"上一轮已结束"，创建新 task 覆盖索引。
    """
    if content_type not in _VALID_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"未知内容类型: {content_type}")

    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在或已过期")

    transcript_resource = workspace.get_resource("transcript")
    if not transcript_resource or not transcript_resource.storage_key:
        raise HTTPException(status_code=400, detail="转录内容不存在")

    existing = await get_active_gen_task(workspace_id, content_type)
    if existing and existing.status in ("pending", "running"):
        logger.info(
            "复用已有生成任务 %s (workspace=%s, type=%s, status=%s)",
            existing.task_id, workspace_id, content_type, existing.status,
        )
        return build_gen_task_response(existing)

    # 新建 task（done/failed 的情况下覆盖原索引）
    task = GenerationTask(
        task_id=str(uuid.uuid4())[:12],
        workspace_id=workspace_id,
        content_type=content_type,
        system_prompt=body.system_prompt,
        user_prompt=body.user_prompt,
    )
    await save_gen_task(task)

    redis = get_redis()
    arq_redis = ArqRedis(redis.connection_pool)
    await arq_redis.enqueue_job("run_generate_content", task.task_id)
    logger.info(
        "新生成任务 %s 已入队 (workspace=%s, type=%s)",
        task.task_id, workspace_id, content_type,
    )

    return build_gen_task_response(task)


@router.get("/generations/{task_id}/stream")
async def consume_generation(
    workspace_id: str, task_id: str, request: Request
) -> StreamingResponse:
    """SSE 消费端点：按 Last-Event-ID 续读 Redis Stream。

    XREAD 不区分 entry 是"历史"还是"新"——同一个循环既能 replay 之前的
    chunk，也能阻塞等新 chunk。前端浏览器 EventSource 重连时自动带
    Last-Event-ID，server 从该 id 之后续推。

    显式 done/error sentinel 用于判定结束，不依赖"连接关闭"——重连场景
    下无法区分"刚结束"和"早就结束很久了"。
    """
    task = await get_gen_task(task_id)
    if not task or task.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="生成任务不存在")

    last_event_id = request.headers.get("last-event-id", "0")
    redis = get_redis()

    async def generate() -> AsyncIterator[str]:
        cursor = last_event_id
        # 终态任务：stream 里一定已有 sentinel，循环一轮 replay 完即退出
        while True:
            if await request.is_disconnected():
                return

            entries = await read_stream(
                redis, task_id, cursor, block_ms=30000, count=200,
            )
            if not entries:
                # 无新消息——心跳由 sse_response 的 _with_heartbeat 自动插入
                continue

            for entry_id, fields in entries:
                cursor = entry_id
                yield f"id: {entry_id}\ndata: {json.dumps(fields)}\n\n"
                if fields.get("type") in ("done", "error"):
                    return

    return sse_response(generate)
