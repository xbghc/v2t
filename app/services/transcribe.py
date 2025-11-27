"""音频转写服务 - 使用 Groq Whisper API"""

import asyncio
from pathlib import Path

import openai
from openai import AsyncOpenAI
from better_ffmpeg_progress import FfmpegProcess

from app.config import get_settings


class TranscribeError(Exception):
    """转写错误"""
    pass


def _run_ffmpeg(video_path: Path, audio_path: Path) -> None:
    """运行 ffmpeg 提取音频（带进度条）"""
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        "-q:a", "4",
        "-y",
        str(audio_path),
    ]

    try:
        process = FfmpegProcess(cmd, ffmpeg_log_level="error")
        process.run()
        if process.return_code != 0:
            raise TranscribeError(f"音频提取失败，退出码: {process.return_code}")
    except FileNotFoundError:
        raise TranscribeError("ffmpeg 未安装，请先安装 ffmpeg")


async def extract_audio_async(
    video_path: Path,
    audio_path: Path | None = None,
) -> Path:
    """
    从视频中提取音频（异步，带进度条）

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

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_ffmpeg, video_path, audio_path)

    if not audio_path.exists():
        raise TranscribeError("音频提取失败：输出文件不存在")

    return audio_path


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
    # 提取音频（带进度条）
    audio_path = await extract_audio_async(video_path)

    try:
        # 转写
        result = await transcribe_audio(audio_path, language)
        return result
    finally:
        # 清理音频文件
        if not keep_audio and audio_path.exists():
            audio_path.unlink()
