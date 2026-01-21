"""路由模块"""

from app.routers.process import router as process_router
from app.routers.prompts import router as prompts_router
from app.routers.resource import router as resource_router
from app.routers.stream import router as stream_router
from app.routers.task import router as task_router

__all__ = [
    "process_router",
    "task_router",
    "stream_router",
    "resource_router",
    "prompts_router",
]
