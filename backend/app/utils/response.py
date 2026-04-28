"""共享响应构建器"""

from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType
from app.models.schemas import WorkspaceResourceResponse, WorkspaceResponse
from app.storage import get_file_storage


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

    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        url=workspace.url,
        title=workspace.title,
        status=workspace.status.value,
        progress=workspace.progress,
        error=workspace.error,
        error_kind=workspace.error_kind,
        resources=resources,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
        series_bvid=workspace.series_bvid,
        series_index=workspace.series_index,
    )
