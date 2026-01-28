"""状态管理 - 使用可配置的元数据存储"""

import logging

from app.config import get_settings
from app.models.entities import Workspace
from app.storage import cleanup_old_files, get_metadata_store

logger = logging.getLogger(__name__)

# 工作区过期时间（24小时）
WORKSPACE_EXPIRE_SECONDS = 86400

# 内存中的 status_queue 缓存（MongoDB 不能持久化 Queue 对象）
_status_queues: dict[str, object] = {}


async def get_workspace(workspace_id: str) -> Workspace | None:
    """
    获取工作区，并更新最后访问时间。

    如果使用 MongoDB，从数据库读取；否则从内存读取。
    status_queue 从内存缓存中恢复。
    """
    store = get_metadata_store()
    workspace = await store.get_workspace(workspace_id)
    if workspace:
        # 恢复 status_queue（仅存在于内存中）
        workspace.status_queue = _status_queues.get(workspace_id)
    return workspace


async def register_workspace(workspace: Workspace) -> None:
    """注册工作区。"""
    store = get_metadata_store()
    # 缓存 status_queue
    if workspace.status_queue:
        _status_queues[workspace.workspace_id] = workspace.status_queue
    await store.save_workspace(workspace)


async def save_workspace(workspace: Workspace) -> None:
    """保存工作区（更新）。"""
    store = get_metadata_store()
    # 更新 status_queue 缓存
    if workspace.status_queue:
        _status_queues[workspace.workspace_id] = workspace.status_queue
    await store.save_workspace(workspace)


async def cleanup_old_workspaces() -> None:
    """
    清理过期工作区和过期资源文件。

    - 元数据存储中的 workspace：基于 last_accessed_at 清理
    - 文件系统中的资源目录：基于目录 atime 清理
    """
    store = get_metadata_store()

    # 清理过期的 workspace 元数据
    expired = await store.list_expired_workspaces(WORKSPACE_EXPIRE_SECONDS)
    for ws in expired:
        await store.delete_workspace(ws.workspace_id)
        # 清理 status_queue 缓存
        _status_queues.pop(ws.workspace_id, None)
        logger.info("清理过期工作区: %s", ws.workspace_id)

    # 清理过期的资源文件目录（基于 atime）
    settings = get_settings()
    cleaned = cleanup_old_files(settings.temp_path, WORKSPACE_EXPIRE_SECONDS)
    if cleaned > 0:
        logger.info("清理过期资源目录: %d 个", cleaned)
