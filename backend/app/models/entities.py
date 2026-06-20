"""数据实体定义"""

import time
from dataclasses import dataclass, field

from .enums import ResourceType, WorkspaceStatus


@dataclass
class WorkspaceResource:
    """工作区资源"""

    resource_id: str
    name: str  # video, audio, transcript, outline, article, podcast
    resource_type: ResourceType
    storage_key: str | None = None  # 存储路径
    prompt: str | None = None  # 生成时的 prompt（TEXT 类型资源的元数据）
    ready: bool = False  # 资源是否产出完成；前端按此判断是否可下载/展示
    created_at: float = field(default_factory=time.time)


@dataclass
class GenerationTask:
    """内容生成任务（outline / article / podcast）

    一次生成对应一条 Redis Stream（key = `gen:{task_id}`），worker 把 LLM chunk
    XADD 进去；SSE 端点按 Last-Event-ID 续读。task_id 全局唯一，stream 自带
    完整生命周期（chunk → done/error sentinel → EXPIRE）。
    """

    task_id: str
    workspace_id: str
    content_type: str  # outline / article / podcast
    status: str = "pending"  # pending / running / done / failed
    resource_id: str = ""  # 完成后落盘的 WorkspaceResource id（文本内容）
    audio_resource_id: str = ""  # podcast 特有：TTS 产出的音频 resource id
    audio_error: str = ""  # podcast 特有：脚本成功但 TTS 失败时的提示
    error: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Workspace:
    """工作区"""

    workspace_id: str
    url: str = ""
    title: str = ""
    status: WorkspaceStatus = WorkspaceStatus.PENDING
    progress: str = "等待处理..."
    error: str = ""  # 用户可读的友好消息（不含技术细节，可直接展示）
    error_kind: str = ""  # 分类：video_too_long / download_failed / transcribe_failed / unknown
    resources: list[WorkspaceResource] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    # B 站分 P 系列元数据（非分 P 视频留空）
    series_bvid: str = ""
    series_index: int = 0  # 1-based 分 P 序号；0 表示非系列
    # 阶段耗时（秒）。stage_name → duration；audio_duration 为视频本身时长
    timings: dict[str, float] = field(default_factory=dict)

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
