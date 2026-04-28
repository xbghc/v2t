"""streaming_pipeline 切片产出测试

用 ffmpeg lavfi 生成静音音频作为伪视频输入，无外部依赖。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.streaming_pipeline import (
    SegmentationState,
    stream_audio_chunks,
)
from app.services.downloader import VideoResult


@pytest.fixture
def synthetic_video(tmp_path) -> Path:
    """合成 120s 静音 m4a 作为伪视频（stream_audio_chunks 用 -vn 抽音频，对容器不挑）"""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    out = tmp_path / "src.m4a"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi",
            "-i", "anullsrc=cl=mono:r=16000",
            "-t", "120",
            "-c:a", "aac",
            str(out),
        ],
        check=True,
    )
    return out


@pytest.mark.asyncio
async def test_stream_audio_chunks_yields_30s_segments(synthetic_video, tmp_path):
    """120s 输入应当产出 4 个切片，时间戳与 is_last 正确"""
    resource_dir = tmp_path / "abc123"
    resource_dir.mkdir()
    video_path = resource_dir / "video.mp4"
    video_path.write_bytes(synthetic_video.read_bytes())

    video = VideoResult(path=video_path, title="t", url_hash="abc123")
    state = SegmentationState()

    chunks = [c async for c in stream_audio_chunks(video, state)]

    # VAD 切点会在 ±5s 容差内贴到自然 silence 中点，所以时间戳不一定是整 30s
    assert len(chunks) == 4
    assert [c.index for c in chunks] == [0, 1, 2, 3]
    assert chunks[0].start == 0.0
    for prev, cur in zip(chunks, chunks[1:]):
        gap = cur.start - prev.start
        assert 25.0 <= gap <= 35.0, f"切片间距 {gap} 超出容差"
    assert [c.is_last for c in chunks] == [False, False, False, True]
    assert state.audio_duration == pytest.approx(120.0, abs=2)
    assert state.total_segments == 4
    assert all(c.path.exists() and c.path.suffix == ".mp3" for c in chunks)


@pytest.mark.asyncio
async def test_stream_audio_chunks_reuses_existing(synthetic_video, tmp_path):
    """已有切片目录应直接复用，不重新跑 ffmpeg"""
    resource_dir = tmp_path / "reuse"
    resource_dir.mkdir()
    video_path = resource_dir / "video.mp4"
    video_path.write_bytes(synthetic_video.read_bytes())
    video = VideoResult(path=video_path, title="t", url_hash="reuse")

    state1 = SegmentationState()
    first = [c async for c in stream_audio_chunks(video, state1)]
    mtimes1 = [c.path.stat().st_mtime for c in first]

    state2 = SegmentationState()
    second = [c async for c in stream_audio_chunks(video, state2)]
    mtimes2 = [c.path.stat().st_mtime for c in second]

    assert mtimes1 == mtimes2
    assert len(second) == 4
    assert second[-1].is_last
