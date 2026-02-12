"""本地文件存储测试"""

import pytest

from app.storage.local_file import LocalFileStorage


@pytest.fixture
def storage(tmp_path):
    """创建临时目录的 LocalFileStorage"""
    return LocalFileStorage(base_dir=tmp_path)


class TestLocalFileStorage:
    """本地文件存储测试"""

    @pytest.mark.asyncio
    async def test_save_and_get_bytes(self, storage):
        """保存和读取字节数据"""
        await storage.save_bytes("test/hello.txt", b"Hello, World!")
        result = await storage.get_bytes("test/hello.txt")
        assert result == b"Hello, World!"

    @pytest.mark.asyncio
    async def test_save_file(self, storage, tmp_path):
        """保存本地文件"""
        # 创建源文件
        src = tmp_path / "src" / "input.txt"
        src.parent.mkdir()
        src.write_bytes(b"test content")

        await storage.save_file("data/output.txt", src)
        result = await storage.get_bytes("data/output.txt")
        assert result == b"test content"

    @pytest.mark.asyncio
    async def test_save_file_same_path_skips(self, storage):
        """源和目标相同时跳过复制"""
        target = storage.base_dir / "same.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"original")

        await storage.save_file("same.txt", target)
        assert target.read_bytes() == b"original"

    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """检查文件存在"""
        assert not await storage.exists("missing.txt")
        await storage.save_bytes("exists.txt", b"data")
        assert await storage.exists("exists.txt")

    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """删除文件"""
        await storage.save_bytes("to_delete.txt", b"data")
        assert await storage.exists("to_delete.txt")

        await storage.delete("to_delete.txt")
        assert not await storage.exists("to_delete.txt")

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """删除不存在的文件不报错"""
        await storage.delete("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_prefix(self, storage):
        """删除前缀目录"""
        await storage.save_bytes("workspace1/file1.txt", b"a")
        await storage.save_bytes("workspace1/file2.txt", b"b")
        await storage.save_bytes("workspace2/file3.txt", b"c")

        await storage.delete_prefix("workspace1")
        assert not await storage.exists("workspace1/file1.txt")
        assert not await storage.exists("workspace1/file2.txt")
        assert await storage.exists("workspace2/file3.txt")

    def test_get_local_path(self, storage):
        """获取本地路径"""
        path = storage.get_local_path("abc/video.mp4")
        assert path == storage.base_dir / "abc" / "video.mp4"
