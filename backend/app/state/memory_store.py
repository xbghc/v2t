"""内存存储和状态管理"""

import logging
import time

from app.config import get_settings
from app.models.entities import Workspace
from app.storage import MemoryMetadataStore, cleanup_old_files

logger = logging.getLogger(__name__)

# 全局元数据存储实例
_metadata_store = MemoryMetadataStore()

# 工作区过期时间（24小时）
WORKSPACE_EXPIRE_SECONDS = 86400


def get_workspace(workspace_id: str) -> Workspace | None:
    """
    获取工作区，并更新最后访问时间。

    注意：这是同步接口，内部调用异步方法。
    """
    workspace = _metadata_store._workspaces.get(workspace_id)
    if workspace:
        workspace.last_accessed_at = time.time()
    return workspace


def register_workspace(workspace: Workspace) -> None:
    """注册工作区。"""
    _metadata_store._workspaces[workspace.workspace_id] = workspace


def cleanup_old_workspaces() -> None:
    """
    清理过期工作区（仅内存）和过期资源文件。

    - 内存中的 workspace 元数据：基于 last_accessed_at 清理
    - 文件系统中的资源目录：基于目录 atime 清理
    """
    now = time.time()

    # 清理过期的 workspace 元数据
    expired_ws_ids = [
        ws_id
        for ws_id, ws in _metadata_store._workspaces.items()
        if now - ws.last_accessed_at > WORKSPACE_EXPIRE_SECONDS
    ]
    for ws_id in expired_ws_ids:
        _metadata_store._workspaces.pop(ws_id, None)
        logger.info("清理过期工作区: %s", ws_id)

    # 清理过期的资源文件目录（基于 atime）
    settings = get_settings()
    cleaned = cleanup_old_files(settings.temp_path, WORKSPACE_EXPIRE_SECONDS)
    if cleaned > 0:
        logger.info("清理过期资源目录: %d 个", cleaned)
