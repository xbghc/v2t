"""Redis 元数据存储实现"""

import json
import logging
import time

from redis.asyncio import Redis

from app.models.entities import Workspace, WorkspaceResource
from app.models.enums import ResourceType, WorkspaceStatus

# 工作区过期时间（24小时）
WORKSPACE_TTL = 86400


class RedisMetadataStore:
    """
    Redis 元数据存储实现。

    使用 Redis Hash 持久化工作区元数据，配合 TTL 自动过期。
    """

    def __init__(self, redis: Redis):
        self._redis = redis

    def _workspace_key(self, workspace_id: str) -> str:
        return f"workspace:{workspace_id}"

    def _resources_key(self, workspace_id: str) -> str:
        return f"workspace:{workspace_id}:resources"

    def _series_lookup_key(self, bvid: str, index: int) -> str:
        return f"workspace:lookup:{bvid}:{index}"

    def _workspace_to_hash(self, workspace: Workspace) -> dict[str, str]:
        """将 Workspace 转换为 Redis Hash 字段"""
        return {
            "url": workspace.url,
            "title": workspace.title,
            "status": workspace.status.value,
            "progress": workspace.progress,
            "error": workspace.error,
            "created_at": str(workspace.created_at),
            "last_accessed_at": str(workspace.last_accessed_at),
            "series_bvid": workspace.series_bvid,
            "series_index": str(workspace.series_index),
        }

    def _resource_to_json(self, resource: WorkspaceResource) -> str:
        """将 WorkspaceResource 序列化为 JSON 字符串"""
        return json.dumps({
            "resource_id": resource.resource_id,
            "name": resource.name,
            "resource_type": resource.resource_type.value,
            "storage_key": resource.storage_key,
            "prompt": resource.prompt,
            "created_at": resource.created_at,
        })

    def _json_to_resource(self, data: str) -> WorkspaceResource:
        """从 JSON 字符串反序列化 WorkspaceResource"""
        d = json.loads(data)
        return WorkspaceResource(
            resource_id=d["resource_id"],
            name=d["name"],
            resource_type=ResourceType(d["resource_type"]),
            storage_key=d.get("storage_key"),
            prompt=d.get("prompt"),
            created_at=d.get("created_at", time.time()),
        )

    def _hash_to_workspace(
        self, workspace_id: str, data: dict[str, str], resources: list[WorkspaceResource]
    ) -> Workspace:
        """从 Redis Hash 数据构建 Workspace"""
        try:
            series_index = int(data.get("series_index") or 0)
        except ValueError:
            series_index = 0
        return Workspace(
            workspace_id=workspace_id,
            url=data.get("url", ""),
            title=data.get("title", ""),
            status=WorkspaceStatus(data.get("status", "pending")),
            progress=data.get("progress", ""),
            error=data.get("error", ""),
            resources=resources,
            created_at=float(data.get("created_at", time.time())),
            last_accessed_at=float(data.get("last_accessed_at", time.time())),
            series_bvid=data.get("series_bvid", ""),
            series_index=series_index,
        )

    async def get_workspace(self, workspace_id: str) -> Workspace | None:
        """获取工作区并更新 last_accessed_at"""
        key = self._workspace_key(workspace_id)
        data = await self._redis.hgetall(key)
        if not data:
            return None

        # 更新 last_accessed_at 并刷新 TTL
        now = str(time.time())
        await self._redis.hset(key, "last_accessed_at", now)
        await self._redis.expire(key, WORKSPACE_TTL)
        await self._redis.expire(self._resources_key(workspace_id), WORKSPACE_TTL)

        data["last_accessed_at"] = now

        # 获取资源列表
        resources = await self._get_resources(workspace_id)
        return self._hash_to_workspace(workspace_id, data, resources)

    async def _get_resources(self, workspace_id: str) -> list[WorkspaceResource]:
        """获取工作区的资源列表"""
        raw_list = await self._redis.lrange(self._resources_key(workspace_id), 0, -1)
        resources = []
        for item in raw_list:
            try:
                resources.append(self._json_to_resource(item))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logging.getLogger(__name__).warning(
                    "跳过损坏的资源数据: %s", e
                )
        return resources

    async def save_workspace(self, workspace: Workspace) -> None:
        """保存工作区（upsert），设置 TTL"""
        key = self._workspace_key(workspace.workspace_id)
        res_key = self._resources_key(workspace.workspace_id)

        # 保存 Hash 字段
        await self._redis.hset(key, mapping=self._workspace_to_hash(workspace))

        # 替换资源列表（先删后写）
        pipe = self._redis.pipeline()
        pipe.delete(res_key)
        for res in workspace.resources:
            pipe.rpush(res_key, self._resource_to_json(res))
        # 设置 TTL
        pipe.expire(key, WORKSPACE_TTL)
        pipe.expire(res_key, WORKSPACE_TTL)
        # 系列元数据：写二级索引（与主键 TTL 对齐）
        if workspace.series_bvid and workspace.series_index > 0:
            lookup_key = self._series_lookup_key(
                workspace.series_bvid, workspace.series_index
            )
            pipe.set(lookup_key, workspace.workspace_id, ex=WORKSPACE_TTL)
        await pipe.execute()

    async def lookup_by_series(self, bvid: str, index: int) -> str | None:
        """通过 series_bvid + series_index 查找已存在的 workspace_id"""
        if not bvid or index <= 0:
            return None
        return await self._redis.get(self._series_lookup_key(bvid, index))

    async def delete_workspace(self, workspace_id: str) -> None:
        """删除工作区"""
        await self._redis.delete(
            self._workspace_key(workspace_id),
            self._resources_key(workspace_id),
        )

    async def check_connection(self) -> tuple[bool, str]:
        """检查 Redis 连接"""
        try:
            await self._redis.ping()
            return True, "已连接到 Redis"
        except Exception as e:
            return False, str(e)
