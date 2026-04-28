"""元数据存储协议定义"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.models.entities import Workspace, WorkspaceResource


class MetadataStore(Protocol):
    """
    元数据存储协议。

    定义工作区元数据存储的抽象接口。
    """

    async def get_workspace(self, workspace_id: str) -> "Workspace | None":
        """
        获取工作区。

        Args:
            workspace_id: 工作区 ID

        Returns:
            工作区对象，不存在则返回 None
        """
        ...

    async def save_workspace(self, workspace: "Workspace") -> None:
        """
        保存工作区。

        Args:
            workspace: 工作区对象
        """
        ...

    async def add_resource(
        self, workspace_id: str, resource: "WorkspaceResource"
    ) -> None:
        """
        原子追加单个资源到工作区，不影响其它已有资源。

        用于多个流式生成并发完成的场景：每条流只追加自己的资源，
        避免 save_workspace 全量覆盖时把其它并发流刚加的资源丢掉。

        Args:
            workspace_id: 工作区 ID
            resource: 要追加的资源
        """
        ...

    async def delete_workspace(self, workspace_id: str) -> None:
        """
        删除工作区。

        Args:
            workspace_id: 工作区 ID
        """
        ...
