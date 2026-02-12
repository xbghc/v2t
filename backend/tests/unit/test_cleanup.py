"""过期文件清理测试"""

import os
import shutil
import tempfile
import time
from pathlib import Path

from app.storage import cleanup_old_files


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
