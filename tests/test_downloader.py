"""视频下载测试"""

import pytest
from pathlib import Path

from app.services.video_downloader import (
    download_video,
    sanitize_filename,
    get_filename_from_url,
    DownloadError,
)


def test_sanitize_filename():
    """测试文件名清理"""
    assert sanitize_filename("hello world") == "hello world"
    assert sanitize_filename("hello<>world") == "hello__world"
    assert sanitize_filename('test:file"name') == "test_file_name"

    # 测试长文件名截断
    long_name = "a" * 300
    result = sanitize_filename(long_name)
    assert len(result) <= 200


def test_get_filename_from_url():
    """测试从 URL 提取文件名"""
    assert get_filename_from_url("https://example.com/video.mp4") == "video.mp4"
    assert get_filename_from_url("https://example.com/path/to/test.mp4") == "test.mp4"
    assert get_filename_from_url("https://example.com/no-extension") == "video.mp4"
    assert get_filename_from_url("https://example.com/") == "video.mp4"


@pytest.mark.asyncio
async def test_download_video():
    """测试视频下载（使用小文件测试）"""
    # 使用一个小的测试文件 URL
    test_url = "https://www.w3schools.com/html/mov_bbb.mp4"

    try:
        result = await download_video(test_url, filename="test_video.mp4")
        assert result.exists()
        assert result.stat().st_size > 0
        print(f"下载成功: {result}")

        # 清理测试文件
        result.unlink()
    except DownloadError as e:
        pytest.skip(f"下载测试跳过: {e}")
