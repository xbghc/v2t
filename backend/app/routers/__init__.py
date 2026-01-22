"""路由模块"""

from .prompts import router as prompts_router
from .stream import router as stream_router
from .workspace import router as workspace_router

__all__ = [
    "workspace_router",
    "stream_router",
    "prompts_router",
]
