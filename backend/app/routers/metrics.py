"""页面访问埋点路由（公开，供前端 PV/UV 上报）

与 /api/diag、/api/admin 不同，这个端点 **不** 被 nginx 屏蔽——前端在每次
路由切换时 fire-and-forget 上报，需要公网可达。只接收计数，不返回任何数据。
"""

import logging

from fastapi import APIRouter, Response

from app.models.schemas import PageviewRequest
from app.storage import record_pageview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.post("/pageview", status_code=204)
async def pageview(req: PageviewRequest) -> Response:
    """记录一次页面访问。埋点失败绝不能影响前端，吞掉异常只记日志。"""
    try:
        path = (req.path or "")[:256]
        # /admin 自身访问不计入全站统计（前端也会跳过，这里双保险）
        if not path.startswith("/admin"):
            await record_pageview(path, req.visitor_id or "")
    except Exception:
        logger.warning("pageview 埋点失败", exc_info=True)
    return Response(status_code=204)
