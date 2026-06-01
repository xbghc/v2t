"""后台管理路由（仅供内部使用）

提供运营统计：全站 PV/UV 趋势、转录历史、处理质量（成功率 / 失败分类）。

⚠️ 无身份认证。与 /api/diag 一样，依赖部署层隔离：nginx-docker.conf 把
/api/admin/* 对公网一律 404，host 内通过 docker-compose 暴露的
127.0.0.1:8101 直连访问。生产环境务必确认 nginx 屏蔽生效。
"""

import logging

from fastapi import APIRouter, Query

from app.models.schemas import (
    AdminStatsResponse,
    HistoryItem,
    HistoryListResponse,
)
from app.storage import get_admin_stats, list_transcribe_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def stats(days: int = Query(14, ge=1, le=90)) -> AdminStatsResponse:
    """仪表盘汇总统计：累计 PV/UV、最近 N 天趋势、转录总数/成功率/失败分类。"""
    data = await get_admin_stats(days)
    return AdminStatsResponse(**data)


@router.get("/history", response_model=HistoryListResponse)
async def history(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> HistoryListResponse:
    """转录历史分页（finished_at 倒序），每条含各阶段耗时 timings。"""
    items, total = await list_transcribe_history(offset, limit)
    return HistoryListResponse(
        items=[HistoryItem(**it) for it in items],
        total=total,
        offset=offset,
        limit=limit,
    )
