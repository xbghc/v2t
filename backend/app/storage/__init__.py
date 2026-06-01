"""存储层"""

import logging
import time

from redis.asyncio import Redis

from app.models.entities import GenerationTask, Workspace, WorkspaceResource

from .local_file import LocalFileStorage, cleanup_old_files
from .metrics_store import MetricsStore
from .redis_store import RedisMetadataStore

logger = logging.getLogger(__name__)

# 全局存储实例（延迟初始化）
_metadata_store: RedisMetadataStore | None = None
_file_storage: LocalFileStorage | None = None
_metrics_store: MetricsStore | None = None
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


def get_metrics_store() -> MetricsStore:
    """返回运营统计存储实例（PV/UV、转录历史、质量计数）。"""
    global _metrics_store

    if _metrics_store is not None:
        return _metrics_store

    redis = get_redis()
    _metrics_store = MetricsStore(redis=redis)
    logger.info("使用 Redis 运营统计存储")

    return _metrics_store


def reset_stores() -> None:
    """重置全局存储实例。"""
    global _metadata_store, _file_storage, _metrics_store, _redis
    _metadata_store = None
    _file_storage = None
    _metrics_store = None
    _redis = None


# --- 便捷函数（替代 state/ 层） ---


async def get_workspace(workspace_id: str) -> Workspace | None:
    """获取工作区。"""
    store = get_metadata_store()
    return await store.get_workspace(workspace_id)


async def save_workspace(workspace: Workspace) -> None:
    """保存（或注册）工作区。"""
    store = get_metadata_store()
    await store.save_workspace(workspace)


async def add_workspace_resource(
    workspace_id: str, resource: WorkspaceResource
) -> None:
    """原子追加单个资源，避免并发流式生成互相覆盖。"""
    store = get_metadata_store()
    await store.add_resource(workspace_id, resource)


async def lookup_workspace_by_series(bvid: str, index: int) -> str | None:
    """通过 series_bvid + series_index 查找已存在的 workspace_id"""
    store = get_metadata_store()
    return await store.lookup_by_series(bvid, index)


# --- GenerationTask 便捷函数 ---


async def save_gen_task(task: GenerationTask) -> None:
    """保存生成任务并更新活跃索引。"""
    await get_metadata_store().save_gen_task(task)


async def get_gen_task(task_id: str) -> GenerationTask | None:
    return await get_metadata_store().get_gen_task(task_id)


async def get_active_gen_task(
    workspace_id: str, content_type: str
) -> GenerationTask | None:
    return await get_metadata_store().get_active_gen_task(workspace_id, content_type)


async def list_gen_tasks_for_workspace(workspace_id: str) -> list[GenerationTask]:
    return await get_metadata_store().list_gen_tasks_for_workspace(workspace_id)


async def update_gen_task(
    task_id: str,
    *,
    status: str | None = None,
    resource_id: str | None = None,
    audio_resource_id: str | None = None,
    audio_error: str | None = None,
    error: str | None = None,
) -> None:
    await get_metadata_store().update_gen_task(
        task_id,
        status=status,
        resource_id=resource_id,
        audio_resource_id=audio_resource_id,
        audio_error=audio_error,
        error=error,
    )


# --- 运营统计便捷函数 ---


async def record_pageview(path: str, visitor_id: str) -> None:
    """记录一次页面访问（PV/UV 埋点）。"""
    await get_metrics_store().record_pageview(path, visitor_id)


async def record_workspace_history(workspace: Workspace) -> None:
    """workspace 进入终态时落一份持久历史快照 + 质量计数。

    与 save_workspace 不同：这份数据无 TTL，长期累积供后台统计；即使原
    workspace 24h 后过期也仍在。
    """
    await get_metrics_store().record_workspace(
        {
            "workspace_id": workspace.workspace_id,
            "url": workspace.url,
            "title": workspace.title,
            "status": workspace.status.value,
            "error_kind": workspace.error_kind,
            "created_at": workspace.created_at,
            "finished_at": time.time(),
            "timings": workspace.timings,
        }
    )


async def get_admin_stats(days: int = 14) -> dict:
    """后台仪表盘汇总统计。"""
    return await get_metrics_store().get_stats(days)


async def list_transcribe_history(
    offset: int, limit: int
) -> tuple[list[dict], int]:
    """转录历史分页（finished_at 倒序），返回 (items, total)。"""
    return await get_metrics_store().list_history(offset, limit)


# 兼容别名
register_workspace = save_workspace


__all__ = [
    "GenerationTask",
    "LocalFileStorage",
    "MetricsStore",
    "RedisMetadataStore",
    "add_workspace_resource",
    "cleanup_old_files",
    "get_active_gen_task",
    "get_admin_stats",
    "get_file_storage",
    "get_gen_task",
    "get_metadata_store",
    "get_metrics_store",
    "get_redis",
    "get_workspace",
    "list_gen_tasks_for_workspace",
    "list_transcribe_history",
    "lookup_workspace_by_series",
    "record_pageview",
    "record_workspace_history",
    "register_workspace",
    "reset_stores",
    "save_gen_task",
    "save_workspace",
    "update_gen_task",
]
