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


class ProviderRateLimited(Exception):
    """Provider 撞流控信号 — Router 接到这个就把 provider 挂 cooldown 切下一个

    retry_after 来自 HTTP `Retry-After` header（Whisper/Groq）；
    DashScope 等没有该头的 provider 用一个固定默认值。
    """

    def __init__(self, retry_after: float, provider_name: str = "") -> None:
        self.retry_after = retry_after
        self.provider_name = provider_name
        super().__init__(
            f"{provider_name or 'provider'} rate limited (retry_after={retry_after:.1f}s)"
        )


class STTProvider(Protocol):
    """STT Provider 接口 — 单 chunk 转录，Router 负责并发与 fallback

    撞限流时抛 ProviderRateLimited，Router 接到后挂 cooldown 切下一个；
    其他错误直接传播让整个流中止。
    """

    name: str

    async def is_available(self) -> tuple[bool, str]:
        """是否可用（API key 配置 + 端点可达）"""

    async def transcribe_chunk(
        self,
        chunk: AudioChunk,
        context: TranscribeContext,
    ) -> list[TranscriptSegment]:
        """转录单个切片，返回该切片的所有句子段（绝对时间戳）"""
        ...


# 兼容旧导入路径：transcribe_stream 是 router 模块的统一入口，
# 但许多旧测试/调用者直接 from .base import ... — 此处不再导出 stream API
__all__ = [
    "AudioChunk",
    "ProviderRateLimited",
    "STTProvider",
    "TranscribeContext",
    "TranscriptSegment",
]
