"""数据实体定义"""

import time
from asyncio import Queue
from dataclasses import dataclass, field
from pathlib import Path

from .enums import ResourceType, WorkspaceStatus


@dataclass
class WorkspaceResource:
    """工作区资源"""

    resource_id: str
    name: str  # video, audio, transcript, outline, article, podcast, zhihu
    resource_type: ResourceType
    resource_path: Path | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class Workspace:
    """工作区"""

    workspace_id: str
    url: str = ""
    title: str = ""
    status: WorkspaceStatus = WorkspaceStatus.PENDING
    progress: str = "等待处理..."
    error: str = ""
    resources: list[WorkspaceResource] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    status_queue: Queue | None = field(default=None, repr=False)

    def get_resource(self, name: str) -> WorkspaceResource | None:
        """获取指定名称的最新资源"""
        for res in reversed(self.resources):
            if res.name == name:
                return res
        return None

    def get_resources_by_name(self, name: str) -> list[WorkspaceResource]:
        """获取指定名称的所有资源"""
        return [res for res in self.resources if res.name == name]

    def add_resource(self, resource: WorkspaceResource) -> None:
        """添加资源"""
        self.resources.append(resource)
        self.last_accessed_at = time.time()
