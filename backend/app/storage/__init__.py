"""存储抽象层"""

import logging

from .file_storage import FileStorage
from .local_file import LocalFileStorage, cleanup_old_files
from .memory_metadata import MemoryMetadataStore
from .metadata_store import MetadataStore

logger = logging.getLogger(__name__)

# 全局元数据存储实例（延迟初始化）
_metadata_store: MetadataStore | None = None


def get_metadata_store() -> MetadataStore:
    """
    根据配置返回元数据存储实例。

    - 如果配置了 MONGODB_URI，返回 MongoMetadataStore
    - 否则返回 MemoryMetadataStore（开发模式）
    """
    global _metadata_store

    if _metadata_store is not None:
        return _metadata_store

    from app.config import get_settings

    settings = get_settings()

    if settings.mongodb_uri:
        from .mongo_metadata import MongoMetadataStore

        _metadata_store = MongoMetadataStore(
            uri=settings.mongodb_uri,
            database=settings.mongodb_database,
        )
        logger.info("使用 MongoDB 元数据存储: %s", settings.mongodb_database)
    else:
        _metadata_store = MemoryMetadataStore()
        logger.info("使用内存元数据存储（开发模式）")

    return _metadata_store


__all__ = [
    "FileStorage",
    "LocalFileStorage",
    "MemoryMetadataStore",
    "MetadataStore",
    "cleanup_old_files",
    "get_metadata_store",
]
