"""存储层测试"""

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from app.storage import LocalFileStorage, MongoMetadataStore, cleanup_old_files
from app.utils.url_hash import compute_url_hash, normalize_url


class TestUrlHash:
    """URL 规范化和哈希测试"""

    def test_normalize_removes_tracking_params(self):
        """移除追踪参数"""
        url = "https://www.bilibili.com/video/BV123?vd_source=abc&utm_source=test"
        normalized = normalize_url(url)
        assert "vd_source" not in normalized
        assert "utm_source" not in normalized

    def test_normalize_preserves_important_params(self):
        """保留重要参数"""
        url = "https://www.bilibili.com/video/BV123?p=2&vd_source=abc"
        normalized = normalize_url(url)
        assert "p=2" in normalized

    def test_normalize_lowercase(self):
        """URL 小写化"""
        url = "HTTPS://WWW.BILIBILI.COM/video/BV123"
        normalized = normalize_url(url)
        assert normalized.startswith("https://www.bilibili.com")

    def test_normalize_removes_trailing_slash(self):
        """移除尾部斜杠"""
        url = "https://www.bilibili.com/video/BV123/"
        normalized = normalize_url(url)
        assert not normalized.endswith("/")

    def test_same_url_same_hash(self):
        """相同 URL 产生相同哈希"""
        url1 = "https://www.bilibili.com/video/BV123?vd_source=abc"
        url2 = "https://www.bilibili.com/video/BV123?vd_source=xyz"
        assert compute_url_hash(url1) == compute_url_hash(url2)

    def test_different_url_different_hash(self):
        """不同 URL 产生不同哈希"""
        url1 = "https://www.bilibili.com/video/BV123"
        url2 = "https://www.bilibili.com/video/BV456"
        assert compute_url_hash(url1) != compute_url_hash(url2)

    def test_different_p_param_different_hash(self):
        """不同分P产生不同哈希"""
        url1 = "https://www.bilibili.com/video/BV123?p=1"
        url2 = "https://www.bilibili.com/video/BV123?p=2"
        assert compute_url_hash(url1) != compute_url_hash(url2)


class TestLocalFileStorage:
    """本地文件存储测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        d = tempfile.mkdtemp()
        yield Path(d)
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def storage(self, temp_dir):
        """创建存储实例"""
        return LocalFileStorage(temp_dir)

    @pytest.mark.asyncio
    async def test_exists_nonexistent(self, storage):
        """不存在的文件返回 False"""
        assert not await storage.exists("nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_save_and_exists(self, storage, temp_dir):
        """保存文件后 exists 返回 True"""
        # 创建测试文件
        test_file = temp_dir / "source.txt"
        test_file.write_text("test content")

        # 保存到存储
        await storage.save_file("abc123/video.mp4", test_file)

        # 验证存在
        assert await storage.exists("abc123/video.mp4")
        assert (temp_dir / "abc123" / "video.mp4").exists()

    @pytest.mark.asyncio
    async def test_delete(self, storage, temp_dir):
        """删除文件"""
        # 创建文件
        (temp_dir / "test.txt").write_text("content")

        # 删除
        await storage.delete("test.txt")

        # 验证
        assert not (temp_dir / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_delete_prefix(self, storage, temp_dir):
        """删除目录"""
        # 创建目录和文件
        d = temp_dir / "abc123"
        d.mkdir()
        (d / "video.mp4").write_text("video")
        (d / "audio.mp3").write_text("audio")

        # 删除目录
        await storage.delete_prefix("abc123")

        # 验证目录不存在
        assert not d.exists()

    def test_get_local_path(self, storage, temp_dir):
        """获取本地路径"""
        path = storage.get_local_path("abc123/video.mp4")
        assert path == temp_dir / "abc123" / "video.mp4"


@pytest.mark.mongo
class TestMongoMetadataStore:
    """MongoDB 元数据存储测试（需要运行 MongoDB）"""

    @pytest.fixture
    async def store(self):
        """创建测试用 MongoDB 存储实例"""
        store = MongoMetadataStore(
            uri="mongodb://localhost:27017",
            database="v2t_test",
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
        from app.models.entities import Workspace

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
        from app.models.entities import Workspace

        ws = Workspace(workspace_id="test123", url="https://example.com")
        await store.save_workspace(ws)
        await store.delete_workspace("test123")

        result = await store.get_workspace("test123")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_expired(self, store):
        """列出过期工作区"""
        from app.models.entities import Workspace

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


class TestCleanupOldFiles:
    """过期文件清理测试"""

    def test_cleanup_old_directories(self):
        """清理过期目录"""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # 创建一个"旧"目录
            old_dir = temp_dir / "old_hash"
            old_dir.mkdir()
            (old_dir / "video.mp4").write_text("video")

            # 设置 atime 为 2 天前
            old_time = time.time() - 2 * 86400
            os.utime(old_dir, (old_time, old_time))

            # 创建一个"新"目录
            new_dir = temp_dir / "new_hash"
            new_dir.mkdir()
            (new_dir / "video.mp4").write_text("video")

            # 清理超过 1 天的
            cleaned = cleanup_old_files(temp_dir, expire_seconds=86400)

            # 验证
            assert cleaned == 1
            assert not old_dir.exists()
            assert new_dir.exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cleanup_empty_dir(self):
        """空目录不报错"""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            cleaned = cleanup_old_files(temp_dir)
            assert cleaned == 0
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cleanup_nonexistent_dir(self):
        """不存在的目录不报错"""
        cleaned = cleanup_old_files(Path("/nonexistent/path"))
        assert cleaned == 0
