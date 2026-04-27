"""数据实体定义"""

import time
from dataclasses import dataclass, field

from .enums import ResourceType, WorkspaceStatus


@dataclass
class WorkspaceResource:
    """工作区资源"""

    resource_id: str
    name: str  # video, audio, transcript, outline, article, podcast, zhihu
    resource_type: ResourceType
    storage_key: str | None = None  # 存储路径
    prompt: str | None = None  # 生成时的 prompt（TEXT 类型资源的元数据）
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
    # B 站分 P 系列元数据（非分 P 视频留空）
    series_bvid: str = ""
    series_index: int = 0  # 1-based 分 P 序号；0 表示非系列

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
