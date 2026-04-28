"""枚举定义"""

from enum import Enum


class WorkspaceStatus(str, Enum):
    """工作区状态

    流式管道下，下载/抽音频/转录融合为单一 PROCESSING 阶段；
    具体进度通过 progress 字符串和 resource.ready 标志传达。
    """

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

    @classmethod
    def _missing_(cls, value):
        if value in ("downloading", "transcribing"):
            return cls.PROCESSING
        return None


class ResourceType(str, Enum):
    """资源类型"""

    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
