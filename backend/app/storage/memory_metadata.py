"""内存元数据存储实现"""

import time

from app.models.entities import Workspace


class MemoryMetadataStore:
    """
    内存元数据存储实现。

    使用字典存储工作区元数据，适用于单机部署。
    """

    def __init__(self):
        self._workspaces: dict[str, Workspace] = {}

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        """获取工作区。"""
        workspace = self._workspaces.get(workspace_id)
        if workspace:
            workspace.last_accessed_at = time.time()
        return workspace

    async def save_workspace(self, workspace: Workspace) -> None:
        """保存工作区。"""
        self._workspaces[workspace.workspace_id] = workspace

    async def delete_workspace(self, workspace_id: str) -> None:
        """删除工作区。"""
        self._workspaces.pop(workspace_id, None)

    async def list_expired_workspaces(self, expire_seconds: int) -> list[Workspace]:
        """列出过期的工作区。"""
        now = time.time()
        return [
            ws
            for ws in self._workspaces.values()
            if now - ws.last_accessed_at > expire_seconds
        ]
