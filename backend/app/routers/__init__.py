"""路由模块"""

from .admin import router as admin_router
from .bilibili import router as bilibili_router
from .diagnostics import router as diagnostics_router
from .media import router as media_router
from .metrics import router as metrics_router
from .prompts import router as prompts_router
from .stream import router as stream_router
from .workspace import router as workspace_router

__all__ = [
    "admin_router",
    "media_router",
    "workspace_router",
    "stream_router",
    "prompts_router",
    "bilibili_router",
    "diagnostics_router",
    "metrics_router",
]
