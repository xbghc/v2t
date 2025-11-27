"""xiazaitool API 服务 - 解析视频链接"""

import httpx
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class VideoInfo:
    """视频信息"""
    title: str
    cover_url: str
    video_url: str
    is_video: bool
    like_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    create_time: str = ""
    pics: list[str] | None = None


class XiazaitoolError(Exception):
    """xiazaitool API 错误"""
    pass


async def parse_video_url(url: str) -> VideoInfo:
    """
    解析视频链接，获取下载地址

    Args:
        url: 视频页面链接

    Returns:
        VideoInfo: 视频信息

    Raises:
        XiazaitoolError: API 调用失败
    """
    settings = get_settings()

    if not settings.xiazaitool_token:
        raise XiazaitoolError("XIAZAITOOL_TOKEN 未配置")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.xiazaitool_api_url,
            json={
                "url": url,
                "token": settings.xiazaitool_token,
            }
        )

        data = response.json()

        if data.get("status") != 200 or not data.get("success"):
            raise XiazaitoolError(f"API 错误: {data}")

        result = data.get("data", {})

        return VideoInfo(
            title=result.get("title", ""),
            cover_url=result.get("coverUrls", ""),
            video_url=result.get("videoUrls", ""),
            is_video=result.get("isVideo", True),
            like_count=result.get("like", 0),
            comment_count=result.get("comment", 0),
            collect_count=result.get("collect", 0),
            create_time=result.get("createTime", ""),
            pics=result.get("pics"),
        )
