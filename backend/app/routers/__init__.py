"""路由模块"""

from app.routers.prompts import router as prompts_router
from app.routers.stream import router as stream_router
from app.routers.workspace import router as workspace_router

__all__ = [
    "workspace_router",
    "stream_router",
    "prompts_router",
]
