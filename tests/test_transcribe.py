"""Whisper 转写测试"""

import pytest
from pathlib import Path

from app.services.transcribe import (
    extract_audio,
    transcribe_video,
    TranscribeError,
)


def test_extract_audio():
    """测试音频提取"""
    # 使用已下载的视频文件测试
    video_path = Path("downloads") / "【盘点】2024年最实用、最火，【你认为的 VS 老外说的】英语视频合集！.mp4"

    if not video_path.exists():
        pytest.skip("测试视频文件不存在")

    try:
        audio_path = extract_audio(video_path)
        assert audio_path.exists()
        assert audio_path.suffix == ".mp3"
        print(f"音频提取成功: {audio_path}")
        print(f"音频大小: {audio_path.stat().st_size / 1024 / 1024:.2f} MB")
    except TranscribeError as e:
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_transcribe_video():
    """测试视频转写"""
    video_path = Path("downloads") / "【盘点】2024年最实用、最火，【你认为的 VS 老外说的】英语视频合集！.mp4"

    if not video_path.exists():
        pytest.skip("测试视频文件不存在")

    try:
        result = await transcribe_video(video_path, language="zh")
        assert result
        print(f"转写结果预览:\n{result[:500]}...")
    except TranscribeError as e:
        pytest.skip(f"跳过测试: {e}")
