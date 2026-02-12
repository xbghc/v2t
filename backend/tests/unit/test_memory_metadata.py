"""内存元数据存储测试"""

import time

import pytest

from app.models.entities import Workspace
from app.storage.memory_metadata import MemoryMetadataStore


class TestMemoryMetadataStore:
    """内存元数据存储测试"""

    @pytest.fixture
    def store(self):
        """创建存储实例"""
        return MemoryMetadataStore()

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

    @pytest.mark.asyncio
    async def test_check_connection(self, store):
        """检查连接（始终成功）"""
        ok, msg = await store.check_connection()
        assert ok is True
        assert "内存" in msg
