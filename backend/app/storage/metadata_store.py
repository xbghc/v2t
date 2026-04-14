"""元数据存储协议定义"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.models.entities import Workspace


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

    async def delete_workspace(self, workspace_id: str) -> None:
        """
        删除工作区。

        Args:
            workspace_id: 工作区 ID
        """
        ...
