"""存储层"""

import logging

from .local_file import LocalFileStorage, cleanup_old_files
from .metadata_store import MetadataStore
from .mongo_metadata import MongoMetadataStore

logger = logging.getLogger(__name__)

# 全局存储实例（延迟初始化）
_metadata_store: MongoMetadataStore | None = None
_file_storage: LocalFileStorage | None = None


def get_file_storage() -> LocalFileStorage:
    """返回本地文件存储实例。"""
    global _file_storage

    if _file_storage is not None:
        return _file_storage

    from app.config import get_settings

    settings = get_settings()

    _file_storage = LocalFileStorage(base_dir=settings.data_path)
    logger.info("使用本地文件存储: %s", settings.data_path)

    return _file_storage


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


def reset_stores() -> None:
    """重置全局存储实例，用于事件循环切换后重新创建连接。"""
    global _metadata_store, _file_storage
    _metadata_store = None
    _file_storage = None


__all__ = [
    "LocalFileStorage",
    "MetadataStore",
    "MongoMetadataStore",
    "cleanup_old_files",
    "get_file_storage",
    "get_metadata_store",
    "reset_stores",
]
