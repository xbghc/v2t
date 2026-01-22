"""枚举定义"""

from enum import Enum


class WorkspaceStatus(str, Enum):
    """工作区状态"""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    READY = "ready"  # 转录完成，可以开始生成
    FAILED = "failed"


class ResourceType(str, Enum):
    """资源类型"""

    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
