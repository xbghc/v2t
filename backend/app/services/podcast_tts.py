"""播客 TTS 服务 - 使用阿里云百炼 TTS API 合成音频"""

import asyncio
import json
import logging
import re
import shutil
from functools import partial
from pathlib import Path

import httpx
import numpy as np
from aiolimiter import AsyncLimiter
from pedalboard.io import AudioFile

from app.config import get_settings

logger = logging.getLogger(__name__)

# 阿里云百炼 TTS API 配置
DASHSCOPE_API_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)
DEFAULT_TTS_VOICE = "Maia"
DEFAULT_TTS_MODEL = "qwen3-tts-flash"

# TTS 限制（中文算 2 字符，英文算 1 字符）
TTS_MAX_CHARS = 600  # 单次最大 TTS 字符数（约 300 中文字）

# 全局限流器：每 60 秒最多 180 次请求（百炼 TTS API 限制）
_tts_rate_limiter = AsyncLimiter(180, 60)

# 最大并发请求数（避免瞬时压力过大触发服务端限流）
TTS_MAX_CONCURRENCY = 10


def tts_char_count(text: str) -> int:
    """计算 TTS 字符数（中文算 2，ASCII 算 1）"""
    count = 0
    for char in text:
        if ord(char) > 127:
            count += 2
        else:
            count += 1
    return count


def _split_long_segment(text: str, max_chars: int) -> list[str]:
    """将超长文本按标点分割成多个短段落（基于 TTS 字符数）"""
    result = []
    remaining = text

    while remaining:
        if tts_char_count(remaining) <= max_chars:
            result.append(remaining)
            break

        # 找到不超过 max_chars 的最大切分点
        cut_pos = 0
        current_count = 0
        for i, char in enumerate(remaining):
            char_cost = 2 if ord(char) > 127 else 1
            if current_count + char_cost > max_chars:
                break
            current_count += char_cost
            cut_pos = i + 1

        chunk = remaining[:cut_pos]
        # 优先找句号
        pos = max(chunk.rfind('。'), chunk.rfind('！'), chunk.rfind('？'),
                  chunk.rfind('.'), chunk.rfind('!'), chunk.rfind('?'))
        # 其次找逗号
        if pos == -1:
            pos = max(chunk.rfind('，'), chunk.rfind(','),
                      chunk.rfind('；'), chunk.rfind(';'))
        # 强制截断
        if pos == -1:
            pos = cut_pos - 1

        result.append(remaining[:pos + 1].strip())
        remaining = remaining[pos + 1:].strip()

    return [s for s in result if s]


def iter_safe_segments(segments: list[str], max_chars: int = TTS_MAX_CHARS):
    """
    迭代 segments，自动分割超长段落

    Yields:
        str: TTS 字符数不超过 max_chars 的文本段落
    """
    for segment in segments:
        if tts_char_count(segment) <= max_chars:
            yield segment
        else:
            yield from _split_long_segment(segment, max_chars)


class PodcastTTSError(Exception):
    """播客 TTS 错误"""
    pass


async def check_tts_api() -> tuple[bool, str]:
    """检测 TTS API 是否可用"""
    settings = get_settings()
    if not settings.dashscope_api_key:
        return False, "DASHSCOPE_API_KEY 未配置"
    try:
        # 实际调用 TTS API 转录"你好"来测试连通性
        await call_dashscope_tts("你好", max_retries=1)
        return True, "OK"
    except Exception as e:
        return False, str(e)


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


async def call_dashscope_tts(
    text: str,
    voice: str = DEFAULT_TTS_VOICE,
    model: str = DEFAULT_TTS_MODEL,
    timeout: float = 60.0,
    max_retries: int = 5,
) -> str:
    """
    调用阿里云百炼 TTS API（带限流和重试）

    Args:
        text: 要合成的文本
        voice: 发音人（默认 Maia）
        model: 模型（默认 qwen3-tts-flash）
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数

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

    retry_delay = 0.0  # 重试前等待时间（在限流器外部等待）

    for attempt in range(max_retries):
        # 重试前等待（在限流器外部，不占用令牌）
        if retry_delay > 0:
            await asyncio.sleep(retry_delay)
            retry_delay = 0.0

        # 主动限流：等待获取令牌
        async with _tts_rate_limiter:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        DASHSCOPE_API_URL,
                        headers=headers,
                        json=payload,
                    )
                result = response.json()

                # 检查限流响应
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        logger.warning(
                            "触发限流 (HTTP 429)，30 秒后重试 (%d/%d)",
                            attempt + 1,
                            max_retries,
                        )
                        retry_delay = 30.0
                        continue
                    raise PodcastTTSError("百炼 TTS API 限流，重试失败")

                if "output" in result and "audio" in result["output"]:
                    return result["output"]["audio"]["url"]

                error_msg = result.get("message", str(result))

                # 检查响应内容中的限流错误
                if "Rate Limit" in error_msg or "rate limit" in error_msg.lower():
                    if attempt < max_retries - 1:
                        logger.warning(
                            "触发限流 (%s)，30 秒后重试 (%d/%d)",
                            error_msg,
                            attempt + 1,
                            max_retries,
                        )
                        retry_delay = 30.0
                        continue
                    raise PodcastTTSError("百炼 TTS API 限流，重试失败")

                raise PodcastTTSError(f"百炼 TTS API 错误: {error_msg}")

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.warning("TTS 请求超时，1 秒后重试 (%d/%d)", attempt + 1, max_retries)
                    retry_delay = 1.0
                    continue
                raise PodcastTTSError("百炼 TTS API 请求超时")
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    logger.warning("TTS 连接失败 (%s)，1 秒后重试 (%d/%d)", e, attempt + 1, max_retries)
                    retry_delay = 1.0
                    continue
                raise PodcastTTSError(f"百炼 TTS API 连接失败: {e}")
            except PodcastTTSError:
                raise

    # 不应该到达这里，但作为安全保障
    raise PodcastTTSError("百炼 TTS API 调用失败")


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


def merge_audio_segments(
    segment_paths: list[Path],
    output_path: Path,
    gap_ms: int = 500,
) -> Path:
    """
    使用 pedalboard 合并多个音频文件，片段之间添加静音间隔

    Args:
        segment_paths: 音频片段文件路径列表
        output_path: 输出文件路径
        gap_ms: 片段之间的静音间隔（毫秒），默认 500ms

    Returns:
        Path: 合并后的音频文件路径

    Raises:
        PodcastTTSError: 合并失败
    """
    if not segment_paths:
        raise PodcastTTSError("没有音频片段可合并")

    if len(segment_paths) == 1:
        shutil.copy(segment_paths[0], output_path)
        return output_path

    audio_segments = []
    sample_rate = None

    for path in segment_paths:
        with AudioFile(str(path)) as f:
            audio = f.read(f.frames)
            if sample_rate is None:
                sample_rate = f.samplerate
        audio_segments.append(audio)

    # 创建静音（shape: channels x samples）
    silence_samples = int(sample_rate * gap_ms / 1000)
    num_channels = audio_segments[0].shape[0]
    silence = np.zeros((num_channels, silence_samples), dtype=np.float32)

    # 拼接：音频 + 静音 + 音频 + 静音 + ...
    parts = []
    for i, audio in enumerate(audio_segments):
        parts.append(audio)
        if i < len(audio_segments) - 1:
            parts.append(silence)

    combined = np.concatenate(parts, axis=1)

    # 写入 MP3
    with AudioFile(str(output_path), "w", sample_rate, num_channels) as f:
        f.write(combined)

    return output_path


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

    # 安全分割：确保所有段落不超过 TTS_MAX_CHARS
    safe_segments = list(iter_safe_segments(segments))

    logger.info("播客脚本分为 %d 段进行合成", len(safe_segments))

    # 确定临时目录
    if temp_dir is None:
        temp_dir = output_path.parent
    temp_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []
    semaphore = asyncio.Semaphore(TTS_MAX_CONCURRENCY)

    try:
        # 使用信号量限制并发，避免瞬时压力过大
        async def synthesize_with_index(i: int, text: str) -> Path:
            async with semaphore:
                segment_path = temp_dir / f"podcast_segment_{i:04d}.wav"
                logger.debug("合成第 %d/%d 段: %s...", i + 1, len(safe_segments), text[:30])
                await synthesize_segment(text, segment_path)
                return segment_path

        tasks = [
            synthesize_with_index(i, text)
            for i, text in enumerate(safe_segments)
        ]
        segment_paths = list(await asyncio.gather(*tasks))

        # 合并所有片段（pedalboard 是同步 API，使用 run_in_executor 避免阻塞事件循环）
        logger.info("合并 %d 个音频片段", len(segment_paths))
        await asyncio.get_running_loop().run_in_executor(
            None,
            partial(merge_audio_segments, segment_paths, output_path)
        )

        logger.info("播客音频生成完成: %s", output_path)
        return output_path

    finally:
        # 清理临时片段文件
        for path in segment_paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError as e:
                logger.warning("清理临时文件失败 %s: %s", path, e)
