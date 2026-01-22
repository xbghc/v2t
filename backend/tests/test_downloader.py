"""视频下载测试"""

import shutil

import pytest

from app.services.video_downloader import (
    DownloadError,
    download_video,
)


@pytest.mark.asyncio
async def test_download_video():
    """测试视频下载（使用小文件测试）"""
    # 使用一个小的测试文件 URL
    test_url = "https://www.w3schools.com/html/mov_bbb.mp4"

    try:
        result = await download_video(test_url)
        assert result.path.exists()
        assert result.path.stat().st_size > 0
        assert result.url_hash  # 应该有 url_hash
        print(f"下载成功: {result.path}, url_hash: {result.url_hash}")

        # 清理测试目录（url_hash 目录）
        shutil.rmtree(result.path.parent, ignore_errors=True)
    except DownloadError as e:
        pytest.skip(f"下载测试跳过: {e}")
