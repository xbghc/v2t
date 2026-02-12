"""本地文件存储实现"""

import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """
    本地文件存储实现。

    文件组织结构：
        base_dir/
            {url_hash}/
                video.mp4
                audio.mp3
                transcript.txt
            {workspace_id}/
                outline_{resource_id}.txt
                article_{resource_id}.txt
                podcast_{resource_id}.mp3
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        return (self.base_dir / key).exists()

    async def save_file(self, key: str, local_path: Path) -> None:
        """保存本地文件到存储（复制）"""
        target = self.base_dir / key
        target.parent.mkdir(parents=True, exist_ok=True)

        if local_path.resolve() == target.resolve():
            return

        shutil.copy2(local_path, target)

    async def save_bytes(self, key: str, data: bytes) -> None:
        """保存字节数据到文件"""
        target = self.base_dir / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def get_bytes(self, key: str) -> bytes:
        """读取文件字节内容"""
        return (self.base_dir / key).read_bytes()

    async def delete(self, key: str) -> None:
        """删除单个文件"""
        target = self.base_dir / key
        if target.exists():
            target.unlink()

    async def delete_prefix(self, prefix: str) -> None:
        """删除指定前缀的所有文件（删除整个目录）"""
        target = self.base_dir / prefix
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    def get_local_path(self, key: str) -> Path:
        """获取文件的本地路径"""
        return self.base_dir / key


def cleanup_old_files(base_dir: Path, expire_seconds: int = 86400) -> int:
    """
    清理过期的资源目录。

    基于目录的访问时间（atime）判断是否过期。

    Returns:
        清理的目录数量
    """
    if not base_dir.exists():
        return 0

    now = time.time()
    cleaned = 0

    for item in base_dir.iterdir():
        if item.is_dir():
            try:
                atime = item.stat().st_atime
                if now - atime > expire_seconds:
                    shutil.rmtree(item)
                    logger.info("清理过期资源目录: %s", item.name)
                    cleaned += 1
            except OSError as e:
                logger.warning("清理目录失败 %s: %s", item.name, e)

    return cleaned
