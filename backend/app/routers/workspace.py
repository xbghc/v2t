"""工作区路由"""

import asyncio
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus
from app.models.schemas import (
    CreateWorkspaceRequest,
    WorkspaceResourceResponse,
    WorkspaceResponse,
)
from app.state import cleanup_old_workspaces, get_workspace, register_workspace, set_status_queue
from app.storage import get_file_storage
from app.tasks import process_workspace
from app.utils.sse import sse_heartbeat, sse_response

router = APIRouter(prefix="/api/workspaces", tags=["workspace"])


async def _build_resource_response(
    workspace_id: str, resource: WorkspaceResource
) -> WorkspaceResourceResponse:
    """构建资源响应"""
    download_url = None
    content = None

    if resource.resource_type in (ResourceType.VIDEO, ResourceType.AUDIO):
        download_url = f"/api/workspaces/{workspace_id}/resources/{resource.resource_id}"
    elif resource.resource_type == ResourceType.TEXT and resource.storage_key:
        try:
            storage = get_file_storage()
            content_bytes = await storage.get_bytes(resource.storage_key)
            content = content_bytes.decode("utf-8")
        except Exception:
            content = ""

    return WorkspaceResourceResponse(
        resource_id=resource.resource_id,
        name=resource.name,
        resource_type=resource.resource_type.value,
        download_url=download_url,
        content=content,
        created_at=resource.created_at,
    )


async def _build_workspace_response(workspace: Workspace) -> WorkspaceResponse:
    """构建工作区响应"""
    resources = [
        await _build_resource_response(workspace.workspace_id, res)
        for res in workspace.resources
    ]

    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        url=workspace.url,
        title=workspace.title,
        status=workspace.status.value,
        progress=workspace.progress,
        error=workspace.error,
        resources=resources,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
    )


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: CreateWorkspaceRequest, background_tasks: BackgroundTasks
) -> WorkspaceResponse:
    """创建工作区并启动视频处理"""
    # 清理过期工作区
    await cleanup_old_workspaces()

    # 创建工作区
    workspace_id = str(uuid.uuid4())[:12]
    workspace = Workspace(workspace_id=workspace_id, url=request.url)
    await register_workspace(workspace)

    # 启动后台处理
    background_tasks.add_task(process_workspace, workspace_id, request.url)

    return await _build_workspace_response(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace_info(workspace_id: str) -> WorkspaceResponse:
    """获取工作区信息"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在或已过期")

    return await _build_workspace_response(workspace)


@router.get("/{workspace_id}/status-stream")
async def stream_workspace_status(
    workspace_id: str, request: Request
) -> StreamingResponse:
    """SSE 推送工作区状态变化"""
    workspace = await get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    # 创建队列并注册到全局缓存（确保后台任务能找到）
    if not workspace.status_queue:
        workspace.status_queue = asyncio.Queue()
        set_status_queue(workspace_id, workspace.status_queue)

    async def generate():
        # 发送当前状态
        response = await _build_workspace_response(workspace)
        yield f"data: {response.model_dump_json()}\n\n"

        # 如果已完成或失败，直接返回
        if workspace.status in (WorkspaceStatus.READY, WorkspaceStatus.FAILED):
            return

        # 持续监听状态变化
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(workspace.status_queue.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in ("ready", "failed"):
                    break
            except TimeoutError:
                yield sse_heartbeat()

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
