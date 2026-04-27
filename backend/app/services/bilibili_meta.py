"""B 站视频元信息服务 - 通过官方 API 获取分 P 列表等"""

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
_BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BilibiliMetaError(Exception):
    """B 站元信息查询错误"""

    pass


@dataclass
class BilibiliPage:
    """单个分 P 信息"""

    page: int  # 1-based 序号
    cid: int
    title: str  # 分 P 标题（"第01讲 ..."）
    duration: int  # 秒
    url: str  # 完整分 P URL


@dataclass
class BilibiliVideoMeta:
    """B 站视频元信息"""

    bvid: str
    title: str  # 系列总标题
    owner: str  # UP 主名
    cover_url: str
    pages: list[BilibiliPage]


def extract_bvid(url_or_bvid: str) -> str | None:
    """从 URL 或 BV 号字符串中提取 BV 号"""
    match = _BVID_RE.search(url_or_bvid)
    return match.group(0) if match else None


async def fetch_video_meta(url_or_bvid: str) -> BilibiliVideoMeta:
    """
    获取 B 站视频的元信息（含分 P 列表）

    Args:
        url_or_bvid: 视频页面 URL 或 BV 号

    Returns:
        BilibiliVideoMeta

    Raises:
        BilibiliMetaError: 解析失败或 API 错误
    """
    bvid = extract_bvid(url_or_bvid)
    if not bvid:
        raise BilibiliMetaError(f"无法从输入中识别 BV 号: {url_or_bvid}")

    headers = {"User-Agent": _UA, "Referer": "https://www.bilibili.com/"}
    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.get(_VIEW_API, params={"bvid": bvid})
    except httpx.HTTPError as e:
        raise BilibiliMetaError(f"请求 B 站 API 失败: {e}") from e

    try:
        payload = response.json()
    except ValueError as e:
        raise BilibiliMetaError(f"B 站 API 响应非 JSON: {e}") from e

    code = payload.get("code")
    if code != 0:
        msg = payload.get("message", "未知错误")
        raise BilibiliMetaError(f"B 站 API 返回错误 (code={code}): {msg}")

    data = payload.get("data") or {}
    raw_pages = data.get("pages") or []
    if not raw_pages:
        raise BilibiliMetaError("视频不存在或未返回分 P 列表")

    pages = [
        BilibiliPage(
            page=p["page"],
            cid=p["cid"],
            title=p.get("part") or f"P{p['page']}",
            duration=int(p.get("duration") or 0),
            url=f"https://www.bilibili.com/video/{bvid}?p={p['page']}",
        )
        for p in raw_pages
    ]

    return BilibiliVideoMeta(
        bvid=bvid,
        title=data.get("title", ""),
        owner=(data.get("owner") or {}).get("name", ""),
        cover_url=data.get("pic", ""),
        pages=pages,
    )
