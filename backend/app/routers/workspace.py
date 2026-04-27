"""工作区路由"""

import json
import logging
import uuid

from arq.connections import ArqRedis
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus
from app.models.schemas import (
    CreateFromTranscriptRequest,
    CreateWorkspaceRequest,
    WorkspaceResponse,
)
from app.storage import (
    get_file_storage,
    get_redis,
    get_workspace,
    register_workspace,
    save_workspace,
)
from app.utils.response import build_workspace_response
from app.utils.sse import sse_heartbeat, sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspace"])


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest) -> WorkspaceResponse:
    """创建工作区并启动视频处理"""
    # 创建工作区
    workspace_id = str(uuid.uuid4())[:12]
    workspace = Workspace(workspace_id=workspace_id, url=request.url)
    await register_workspace(workspace)

    # 通过 arq 提交后台任务
    redis = get_redis()
    arq_redis = ArqRedis(redis.connection_pool)
    await arq_redis.enqueue_job("run_process_workspace", workspace_id, request.url)
    logger.info("工作区 %s 已入队，等待 worker pickup: %s", workspace_id, request.url)

    return await build_workspace_response(workspace)


@router.post("/from-transcript", response_model=WorkspaceResponse)
async def create_workspace_from_transcript(
    request: CreateFromTranscriptRequest,
) -> WorkspaceResponse:
    """从已有转录文本直接创建工作区，跳过下载/转录流程，状态直接置 ready。"""
    workspace_id = str(uuid.uuid4())[:12]
    workspace = Workspace(
        workspace_id=workspace_id,
        url=request.source_url,
        title=request.title,
        status=WorkspaceStatus.READY,
        progress="转录已就绪",
    )

    storage = get_file_storage()
    transcript_key = f"{workspace_id}/transcript.txt"
    await storage.save_bytes(transcript_key, request.transcript.encode("utf-8"))

    transcript_resource = WorkspaceResource(
        resource_id=str(uuid.uuid4())[:8],
        name="transcript",
        resource_type=ResourceType.TEXT,
        storage_key=transcript_key,
    )
    workspace.add_resource(transcript_resource)

    await save_workspace(workspace)
    logger.info("工作区 %s 从 transcript 直接创建（ready）", workspace_id)

    return await build_workspace_response(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace_info(workspace_id: str) -> WorkspaceResponse:
    """获取工作区信息"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在或已过期")

    return await build_workspace_response(workspace)


@router.get("/{workspace_id}/status-stream")
async def stream_workspace_status(
    workspace_id: str, request: Request
) -> StreamingResponse:
    """SSE 推送工作区状态变化（通过 Redis Pub/Sub）"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    async def generate():
        # 先订阅 Redis Pub/Sub channel（在读取当前状态之前！）
        # 这样即使 worker 在我们读取状态后立即发布消息，也不会丢失
        redis = get_redis()
        pubsub = redis.pubsub()
        channel = f"workspace:{workspace_id}:status"
        await pubsub.subscribe(channel)
        logger.info("工作区 %s SSE 已连接，当前状态: %s", workspace_id, workspace.status.value)

        try:
            # 发送当前状态
            current = await get_workspace(workspace_id)
            if not current:
                return
            response = await build_workspace_response(current)
            yield f"data: {response.model_dump_json()}\n\n"

            # 如果已完成或失败，直接返回
            if current.status in (WorkspaceStatus.READY, WorkspaceStatus.FAILED):
                return

            # 持续监听状态变化
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=30.0
                )
                if message is not None and message["type"] == "message":
                    data_str = message["data"]
                    yield f"data: {data_str}\n\n"
                    data = json.loads(data_str)
                    if data.get("status") in ("ready", "failed"):
                        break
                else:
                    # 超时，发心跳
                    yield sse_heartbeat()
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            logger.info("工作区 %s SSE 已断开", workspace_id)

    return sse_response(generate)


@router.get("/{workspace_id}/resources/{resource_id}")
async def download_resource(workspace_id: str, resource_id: str) -> FileResponse:
    """下载资源文件"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    # 查找资源
    resource = None
    for res in workspace.resources:
        if res.resource_id == resource_id:
            resource = res
            break

    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    if not resource.storage_key:
        raise HTTPException(status_code=404, detail="资源文件不存在")

    # TEXT 类型通过 content 字段返回，不需要下载
    if resource.resource_type == ResourceType.TEXT:
        raise HTTPException(status_code=400, detail="文本资源不支持下载")

    storage = get_file_storage()
    local_path = storage.get_local_path(resource.storage_key)

    if not local_path.exists():
        raise HTTPException(status_code=404, detail="资源文件不存在")

    return FileResponse(path=local_path)
