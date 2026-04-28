"""语音活动检测 (VAD) - Silero VAD

提供两个核心能力：
    1. detect_speech_ranges: 对已落盘音频跑 VAD，返回完整 speech 区间列表
       （用于一次性场景，比如 streaming_pipeline 兜底或单元测试）
    2. plan_split_points: 把目标切点（每 30s）贴到附近 silence 中点

streaming_pipeline.py 内部用增量流式 VAD（VADIterator + ffmpeg PCM stream）
直接做切点决策，那部分逻辑不在这里。本文件保留 _load_model / _silero_lock
作为公共入口供它复用。

silero-vad ONNX runtime 不是线程安全的，model 调用必须串行。
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_silero_lock = asyncio.Lock()
_VAD_SAMPLE_RATE = 16000
_VAD_FRAME_SAMPLES = 512  # silero @ 16kHz 固定
_VAD_FRAME_BYTES = _VAD_FRAME_SAMPLES * 2  # int16
_VAD_READ_BATCH = _VAD_FRAME_BYTES * 64  # ~2s 一批


def _load_model():
    """单进程内单例加载 Silero VAD（onnx 后端）"""
    global _model
    if _model is None:
        from silero_vad import load_silero_vad

        logger.info("加载 Silero VAD 模型...")
        _model = load_silero_vad(onnx=True)
    return _model


@dataclass
class SpeechRange:
    """有声语音区间（秒）"""

    start: float
    end: float


def _vad_consume_pcm_stream(stdout) -> list[SpeechRange]:
    """从 stdout 同步读 16k mono int16 PCM 喂 VADIterator，返回 speech_ranges"""
    import numpy as np
    import torch
    from silero_vad import VADIterator

    model = _load_model()
    vad_iter = VADIterator(
        model,
        sampling_rate=_VAD_SAMPLE_RATE,
        threshold=0.5,
        min_silence_duration_ms=200,
    )

    speech_ranges: list[SpeechRange] = []
    current_start: float | None = None
    buf = bytearray()

    while True:
        chunk = stdout.read(_VAD_READ_BATCH)
        if not chunk:
            break
        buf.extend(chunk)
        while len(buf) >= _VAD_FRAME_BYTES:
            frame_bytes = bytes(buf[:_VAD_FRAME_BYTES])
            del buf[:_VAD_FRAME_BYTES]
            arr = (
                np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
                / 32768.0
            )
            event = vad_iter(
                torch.from_numpy(arr.copy()), return_seconds=True
            )
            if not event:
                continue
            if "start" in event:
                current_start = float(event["start"])
            if "end" in event and current_start is not None:
                speech_ranges.append(
                    SpeechRange(start=current_start, end=float(event["end"]))
                )
                current_start = None

    vad_iter.reset_states()
    return speech_ranges


def _detect_pcm_sync(audio_path: Path) -> list[SpeechRange]:
    """对已落盘音频单独跑 VAD"""
    proc = subprocess.Popen(
        [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-i", str(audio_path),
            "-ar", str(_VAD_SAMPLE_RATE), "-ac", "1",
            "-f", "s16le", "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        ranges = _vad_consume_pcm_stream(proc.stdout)
    finally:
        if proc.stdout:
            proc.stdout.close()
    rc = proc.wait()
    if rc != 0:
        stderr = (
            proc.stderr.read().decode(errors="ignore")[-300:]
            if proc.stderr
            else ""
        )
        raise RuntimeError(f"ffmpeg 解码音频失败 ({rc}): {stderr}")
    return ranges


async def detect_speech_ranges(audio_path: Path) -> list[SpeechRange]:
    """对已落盘音频跑 VAD（一次性场景）"""
    async with _silero_lock:
        return await asyncio.to_thread(_detect_pcm_sync, audio_path)


def plan_split_points(
    speech_ranges: list[SpeechRange],
    total_duration: float,
    target_segment: float = 30.0,
    tolerance: float = 5.0,
    min_segment: float = 5.0,
) -> list[float]:
    """根据 VAD 结果决定切点（绝对秒数列表）

    对每个目标位置 i*target_segment，在 [target-tolerance, target+tolerance] 内寻找
    最接近的 silence（speech 之间的间隙）中点作为切点。范围内无 silence 则强切目标点。

    Returns:
        切点的秒数列表（不含 0 和 total_duration），例如 [27.5, 58.2, 89.0]。
        据此切片为 [0, 27.5], [27.5, 58.2], [58.2, 89.0], [89.0, total]。
    """
    if total_duration <= target_segment * 1.2:
        return []

    silences: list[tuple[float, float]] = []
    if speech_ranges:
        if speech_ranges[0].start > 0.05:
            silences.append((0.0, speech_ranges[0].start))
        for i in range(len(speech_ranges) - 1):
            silences.append((speech_ranges[i].end, speech_ranges[i + 1].start))
        if speech_ranges[-1].end < total_duration - 0.05:
            silences.append((speech_ranges[-1].end, total_duration))
    else:
        silences.append((0.0, total_duration))

    split_points: list[float] = []
    target = target_segment
    last_split = 0.0
    while target < total_duration - min_segment:
        best: float | None = None
        for sil_start, sil_end in silences:
            sil_mid = (sil_start + sil_end) / 2
            if abs(sil_mid - target) > tolerance:
                continue
            if sil_mid <= last_split + min_segment:
                continue
            if sil_mid >= total_duration - min_segment:
                continue
            if best is None or abs(sil_mid - target) < abs(best - target):
                best = sil_mid

        chosen = best if best is not None else target
        split_points.append(chosen)
        last_split = chosen
        target = chosen + target_segment

    return split_points
