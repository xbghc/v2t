"""阿里云百炼语音识别服务 - 通过 DashScope SDK 调用 Paraformer"""

import asyncio
import logging
from http import HTTPStatus
from pathlib import Path

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback

from app.config import get_settings
from app.services.transcribe import TranscribeError, format_timestamp

logger = logging.getLogger(__name__)


class _NoopCallback(RecognitionCallback):
    """Recognition 要求 callback 参数，但 call() 模式不使用它"""

    def on_event(self, result):
        pass

    def on_error(self, result):
        pass


def _format_sentences(sentences: list[dict]) -> str:
    """将 DashScope 句子列表格式化为带时间戳的文本"""
    lines = []
    for sent in sentences:
        text = sent.get("text", "").strip()
        if not text:
            continue
        begin_ms = sent.get("begin_time", 0)
        timestamp = format_timestamp(begin_ms / 1000.0)
        lines.append(f"[{timestamp}] {text}")
    return "\n".join(lines)


def _call_recognition(audio_path: Path, language: str | None) -> str:
    """同步调用 DashScope Recognition（在线程中执行）"""
    settings = get_settings()

    if not settings.dashscope_api_key:
        raise TranscribeError("DASHSCOPE_API_KEY 未配置")

    dashscope.api_key = settings.dashscope_api_key

    audio_format = audio_path.suffix.lstrip(".")
    language_hints = [language] if language else ["zh", "en"]

    recognition = Recognition(
        model=settings.dashscope_stt_model,
        callback=_NoopCallback(),
        format=audio_format,
        sample_rate=16000,
        language_hints=language_hints,
    )

    result = recognition.call(str(audio_path))

    if result.status_code != HTTPStatus.OK:
        raise TranscribeError(
            f"DashScope STT 失败 (HTTP {result.status_code}): {result.message}"
        )

    sentences = result.get_sentence()
    if not sentences:
        raise TranscribeError("DashScope STT 返回空结果")

    if isinstance(sentences, dict):
        sentences = [sentences]

    return _format_sentences(sentences)


async def transcribe_audio_dashscope(
    audio_path: Path,
    language: str | None = None,
) -> str:
    """通过 DashScope SDK 转录音频文件

    Args:
        audio_path: 音频文件路径
        language: 语言代码（如 "zh", "en"），None 默认中英混合

    Returns:
        str: 带时间戳的转写文本
    """
    return await asyncio.to_thread(_call_recognition, audio_path, language)


async def check_dashscope_stt() -> tuple[bool, str]:
    """检测 DashScope STT 是否可用（仅检查 API Key 配置）"""
    settings = get_settings()
    if not settings.dashscope_api_key:
        return False, "DASHSCOPE_API_KEY 未配置"
    return True, f"OK (model: {settings.dashscope_stt_model})"
