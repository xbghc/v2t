"""共享响应构建器"""

from app.models.entities import GenerationTask, Workspace, WorkspaceResource
from app.models.enums import ResourceType
from app.models.schemas import (
    GenerationTaskResponse,
    WorkspaceResourceResponse,
    WorkspaceResponse,
)
from app.storage import get_file_storage, list_gen_tasks_for_workspace


def build_gen_task_response(task: GenerationTask) -> GenerationTaskResponse:
    """生成任务 → 响应，stream_url 直接由后端拼好。"""
    stream_url = (
        f"/api/workspaces/{task.workspace_id}/generations/{task.task_id}/stream"
    )
    return GenerationTaskResponse(
        task_id=task.task_id,
        workspace_id=task.workspace_id,
        content_type=task.content_type,
        status=task.status,
        resource_id=task.resource_id,
        audio_resource_id=task.audio_resource_id,
        audio_error=task.audio_error,
        error=task.error,
        stream_url=stream_url,
    )


async def build_resource_response(
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
        ready=resource.ready,
        created_at=resource.created_at,
    )


async def build_workspace_response(workspace: Workspace) -> WorkspaceResponse:
    """构建工作区响应"""
    resources = [
        await build_resource_response(workspace.workspace_id, res)
        for res in workspace.resources
    ]
    # 附带各内容类型当前活跃 task —— 前端单次 GET 即可恢复（包括正在跑、已完成、已失败）
    gen_tasks = await list_gen_tasks_for_workspace(workspace.workspace_id)
    generations = [build_gen_task_response(t) for t in gen_tasks]

    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        url=workspace.url,
        title=workspace.title,
        status=workspace.status.value,
        progress=workspace.progress,
        error=workspace.error,
        error_kind=workspace.error_kind,
        resources=resources,
        generations=generations,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
        series_bvid=workspace.series_bvid,
        series_index=workspace.series_index,
        timings=dict(workspace.timings),
    )
