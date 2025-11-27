"""音频转写服务 - 使用 Groq Whisper API"""

import asyncio
import subprocess
from pathlib import Path

import openai
from openai import AsyncOpenAI

from app.config import get_settings


class TranscribeError(Exception):
    """转写错误"""
    pass


def extract_audio(video_path: Path, audio_path: Path | None = None) -> Path:
    """
    从视频中提取音频

    Args:
        video_path: 视频文件路径
        audio_path: 音频输出路径（可选）

    Returns:
        Path: 音频文件路径
    """
    if audio_path is None:
        audio_path = video_path.with_suffix(".mp3")

    if audio_path.exists():
        return audio_path

    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(video_path),
                "-vn",  # 不处理视频
                "-acodec", "libmp3lame",
                "-ar", "16000",  # Whisper 推荐采样率
                "-ac", "1",  # 单声道
                "-q:a", "4",  # 质量
                "-y",  # 覆盖输出
                str(audio_path),
            ],
            check=True,
            capture_output=True,
        )
        return audio_path
    except subprocess.CalledProcessError as e:
        raise TranscribeError(f"音频提取失败: {e.stderr.decode()}") from e
    except FileNotFoundError:
        raise TranscribeError("ffmpeg 未安装，请先安装 ffmpeg")


def get_groq_client() -> AsyncOpenAI:
    """获取 Groq 客户端"""
    settings = get_settings()

    if not settings.groq_api_key:
        raise TranscribeError("GROQ_API_KEY 未配置")

    return AsyncOpenAI(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
    )


def format_timestamp(seconds: float) -> str:
    """格式化时间戳为 MM:SS 格式"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def format_segments(segments: list) -> str:
    """将分段数据格式化为带时间戳的文本"""
    lines = []
    for seg in segments:
        start = format_timestamp(getattr(seg, "start", 0))
        text = getattr(seg, "text", "").strip()
        if text:
            lines.append(f"[{start}] {text}")
    return "\n".join(lines)


async def transcribe_audio(
    audio_path: Path,
    language: str | None = None,
) -> str:
    """
    转写音频文件

    Args:
        audio_path: 音频文件路径
        language: 语言代码（如 "zh", "en"），None 为自动检测

    Returns:
        str: 带时间戳的转写文本
    """
    settings = get_settings()
    client = get_groq_client()

    try:
        with open(audio_path, "rb") as f:
            kwargs = {
                "model": settings.groq_whisper_model,
                "file": f,
                "response_format": "verbose_json",
            }
            if language:
                kwargs["language"] = language

            response = await client.audio.transcriptions.create(**kwargs)
    except openai.RateLimitError:
        raise TranscribeError(
            "Groq 转录配额已用尽 (每小时限制 2 小时音频)\n"
            "请等待约 1 小时后重试"
        )
    except openai.APIConnectionError:
        raise TranscribeError("Groq API 连接失败，请检查网络")
    except openai.APITimeoutError:
        raise TranscribeError("Groq API 请求超时")
    except openai.APIError as e:
        raise TranscribeError(f"Groq API 错误: {e.message}")

    # 格式化为带时间戳的文本
    if hasattr(response, "segments") and response.segments:
        return format_segments(response.segments)

    # 如果没有分段，返回纯文本
    return response.text if hasattr(response, "text") else str(response)


async def transcribe_video(
    video_path: Path,
    language: str | None = None,
    keep_audio: bool = False,
) -> str:
    """
    转写视频文件

    Args:
        video_path: 视频文件路径
        language: 语言代码
        keep_audio: 是否保留提取的音频文件

    Returns:
        str: 转写文本
    """
    # 提取音频
    loop = asyncio.get_event_loop()
    audio_path = await loop.run_in_executor(None, extract_audio, video_path)

    try:
        # 转写
        result = await transcribe_audio(audio_path, language)
        return result
    finally:
        # 清理音频文件
        if not keep_audio and audio_path.exists():
            audio_path.unlink()
