"""枚举定义"""

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    READY = "ready"  # 转录完成，可以开始生成（前端并行调用各生成端点）
    COMPLETED = "completed"
    FAILED = "failed"
