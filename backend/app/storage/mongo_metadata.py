"""MongoDB 元数据存储实现"""

import time
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus


class MongoMetadataStore:
    """
    MongoDB 元数据存储实现。

    使用 MongoDB 持久化工作区元数据，适用于生产环境。
    """

    def __init__(self, uri: str, database: str):
        """
        初始化 MongoDB 存储。

        Args:
            uri: MongoDB 连接 URI
            database: 数据库名称
        """
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self._db: AsyncIOMotorDatabase = self._client[database]
        self._collection = self._db["workspaces"]

    def _workspace_to_doc(self, workspace: Workspace) -> dict[str, Any]:
        """将 Workspace dataclass 转换为 MongoDB 文档"""
        resources = []
        for res in workspace.resources:
            resources.append({
                "resource_id": res.resource_id,
                "name": res.name,
                "resource_type": res.resource_type.value,
                "resource_path": str(res.resource_path) if res.resource_path else None,
                "created_at": res.created_at,
            })

        return {
            "_id": workspace.workspace_id,
            "url": workspace.url,
            "title": workspace.title,
            "status": workspace.status.value,
            "progress": workspace.progress,
            "error": workspace.error,
            "resources": resources,
            "created_at": workspace.created_at,
            "last_accessed_at": workspace.last_accessed_at,
        }

    def _doc_to_workspace(self, doc: dict[str, Any]) -> Workspace:
        """将 MongoDB 文档转换为 Workspace dataclass"""
        resources = []
        for res_doc in doc.get("resources", []):
            resource_path = res_doc.get("resource_path")
            resources.append(WorkspaceResource(
                resource_id=res_doc["resource_id"],
                name=res_doc["name"],
                resource_type=ResourceType(res_doc["resource_type"]),
                resource_path=Path(resource_path) if resource_path else None,
                created_at=res_doc.get("created_at", time.time()),
            ))

        return Workspace(
            workspace_id=doc["_id"],
            url=doc.get("url", ""),
            title=doc.get("title", ""),
            status=WorkspaceStatus(doc.get("status", "pending")),
            progress=doc.get("progress", ""),
            error=doc.get("error", ""),
            resources=resources,
            created_at=doc.get("created_at", time.time()),
            last_accessed_at=doc.get("last_accessed_at", time.time()),
            status_queue=None,  # 不持久化队列
        )

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        """获取工作区并更新 last_accessed_at"""
        now = time.time()
        result = await self._collection.find_one_and_update(
            {"_id": workspace_id},
            {"$set": {"last_accessed_at": now}},
            return_document=True,
        )
        if result:
            return self._doc_to_workspace(result)
        return None

    async def save_workspace(self, workspace: Workspace) -> None:
        """保存工作区（upsert）"""
        doc = self._workspace_to_doc(workspace)
        await self._collection.replace_one(
            {"_id": workspace.workspace_id},
            doc,
            upsert=True,
        )

    async def delete_workspace(self, workspace_id: str) -> None:
        """删除工作区"""
        await self._collection.delete_one({"_id": workspace_id})

    async def list_expired_workspaces(self, expire_seconds: int) -> list[Workspace]:
        """列出过期的工作区"""
        threshold = time.time() - expire_seconds
        cursor = self._collection.find({"last_accessed_at": {"$lt": threshold}})
        workspaces = []
        async for doc in cursor:
            workspaces.append(self._doc_to_workspace(doc))
        return workspaces

    async def check_connection(self) -> tuple[bool, str]:
        """检查 MongoDB 连接"""
        try:
            await self._client.admin.command("ping")
            return True, f"已连接到 {self._db.name}"
        except Exception as e:
            return False, str(e)
