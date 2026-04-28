"""流式音频管道（VAD 增量切点版）

流程（首次）：
    1. ffmpeg 抽 audio.mp3（一次性，由 prepare_audio 完成）
    2. ffmpeg 解码 audio.mp3 → s16le PCM stdout
    3. silero-vad VADIterator 边读 PCM 边推理 → 累积 speech_ranges
    4. 当处理时间 t > target_segment * (i+1) + tolerance 时，
       第 i 个目标切点的 [target±tolerance] 区间内所有 silence 已知，
       立即决策切点并 push 到内部 queue
    5. 切片任务消费 queue：ffmpeg `-ss A -t D -c:a copy` 从 audio.mp3 切单段（毫秒级）
    6. yield AudioChunk → 上游 STT 立即启动

第一片启动延迟：~3-5s（VAD 跑到 30s 处只要 ~0.3s，加切片 1-2s）。

流程（缓存命中）：
    切片 manifest + 文件都在 → 直接按 manifest yield，零开销复用。

silero-vad ONNX 不是线程安全，全 VAD 推理串到 _silero_lock 同步执行。
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from app.services.downloader import VideoResult
from app.services.stt.base import AudioChunk
from app.services.transcribe import _get_duration
from app.services.vad import (
    SpeechRange,
    _load_model,
    _silero_lock,
)

logger = logging.getLogger(__name__)

SEGMENT_DURATION = 30.0
SEGMENT_TOLERANCE = 5.0
SEGMENTS_DIRNAME = "audio_segments"
MANIFEST_FILENAME = "segments.json"
MIN_SEGMENT_BYTES = 1024
MIN_SEGMENT_SECONDS = 5.0

_VAD_SAMPLE_RATE = 16000
_VAD_FRAME_SAMPLES = 512  # silero @ 16kHz 固定
_VAD_FRAME_BYTES = _VAD_FRAME_SAMPLES * 2  # int16
_VAD_READ_BATCH_BYTES = _VAD_FRAME_BYTES * 64  # ~2s 一批读


class StreamingPipelineError(Exception):
    """流式管道错误"""


@dataclass
class SegmentationState:
    """切片管道运行状态，由调用方持有"""

    audio_path: Path | None = None
    segments_dir: Path | None = None
    audio_duration: float | None = None
    total_segments: int = 0
    speech_ranges: list[SpeechRange] = field(default_factory=list)
    cut_points: list[float] = field(default_factory=list)


# ============ 抽音频（独立阶段） ============

async def prepare_audio(video: VideoResult) -> Path:
    """从 video.mp4 抽 audio.mp3（已存在则复用）。

    VAD 不在此阶段跑 —— stream_audio_chunks 内部会边切边 VAD。
    """
    audio_path = video.path.parent / "audio.mp3"
    if not audio_path.exists():
        await _extract_full_audio(video.path, audio_path)
    return audio_path


async def _extract_full_audio(video_path: Path, audio_path: Path) -> None:
    """从 mp4 抽出 audio.mp3（16kHz mono q=4）"""
    cmd = [
        "ffmpeg",
        "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-vn",
        "-c:a", "libmp3lame",
        "-ar", "16000", "-ac", "1", "-q:a", "4",
        "-y", str(audio_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise StreamingPipelineError("ffmpeg 未安装") from e

    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise StreamingPipelineError(
            f"音频抽取失败: {stderr.decode(errors='ignore')[-200:]}"
        )


# ============ 主管道 ============

async def stream_audio_chunks(
    video: VideoResult,
    state: SegmentationState,
    target_segment: float = SEGMENT_DURATION,
    tolerance: float = SEGMENT_TOLERANCE,
) -> AsyncIterator[AudioChunk]:
    """对已下载 mp4 做"VAD + 增量切片"流式产出"""
    resource_dir = video.path.parent
    audio_path = resource_dir / "audio.mp3"
    segments_dir = resource_dir / SEGMENTS_DIRNAME
    segments_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = segments_dir / MANIFEST_FILENAME
    state.audio_path = audio_path
    state.segments_dir = segments_dir

    # 兜底抽音频（首次场景由 prepare_audio 完成，但测试可能直接进这里）
    if not audio_path.exists():
        logger.info("抽取全文音频: %s", audio_path)
        await _extract_full_audio(video.path, audio_path)

    duration = await asyncio.to_thread(_get_duration, audio_path)
    if duration is None or duration <= 0:
        raise StreamingPipelineError("音频时长解析失败")
    state.audio_duration = duration

    # === 切片缓存复用 ===
    cached = _load_manifest_if_valid(manifest_path, segments_dir)
    if cached is not None:
        logger.info("复用已有切片: %d 片", len(cached))
        state.total_segments = len(cached)
        state.cut_points = [c["end"] for c in cached[:-1]]
        for c in cached:
            yield AudioChunk(
                path=segments_dir / c["filename"],
                index=c["index"],
                start=float(c["start"]),
                end=float(c["end"]),
                is_last=bool(c["is_last"]),
            )
        return

    # === 单片场景：太短不切 ===
    if duration <= target_segment * 1.2:
        state.total_segments = 1
        chunk = AudioChunk(
            path=audio_path, index=0,
            start=0.0, end=duration, is_last=True,
        )
        _write_manifest(
            manifest_path,
            [_chunk_to_manifest(chunk, audio_path.name)],
        )
        yield chunk
        return

    # === 多片场景：清理旧切片 ===
    for p in segments_dir.glob("seg_*.mp3"):
        p.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)

    # === 流式 VAD + 增量切片 ===
    cuts_q: asyncio.Queue = asyncio.Queue()
    vad_task = asyncio.create_task(
        _stream_vad_and_emit_cuts(
            audio_path, duration, cuts_q, state,
            target_segment, tolerance,
        )
    )

    manifest_entries: list[dict] = []
    idx = 0
    try:
        while True:
            item = await cuts_q.get()
            if item is None:
                break
            seg_start, seg_end, is_last = item
            seg_path = segments_dir / f"seg_{idx:04d}.mp3"
            await _ffmpeg_cut_mp3(audio_path, seg_path, seg_start, seg_end)

            chunk = AudioChunk(
                path=seg_path, index=idx,
                start=seg_start, end=seg_end,
                is_last=is_last,
            )
            manifest_entries.append(_chunk_to_manifest(chunk, seg_path.name))
            yield chunk
            idx += 1
        state.total_segments = idx

        # 切完所有片才落 manifest（部分失败不留半截）
        _write_manifest(manifest_path, manifest_entries)

        # 等 VAD 任务正常退出（异常会从 .result() 抛出来）
        await vad_task

    except BaseException:
        # 异常或上游 cancel：清掉 VAD 任务
        if not vad_task.done():
            vad_task.cancel()
            try:
                await vad_task
            except (asyncio.CancelledError, Exception):
                pass
        raise


# ============ 流式 VAD + 增量切点 ============

async def _stream_vad_and_emit_cuts(
    audio_path: Path,
    duration: float,
    cuts_q: asyncio.Queue,
    state: SegmentationState,
    target_segment: float,
    tolerance: float,
) -> None:
    """边解码 PCM 边跑 VAD，每个目标切点一旦能定就 push 到 cuts_q

    push 内容：(start, end, is_last)，None 作为结束标记。
    """
    decode_proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-nostdin", "-loglevel", "error",
        "-i", str(audio_path),
        "-ar", str(_VAD_SAMPLE_RATE), "-ac", "1",
        "-f", "s16le", "-",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    speech_ranges: list[SpeechRange] = []
    cut_points: list[float] = []
    last_cut = 0.0
    next_target = target_segment
    processed_seconds = 0.0
    speech_state: dict = {"current_start": None}  # mutable holder for to_thread

    # 上次决策时已知的 silence 数量上限：tolerance 内的所有 silence 都已知
    # → 当 processed_seconds >= next_target + tolerance 时可决策

    try:
        async with _silero_lock:
            await asyncio.to_thread(_load_model)  # 预热（首次外部场景）
            from silero_vad import VADIterator

            model = _load_model()
            vad_iter = VADIterator(
                model,
                sampling_rate=_VAD_SAMPLE_RATE,
                threshold=0.5,
                min_silence_duration_ms=200,
            )

            buf = bytearray()
            assert decode_proc.stdout is not None
            while True:
                chunk = await decode_proc.stdout.read(_VAD_READ_BATCH_BYTES)
                if not chunk:
                    break
                buf.extend(chunk)

                # 收集完整帧批量送 VAD
                frames: list[bytes] = []
                while len(buf) >= _VAD_FRAME_BYTES:
                    frames.append(bytes(buf[:_VAD_FRAME_BYTES]))
                    del buf[:_VAD_FRAME_BYTES]
                if not frames:
                    continue

                new_ranges, samples_added = await asyncio.to_thread(
                    _vad_run_frames, vad_iter, frames, speech_state,
                )
                speech_ranges.extend(new_ranges)
                processed_seconds += samples_added / _VAD_SAMPLE_RATE

                # 决策可定切点
                while (
                    processed_seconds >= next_target + tolerance
                    and next_target < duration - MIN_SEGMENT_SECONDS
                ):
                    cut = _decide_cut(
                        speech_ranges,
                        next_target,
                        tolerance,
                        last_cut,
                        duration,
                    )
                    cut_points.append(cut)
                    await cuts_q.put((last_cut, cut, False))
                    last_cut = cut
                    next_target = cut + target_segment

            vad_iter.reset_states()

        # ffmpeg 完成；等进程收尾
        rc = await decode_proc.wait()
        if rc != 0:
            stderr = b""
            if decode_proc.stderr:
                stderr = await decode_proc.stderr.read()
            raise StreamingPipelineError(
                f"PCM 解码失败 ({rc}): {stderr.decode(errors='ignore')[-200:]}"
            )

        state.speech_ranges = speech_ranges
        state.cut_points = cut_points

        # 最后一段（last_cut → duration）
        await cuts_q.put((last_cut, duration, True))
        await cuts_q.put(None)

    except BaseException:
        if decode_proc.returncode is None:
            decode_proc.terminate()
            try:
                await asyncio.wait_for(decode_proc.wait(), timeout=5)
            except TimeoutError:
                decode_proc.kill()
                await decode_proc.wait()
        # 推 None 让消费者退出
        await cuts_q.put(None)
        raise


def _vad_run_frames(
    vad_iter, frames: list[bytes], speech_state: dict,
) -> tuple[list[SpeechRange], int]:
    """同步：批量推理一组 512-sample 帧；从 events 累积 SpeechRange"""
    import numpy as np
    import torch

    new_ranges: list[SpeechRange] = []
    samples_added = 0
    for frame_bytes in frames:
        arr = (
            np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        event = vad_iter(
            torch.from_numpy(arr.copy()), return_seconds=True
        )
        samples_added += _VAD_FRAME_SAMPLES
        if not event:
            continue
        if "start" in event:
            speech_state["current_start"] = float(event["start"])
        if "end" in event and speech_state["current_start"] is not None:
            new_ranges.append(
                SpeechRange(
                    start=speech_state["current_start"],
                    end=float(event["end"]),
                )
            )
            speech_state["current_start"] = None
    return new_ranges, samples_added


def _decide_cut(
    speech_ranges: list[SpeechRange],
    target: float,
    tolerance: float,
    last_cut: float,
    total_duration: float,
) -> float:
    """单点决策：在 [target - tolerance, target + tolerance] 内找最佳 silence 中点

    跟 plan_split_points 同源逻辑，但只决策一个点（增量场景）。
    """
    silences: list[tuple[float, float]] = []
    if speech_ranges:
        if speech_ranges[0].start > 0.05 and last_cut == 0.0:
            silences.append((0.0, speech_ranges[0].start))
        for i in range(len(speech_ranges) - 1):
            silences.append((speech_ranges[i].end, speech_ranges[i + 1].start))

    best: float | None = None
    for sil_start, sil_end in silences:
        sil_mid = (sil_start + sil_end) / 2
        if abs(sil_mid - target) > tolerance:
            continue
        if sil_mid <= last_cut + MIN_SEGMENT_SECONDS:
            continue
        if sil_mid >= total_duration - MIN_SEGMENT_SECONDS:
            continue
        if best is None or abs(sil_mid - target) < abs(best - target):
            best = sil_mid

    return best if best is not None else target


# ============ 切片 ============

async def _ffmpeg_cut_mp3(
    audio_path: Path, out_path: Path, start: float, end: float,
) -> None:
    """从 audio.mp3 切单段（input seek + c:a copy 不重新编码，毫秒级）

    精度：mp3 frame-aligned (~26ms)，对 STT 无影响。
    """
    duration = max(0.001, end - start)
    cmd = [
        "ffmpeg",
        "-nostdin", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}",
        "-i", str(audio_path),
        "-t", f"{duration:.3f}",
        "-c:a", "copy",
        "-y", str(out_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise StreamingPipelineError(
            f"切片失败 [{start:.1f}-{end:.1f}s]: "
            f"{stderr.decode(errors='ignore')[-200:]}"
        )
    if not out_path.exists() or out_path.stat().st_size < MIN_SEGMENT_BYTES:
        raise StreamingPipelineError(
            f"切片产物异常 [{start:.1f}-{end:.1f}s]: 文件不存在或过小"
        )


# ============ Manifest（切片缓存复用） ============

def _chunk_to_manifest(chunk: AudioChunk, filename: str) -> dict:
    return {
        "index": chunk.index,
        "filename": filename,
        "start": chunk.start,
        "end": chunk.end,
        "is_last": chunk.is_last,
    }


def _write_manifest(manifest_path: Path, entries: list[dict]) -> None:
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False), encoding="utf-8"
    )


def _load_manifest_if_valid(
    manifest_path: Path, segments_dir: Path,
) -> list[dict] | None:
    """加载 manifest 并验证文件齐全且非零 — 任一不满足则返回 None"""
    if not manifest_path.exists():
        return None
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(entries, list) or not entries:
        return None
    for e in entries:
        if not isinstance(e, dict):
            return None
        fname = e.get("filename")
        if not fname:
            return None
        p = segments_dir / fname
        if not p.exists() or p.stat().st_size < MIN_SEGMENT_BYTES:
            return None
    return entries
