"""音频转写服务 - 使用 OpenAI Whisper 兼容 API"""

import asyncio
import logging
import re
import subprocess
from pathlib import Path

import openai
from openai import AsyncOpenAI
from rich.progress import BarColumn, Progress, TaskProgressColumn, TimeRemainingColumn

from app.config import get_settings

logger = logging.getLogger(__name__)


class TranscribeError(Exception):
    """转写错误"""
    pass


def _get_duration(video_path: Path) -> float | None:
    """获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except ValueError as e:
        logger.warning("ffprobe 输出解析失败: %s", e)
    except FileNotFoundError:
        logger.warning("ffprobe 未安装，无法获取视频时长")
    return None


def _parse_time(line: str) -> float | None:
    """解析 ffmpeg 输出中的时间"""
    match = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return None


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

    duration = _get_duration(video_path)

    cmd = [
        "ffmpeg",
        "-nostdin",
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
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        if duration:
            with Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                transient=True,
            ) as progress:
                task = progress.add_task("提取音频", total=duration)

                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    t = _parse_time(line.decode(errors="ignore"))
                    if t is not None:
                        progress.update(task, completed=min(t, duration))

                progress.update(task, completed=duration)
        else:
            await process.communicate()

        await process.wait()

        if process.returncode != 0:
            raise TranscribeError("音频提取失败")

    except FileNotFoundError:
        raise TranscribeError(
            "ffmpeg 未安装，请先安装:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg"
        )

    if not audio_path.exists():
        raise TranscribeError("音频提取失败：输出文件不存在")

    return audio_path


_whisper_client: AsyncOpenAI | None = None


def get_whisper_client() -> AsyncOpenAI:
    """获取 Whisper 兼容客户端（单例模式，复用连接）"""
    global _whisper_client
    if _whisper_client is None:
        settings = get_settings()
        if not settings.whisper_api_key:
            raise TranscribeError("WHISPER_API_KEY 未配置")
        _whisper_client = AsyncOpenAI(
            base_url=settings.whisper_base_url,
            api_key=settings.whisper_api_key,
        )
    return _whisper_client


async def check_whisper_api() -> tuple[bool, str]:
    """检测 Whisper API 是否可用"""
    settings = get_settings()
    if not settings.whisper_api_key:
        return False, "WHISPER_API_KEY 未配置"
    try:
        client = get_whisper_client()
        await client.models.list()
        return True, "OK"
    except Exception as e:
        return False, str(e)


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
    client = get_whisper_client()

    try:
        with open(audio_path, "rb") as f:
            kwargs = {
                "model": settings.whisper_model,
                "file": f,
                "response_format": "verbose_json",
            }
            if language:
                kwargs["language"] = language

            response = await client.audio.transcriptions.create(**kwargs)
    except openai.RateLimitError:
        raise TranscribeError("转录 API 配额已用尽，请稍后重试")
    except openai.APIConnectionError:
        raise TranscribeError("转录 API 连接失败，请检查网络")
    except openai.APITimeoutError:
        raise TranscribeError("转录 API 请求超时")
    except openai.APIError as e:
        raise TranscribeError(f"转录 API 错误: {e.message}")

    # 格式化为带时间戳的文本
    if hasattr(response, "segments") and response.segments:
        return format_segments(response.segments)

    # 如果没有分段，返回纯文本
    return response.text if hasattr(response, "text") else str(response)


async def transcribe_video(
    video_path: Path,
    language: str | None = None,
) -> tuple[str, Path]:
    """
    转写视频文件

    Args:
        video_path: 视频文件路径
        language: 语言代码

    Returns:
        tuple[str, Path]: (转写文本, 音频文件路径)
    """
    # 提取音频（带进度条，已存在则跳过）
    audio_path = await extract_audio_async(video_path)

    # 转写
    result = await transcribe_audio(audio_path, language)
    return result, audio_path
