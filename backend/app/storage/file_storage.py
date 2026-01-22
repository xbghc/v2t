"""文件存储协议定义"""

from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    """
    文件存储协议。

    定义文件存储的抽象接口，支持本地文件系统和云存储（如 OSS）。
    """

    async def exists(self, key: str) -> bool:
        """
        检查文件是否存在。

        Args:
            key: 文件路径/键名，如 "abc123/video.mp4"

        Returns:
            文件是否存在
        """
        ...

    async def get_url(self, key: str) -> str:
        """
        获取文件的访问 URL。

        Args:
            key: 文件路径/键名

        Returns:
            文件访问 URL（本地为 API 路径，OSS 为签名 URL）
        """
        ...

    async def save_file(self, key: str, local_path: Path) -> None:
        """
        保存本地文件到存储。

        Args:
            key: 目标路径/键名
            local_path: 本地文件路径
        """
        ...

    async def delete(self, key: str) -> None:
        """
        删除单个文件。

        Args:
            key: 文件路径/键名
        """
        ...

    async def delete_prefix(self, prefix: str) -> None:
        """
        删除指定前缀的所有文件。

        Args:
            prefix: 路径前缀，如 "abc123/" 删除该目录下所有文件
        """
        ...
