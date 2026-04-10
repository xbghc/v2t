"""存储层"""

import logging

from redis.asyncio import Redis

from .local_file import LocalFileStorage, cleanup_old_files
from .metadata_store import MetadataStore
from .redis_store import RedisMetadataStore

logger = logging.getLogger(__name__)

# 全局存储实例（延迟初始化）
_metadata_store: RedisMetadataStore | None = None
_file_storage: LocalFileStorage | None = None
_redis: Redis | None = None


def get_redis() -> Redis:
    """返回全局 Redis 连接实例。"""
    global _redis

    if _redis is not None:
        return _redis

    from app.config import get_settings

    settings = get_settings()

    _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Redis 连接: %s", settings.redis_url)

    return _redis


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


def get_metadata_store() -> RedisMetadataStore:
    """返回 Redis 元数据存储实例。"""
    global _metadata_store

    if _metadata_store is not None:
        return _metadata_store

    redis = get_redis()
    _metadata_store = RedisMetadataStore(redis=redis)
    logger.info("使用 Redis 元数据存储")

    return _metadata_store


def reset_stores() -> None:
    """重置全局存储实例。"""
    global _metadata_store, _file_storage, _redis
    _metadata_store = None
    _file_storage = None
    _redis = None


__all__ = [
    "LocalFileStorage",
    "MetadataStore",
    "RedisMetadataStore",
    "cleanup_old_files",
    "get_file_storage",
    "get_metadata_store",
    "get_redis",
    "reset_stores",
]
