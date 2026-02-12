"""MongoDB 集成测试"""

import time

import pytest

from app.models.entities import Workspace
from app.storage import MongoMetadataStore
from tests.conftest import MONGO_DB, MONGO_URI


class TestMongoMetadataStore:
    """MongoDB 元数据存储测试（需要运行 MongoDB）"""

    @pytest.fixture
    async def store(self):
        """创建测试用 MongoDB 存储实例"""
        if not MONGO_URI or not MONGO_DB:
            pytest.skip("TEST_MONGODB_URI 或 TEST_MONGODB_DATABASE 未配置")

        store = MongoMetadataStore(
            uri=MONGO_URI,
            database=MONGO_DB,
        )
        # 检查连接
        ok, _ = await store.check_connection()
        if not ok:
            pytest.skip("MongoDB 不可用")
        yield store
        # 清理测试数据
        await store._collection.delete_many({})

    @pytest.mark.asyncio
    async def test_save_and_get(self, store):
        """保存和获取工作区"""
        ws = Workspace(workspace_id="test123", url="https://example.com")
        await store.save_workspace(ws)

        result = await store.get_workspace("test123")
        assert result is not None
        assert result.workspace_id == "test123"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        """获取不存在的工作区返回 None"""
        result = await store.get_workspace("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, store):
        """删除工作区"""
        ws = Workspace(workspace_id="test123", url="https://example.com")
        await store.save_workspace(ws)
        await store.delete_workspace("test123")

        result = await store.get_workspace("test123")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_expired(self, store):
        """列出过期工作区"""
        # 创建一个"过期"的工作区
        ws = Workspace(workspace_id="old", url="https://old.com")
        ws.last_accessed_at = time.time() - 100  # 100秒前
        await store.save_workspace(ws)

        # 创建一个新的工作区
        ws_new = Workspace(workspace_id="new", url="https://new.com")
        await store.save_workspace(ws_new)

        # 查找超过50秒未访问的
        expired = await store.list_expired_workspaces(50)
        assert len(expired) == 1
        assert expired[0].workspace_id == "old"
