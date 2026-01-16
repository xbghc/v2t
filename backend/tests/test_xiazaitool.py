"""xiazaitool API 测试"""

import pytest

from app.services.xiazaitool import XiazaitoolError, parse_video_url


@pytest.mark.asyncio
async def test_parse_video_url():
    """测试解析视频链接"""
    # 使用一个测试链接
    # 注意：需要配置有效的 XIAZAITOOL_TOKEN
    test_url = "https://www.bilibili.com/video/BV1xx411c7mD"

    try:
        result = await parse_video_url(test_url)
        print(f"标题: {result.title}")
        print(f"视频链接: {result.video_url}")
        print(f"封面: {result.cover_url}")
        assert result.title
        assert result.video_url
    except XiazaitoolError as e:
        # Token 未配置时跳过
        pytest.skip(f"跳过测试: {e}")


@pytest.mark.asyncio
async def test_parse_video_url_no_token():
    """测试未配置 token 时的错误处理"""
    from app.config import get_settings

    settings = get_settings()
    original_token = settings.xiazaitool_token

    # 临时清除 token
    settings.xiazaitool_token = ""

    try:
        with pytest.raises(XiazaitoolError, match="XIAZAITOOL_TOKEN 未配置"):
            await parse_video_url("https://example.com/video")
    finally:
        # 恢复 token
        settings.xiazaitool_token = original_token
