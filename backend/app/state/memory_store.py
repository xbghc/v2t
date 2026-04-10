"""状态管理 - Redis 后端"""

import logging

from app.models.entities import Workspace
from app.storage import get_metadata_store

logger = logging.getLogger(__name__)


async def get_workspace(workspace_id: str) -> Workspace | None:
    """获取工作区。"""
    store = get_metadata_store()
    return await store.get_workspace(workspace_id)


async def register_workspace(workspace: Workspace) -> None:
    """注册工作区。"""
    store = get_metadata_store()
    await store.save_workspace(workspace)


async def save_workspace(workspace: Workspace) -> None:
    """保存工作区（更新）。"""
    store = get_metadata_store()
    await store.save_workspace(workspace)
