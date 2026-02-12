"""内存元数据存储实现（用于测试）"""

import time

from app.models.entities import Workspace


class MemoryMetadataStore:
    """
    内存元数据存储实现。

    用于单元测试，不需要外部服务依赖。
    """

    def __init__(self):
        self._workspaces: dict[str, Workspace] = {}

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        """获取工作区并更新 last_accessed_at"""
        workspace = self._workspaces.get(workspace_id)
        if workspace:
            workspace.last_accessed_at = time.time()
        return workspace

    async def save_workspace(self, workspace: Workspace) -> None:
        """保存工作区"""
        self._workspaces[workspace.workspace_id] = workspace

    async def delete_workspace(self, workspace_id: str) -> None:
        """删除工作区"""
        self._workspaces.pop(workspace_id, None)

    async def list_expired_workspaces(self, expire_seconds: int) -> list[Workspace]:
        """列出过期的工作区"""
        threshold = time.time() - expire_seconds
        return [
            ws for ws in self._workspaces.values()
            if ws.last_accessed_at < threshold
        ]

    async def check_connection(self) -> tuple[bool, str]:
        """检查连接（内存存储始终可用）"""
        return True, "内存存储"
