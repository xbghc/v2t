"""状态管理模块 — 已迁移到 app.storage，保留兼容导出"""

from app.storage import get_workspace, register_workspace, save_workspace

__all__ = [
    "get_workspace",
    "register_workspace",
    "save_workspace",
]
