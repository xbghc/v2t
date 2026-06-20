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


class GenerationContentType(str, Enum):
    """可生成的内容类型。

    这是"有哪些内容类型"的唯一权威来源：路由层从这里派生白名单做校验，
    OpenAPI 据此生成精确 union，前端 codegen 同步——不再前后端各硬编码一份。
    """

    OUTLINE = "outline"
    ARTICLE = "article"
    PODCAST = "podcast"


class GenerationStatus(str, Enum):
    """内容生成任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class WorkspaceErrorKind(str, Enum):
    """工作区失败原因分类（前端据此决定是否给重试按钮等）。

    空字符串 = 无错误（成功或处理中）。其余取值与 _mark_failed 的调用一一对应。
    """

    NONE = ""
    VIDEO_TOO_LONG = "video_too_long"
    DOWNLOAD_FAILED = "download_failed"
    TRANSCRIBE_FAILED = "transcribe_failed"
    UNKNOWN = "unknown"
