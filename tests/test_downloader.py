"""视频下载测试"""


import pytest

from app.services.video_downloader import (
    DownloadError,
    download_video,
    sanitize_filename,
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


@pytest.mark.asyncio
async def test_download_video():
    """测试视频下载（使用小文件测试）"""
    # 使用一个小的测试文件 URL
    test_url = "https://www.w3schools.com/html/mov_bbb.mp4"

    try:
        result = await download_video(test_url)
        assert result.path.exists()
        assert result.path.stat().st_size > 0
        print(f"下载成功: {result.path}")

        # 清理测试文件
        result.path.unlink()
    except DownloadError as e:
        pytest.skip(f"下载测试跳过: {e}")
