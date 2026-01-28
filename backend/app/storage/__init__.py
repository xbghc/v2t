"""存储抽象层"""

import logging

from .file_storage import FileStorage
from .local_file import LocalFileStorage, cleanup_old_files
from .metadata_store import MetadataStore
from .mongo_metadata import MongoMetadataStore

logger = logging.getLogger(__name__)

# 全局元数据存储实例（延迟初始化）
_metadata_store: MongoMetadataStore | None = None


def get_metadata_store() -> MongoMetadataStore:
    """
    返回 MongoDB 元数据存储实例。

    必须配置 MONGODB_URI 环境变量。
    """
    global _metadata_store

    if _metadata_store is not None:
        return _metadata_store

    from app.config import get_settings

    settings = get_settings()

    _metadata_store = MongoMetadataStore(
        uri=settings.mongodb_uri,
        database=settings.mongodb_database,
    )
    logger.info("使用 MongoDB 元数据存储: %s", settings.mongodb_database)

    return _metadata_store


__all__ = [
    "FileStorage",
    "LocalFileStorage",
    "MetadataStore",
    "MongoMetadataStore",
    "cleanup_old_files",
    "get_metadata_store",
]
