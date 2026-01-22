"""内存存储和状态管理"""

import logging
import time

from app.models.entities import Workspace

logger = logging.getLogger(__name__)

# 工作区存储
workspaces: dict[str, Workspace] = {}

# 工作区过期时间（24小时）
WORKSPACE_EXPIRE_SECONDS = 86400


def get_workspace(workspace_id: str) -> Workspace | None:
    """获取工作区，并更新最后访问时间"""
    workspace = workspaces.get(workspace_id)
    if workspace:
        workspace.last_accessed_at = time.time()
    return workspace


def register_workspace(workspace: Workspace) -> None:
    """注册工作区"""
    workspaces[workspace.workspace_id] = workspace


def cleanup_old_workspaces() -> None:
    """清理过期工作区及其资源文件"""
    now = time.time()
    expired_ws_ids = [
        ws_id
        for ws_id, ws in workspaces.items()
        if now - ws.last_accessed_at > WORKSPACE_EXPIRE_SECONDS
    ]
    for ws_id in expired_ws_ids:
        ws = workspaces.pop(ws_id, None)
        if ws:
            # 清理所有资源文件
            for resource in ws.resources:
                if resource.resource_path and resource.resource_path.exists():
                    try:
                        resource.resource_path.unlink()
                        logger.info("清理资源文件: %s", resource.resource_path)
                    except OSError as e:
                        logger.warning("清理资源文件失败 %s: %s", resource.resource_path, e)
            logger.info("清理过期工作区: %s", ws_id)
