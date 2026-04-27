"""路由模块"""

from .desktop import router as desktop_router
from .prompts import router as prompts_router
from .stream import router as stream_router
from .workspace import router as workspace_router

__all__ = [
    "desktop_router",
    "workspace_router",
    "stream_router",
    "prompts_router",
]
