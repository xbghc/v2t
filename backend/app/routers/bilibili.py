"""B 站相关辅助接口（探测分 P 列表等）"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.bilibili_meta import (
    BilibiliMetaError,
    fetch_video_meta,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bilibili", tags=["bilibili"])


class BilibiliPageResponse(BaseModel):
    page: int
    cid: int
    title: str
    duration: int
    url: str


class BilibiliVideoMetaResponse(BaseModel):
    bvid: str
    title: str
    owner: str
    cover_url: str
    pages: list[BilibiliPageResponse]


@router.get("/pages", response_model=BilibiliVideoMetaResponse)
async def get_pages(url: str) -> BilibiliVideoMetaResponse:
    """
    获取 B 站视频的分 P 列表。

    入参可以是完整页面 URL（含或不含查询串）或 BV 号字符串。
    返回：视频系列标题、UP 主、封面、每个分 P 的 page/cid/标题/时长/URL。
    """
    try:
        meta = await fetch_video_meta(url)
    except BilibiliMetaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return BilibiliVideoMetaResponse(
        bvid=meta.bvid,
        title=meta.title,
        owner=meta.owner,
        cover_url=meta.cover_url,
        pages=[
            BilibiliPageResponse(
                page=p.page,
                cid=p.cid,
                title=p.title,
                duration=p.duration,
                url=p.url,
            )
            for p in meta.pages
        ],
    )
