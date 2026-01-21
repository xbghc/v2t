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
class VideoTask:
    """视频下载和转录任务"""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    title: str = ""
    resource_id: str | None = None
    transcript: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    status_queue: Queue | None = field(default=None, repr=False)


@dataclass
class OutlineTask:
    """大纲生成任务"""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    transcript: str = ""  # 输入
    outline: str = ""  # 输出
    error: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class ArticleTask:
    """文章生成任务"""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    transcript: str = ""  # 输入
    article: str = ""  # 输出
    error: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class PodcastTask:
    """播客生成任务"""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = "等待处理..."
    title: str = ""
    transcript: str = ""  # 输入
    podcast_script: str = ""
    podcast_audio_path: Path | None = None
    podcast_error: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    status_queue: Queue | None = field(default=None, repr=False)


# 任务类型联合
Task = VideoTask | OutlineTask | ArticleTask | PodcastTask
