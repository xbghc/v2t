"""STT 流式转录的基础类型与 Provider 协议"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class AudioChunk:
    """音频切片，由 streaming_pipeline 产出，由 Provider 消费"""

    path: Path
    """切片在磁盘上的位置（mp3）"""

    index: int
    """切片序号，从 0 开始"""

    start: float
    """切片在原音频中的起始秒数（绝对时间）"""

    end: float
    """切片在原音频中的结束秒数（绝对时间）"""

    is_last: bool = False
    """是否为最后一片"""

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class TranscriptSegment:
    """转录段，Provider 产出，调用方消费

    一个 AudioChunk 通常会被拆成多个 TranscriptSegment（句子级时间戳）。
    时间戳已重映射为原音频的绝对秒数。
    """

    start: float
    """段在原音频中的起始秒数（绝对时间）"""

    end: float
    """段在原音频中的结束秒数（绝对时间）"""

    text: str
    """转录文本"""

    chunk_index: int = -1
    """所属切片序号，便于上层进度跟踪"""


@dataclass
class TranscribeContext:
    """转录上下文，Provider 可选利用其中字段做调优"""

    language: str | None = None
    """语言提示，如 "zh" "en"，None 为自动检测"""

    extra: dict = field(default_factory=dict)


class STTProvider(Protocol):
    """STT Provider 接口

    实现可以是真流式（WebSocket / SSE）或伪流式（切片 + 并发）。
    上层通过 transcribe_stream 函数路由到具体 Provider，对调用方完全透明。
    """

    name: str

    max_audio_duration: int | None
    """单次任务推荐处理的音频时长上限（秒）；None 为无上限。

    用于 select_provider 做时长路由：超过此值的音频不会被分派到该 Provider，
    主要是防止 Groq free 等限额端点被长视频打爆 RPM/quota。
    """

    async def is_available(self) -> tuple[bool, str]:
        """是否可用（API key 配置 + 端点可达）"""

    async def transcribe_stream(
        self,
        chunks: AsyncIterator[AudioChunk],
        context: TranscribeContext,
    ) -> AsyncIterator[TranscriptSegment]:
        """消费切片流，按时间顺序产出转录段"""
        ...
