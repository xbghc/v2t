"""后台任务模块"""

from app.tasks.workspace_task import process_workspace

__all__ = [
    "process_workspace",
]
