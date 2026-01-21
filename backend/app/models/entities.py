"""数据实体定义"""

import time
from asyncio import Queue
from dataclasses import dataclass, field
from pathlib import Path

from app.models.enums import TaskStatus


@dataclass
class Resource:
    """资源（视频/音频文件）"""

    resource_id: str  # 文件内容哈希
    video_path: Path | None = None
    audio_path: Path | None = None
    title: str = ""
    created_at: float = field(default_factory=time.time)
    ref_count: int = 1  # 引用计数


@dataclass
class TaskResult:
    """任务结果"""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    title: str = ""
    resource_id: str | None = None  # 关联的资源 ID（文件哈希）
    transcript: str = ""
    outline: str = ""
    article: str = ""
    podcast_script: str = ""
    podcast_audio_path: Path | None = None
    podcast_error: str = ""  # 播客生成失败的错误信息
    error: str = ""
    created_at: float = field(default_factory=time.time)
    # 生成选项（用于 SSE 流式生成）
    generate_outline_flag: bool = False
    generate_article_flag: bool = False
    generate_podcast_flag: bool = False
    # 自定义提示词
    outline_system_prompt: str = ""
    outline_user_prompt: str = ""
    article_system_prompt: str = ""
    article_user_prompt: str = ""
    podcast_system_prompt: str = ""
    podcast_user_prompt: str = ""
    # SSE 状态推送队列
    status_queue: Queue | None = field(default=None, repr=False)
