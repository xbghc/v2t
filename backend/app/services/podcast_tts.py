"""播客 TTS 服务 - 使用阿里云百炼 TTS API 合成音频"""

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# 阿里云百炼 TTS API 配置
DASHSCOPE_API_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)
DEFAULT_TTS_VOICE = "Maia"
DEFAULT_TTS_MODEL = "qwen3-tts-flash"

# TTS 限制
TTS_MAX_CHARS = 600  # 单次最大字符数（300 字 = 600 字符，中文）



class PodcastTTSError(Exception):
    """播客 TTS 错误"""
    pass


def parse_segments(script: str) -> list[str]:
    """
    解析 LLM 返回的 JSON 格式分段脚本

    Args:
        script: LLM 返回的 JSON 格式脚本

    Returns:
        list[str]: 分段后的文本列表

    Raises:
        PodcastTTSError: JSON 解析失败
    """
    if not script or not script.strip():
        raise PodcastTTSError("播客脚本为空")

    script = script.strip()

    # 尝试直接解析 JSON
    try:
        data = json.loads(script)
        if isinstance(data, dict) and "segments" in data:
            segments = data["segments"]
            if isinstance(segments, list):
                return [s.strip() for s in segments if isinstance(s, str) and s.strip()]
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取 JSON
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', script, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict) and "segments" in data:
                segments = data["segments"]
                if isinstance(segments, list):
                    return [s.strip() for s in segments if isinstance(s, str) and s.strip()]
        except json.JSONDecodeError:
            pass

    raise PodcastTTSError(f"无法解析播客脚本 JSON 格式: {script[:100]}...")


def split_by_sentence(text: str) -> list[str]:
    """
    按句号/问号/感叹号分割超长段落

    Args:
        text: 要分割的文本

    Returns:
        list[str]: 分割后的句子列表
    """
    if not text or not text.strip():
        return []

    # 按句号/问号/感叹号分割，保留标点
    sentences = re.split(r'([。！？.!?])', text)

    # 重新组合句子和标点
    result = []
    current = ""

    for i in range(0, len(sentences) - 1, 2):
        sentence = sentences[i]
        punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
        combined = sentence + punctuation

        # 累积句子，直到接近限制
        if len(current) + len(combined) <= TTS_MAX_CHARS:
            current += combined
        else:
            if current:
                result.append(current.strip())
            current = combined

    # 处理最后一个（如果没有标点）
    if len(sentences) % 2 == 1 and sentences[-1]:
        if len(current) + len(sentences[-1]) <= TTS_MAX_CHARS:
            current += sentences[-1]
        else:
            if current:
                result.append(current.strip())
            current = sentences[-1]

    if current:
        result.append(current.strip())

    return [s for s in result if s]


def validate_and_fix_segments(segments: list[str]) -> list[str]:
    """
    验证并修复超长段落

    Args:
        segments: 分段列表

    Returns:
        list[str]: 修复后的分段列表

    Raises:
        PodcastTTSError: 段落过长且无法分割
    """
    result = []

    for segment in segments:
        if len(segment) <= TTS_MAX_CHARS:
            result.append(segment)
        else:
            # 警告 + 按句号分割 fallback
            logger.warning(
                "段落超过 %d 字符，尝试按句号分割: %s...",
                TTS_MAX_CHARS,
                segment[:50]
            )
            sub_segments = split_by_sentence(segment)

            for sub in sub_segments:
                if len(sub) > TTS_MAX_CHARS:
                    raise PodcastTTSError(
                        f"段落过长且无法分割: {len(sub)} 字符"
                    )
                result.append(sub)

    return result


async def call_dashscope_tts(
    text: str,
    voice: str = DEFAULT_TTS_VOICE,
    model: str = DEFAULT_TTS_MODEL,
    timeout: float = 60.0,
) -> str:
    """
    调用阿里云百炼 TTS API

    Args:
        text: 要合成的文本
        voice: 发音人（默认 Maia）
        model: 模型（默认 qwen3-tts-flash）
        timeout: 请求超时时间（秒）

    Returns:
        str: 生成的音频文件 URL

    Raises:
        PodcastTTSError: API 调用失败
    """
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise PodcastTTSError("未配置 DASHSCOPE_API_KEY 环境变量")

    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": {"text": text, "voice": voice},
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                DASHSCOPE_API_URL,
                headers=headers,
                json=payload,
            )
            result = response.json()

            if "output" in result and "audio" in result["output"]:
                return result["output"]["audio"]["url"]
            else:
                error_msg = result.get("message", str(result))
                raise PodcastTTSError(f"百炼 TTS API 错误: {error_msg}")

        except httpx.TimeoutException:
            raise PodcastTTSError("百炼 TTS API 请求超时")
        except httpx.RequestError as e:
            raise PodcastTTSError(f"百炼 TTS API 连接失败: {e}")


async def download_audio(url: str, output_path: Path, timeout: float = 30.0) -> Path:
    """
    下载音频文件

    Args:
        url: 音频文件 URL
        output_path: 输出文件路径
        timeout: 下载超时时间（秒）

    Returns:
        Path: 下载的文件路径

    Raises:
        PodcastTTSError: 下载失败
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            if response.status_code != 200:
                raise PodcastTTSError(f"音频下载失败: HTTP {response.status_code}")
            output_path.write_bytes(response.content)
            return output_path
        except httpx.TimeoutException:
            raise PodcastTTSError("音频下载超时")
        except httpx.RequestError as e:
            raise PodcastTTSError(f"音频下载失败: {e}")


async def synthesize_segment(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_TTS_VOICE,
    model: str = DEFAULT_TTS_MODEL,
    timeout: float = 60.0,
) -> Path:
    """
    合成单段音频

    Args:
        text: 要合成的文本
        output_path: 输出音频文件路径
        voice: 发音人
        model: TTS 模型
        timeout: 请求超时时间（秒）

    Returns:
        Path: 生成的音频文件路径

    Raises:
        PodcastTTSError: 合成失败
    """
    if len(text) > TTS_MAX_CHARS:
        raise PodcastTTSError(f"文本长度 {len(text)} 超过限制 {TTS_MAX_CHARS}")

    # 调用百炼 API 获取音频 URL
    audio_url = await call_dashscope_tts(text, voice, model, timeout)

    # 下载音频文件
    await download_audio(audio_url, output_path)

    return output_path


async def merge_audio_segments(
    segment_paths: list[Path],
    output_path: Path,
) -> Path:
    """
    使用 ffmpeg concat 合并多个音频文件

    Args:
        segment_paths: 音频片段文件路径列表
        output_path: 输出文件路径

    Returns:
        Path: 合并后的音频文件路径

    Raises:
        PodcastTTSError: 合并失败
    """
    if not segment_paths:
        raise PodcastTTSError("没有音频片段可合并")

    if len(segment_paths) == 1:
        # 只有一个片段，直接复制
        import shutil
        shutil.copy(segment_paths[0], output_path)
        return output_path

    # 创建 concat 列表文件
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.txt',
        delete=False,
        encoding='utf-8'
    ) as f:
        for path in segment_paths:
            # ffmpeg concat 需要转义单引号
            escaped_path = str(path).replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
        concat_list_path = Path(f.name)

    try:
        # 使用 ffmpeg concat demuxer 合并并转码为 MP3
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",  # 覆盖输出
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c:a", "libmp3lame",  # 转码为 MP3
            "-q:a", "2",  # 高质量 VBR
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "未知错误"
            raise PodcastTTSError(f"音频合并失败: {error_msg}")

        return output_path

    finally:
        # 清理临时文件
        try:
            concat_list_path.unlink()
        except OSError:
            pass


async def generate_podcast_audio(
    script: str,
    output_path: Path,
    temp_dir: Path | None = None,
) -> Path:
    """
    生成播客音频主流程

    Args:
        script: 播客脚本文本
        output_path: 输出音频文件路径
        temp_dir: 临时文件目录

    Returns:
        Path: 生成的播客音频文件路径

    Raises:
        PodcastTTSError: 生成失败
    """
    if not script or not script.strip():
        raise PodcastTTSError("播客脚本为空")

    # 解析 LLM 分段
    segments = parse_segments(script)
    if not segments:
        raise PodcastTTSError("文本分段失败")

    # 验证并修复超长段落
    segments = validate_and_fix_segments(segments)

    logger.info("播客脚本分为 %d 段进行合成", len(segments))

    # 确定临时目录
    if temp_dir is None:
        temp_dir = output_path.parent
    temp_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []

    try:
        # 并发合成所有段落
        async def synthesize_with_index(i: int, text: str) -> Path:
            segment_path = temp_dir / f"podcast_segment_{i:04d}.wav"
            logger.debug("合成第 %d/%d 段: %s...", i + 1, len(segments), text[:30])
            await synthesize_segment(text, segment_path)
            return segment_path

        tasks = [
            synthesize_with_index(i, text)
            for i, text in enumerate(segments)
        ]
        segment_paths = list(await asyncio.gather(*tasks))

        # 合并所有片段
        logger.info("合并 %d 个音频片段", len(segment_paths))
        await merge_audio_segments(segment_paths, output_path)

        logger.info("播客音频生成完成: %s", output_path)
        return output_path

    finally:
        # 清理临时片段文件
        for path in segment_paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
