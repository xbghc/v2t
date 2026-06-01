"""运营统计持久层（与 workspace 24h 易失存储正交，所有 key 不设 TTL）

记录全站 PV/UV、转录历史快照与处理质量计数，供后台管理页面读取。

与 RedisMetadataStore 的根本区别：workspace:* 是 24h 易失的（访问刷新、
无访问即过期），而这里的数据需要长期累积，因此一律 **不设 TTL**。转录历史
也必须把字段快照复制一份到 history:item:*，不能只存 id 再回查 workspace
（24h 后原 workspace 已不在）。
"""

import json
import logging
import time
from datetime import datetime, timedelta

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ---- Redis key（均无 TTL）----
_PV_TOTAL = "metrics:pv:total"        # String  累计总 PV
_PV_DAILY = "metrics:pv:daily"        # Hash    field=YYYY-MM-DD -> 当天 PV
_UV_TOTAL = "metrics:uv:total"        # HLL     全期独立访客
_UV_DAILY = "metrics:uv:daily:{date}"  # HLL     每天独立访客
_STATUS = "metrics:status"            # Hash    field=ready|failed -> 累计计数
_ERROR_KIND = "metrics:error_kind"    # Hash    field=error_kind -> 累计计数
_HISTORY_INDEX = "history:index"      # ZSet    score=finished_at, member=workspace_id
_HISTORY_ITEM = "history:item:{id}"   # Hash    持久快照


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class MetricsStore:
    """运营统计读写（PV/UV 埋点、转录历史、质量计数）。"""

    def __init__(self, redis: Redis):
        self._redis = redis

    # ---- PV / UV 埋点 ----

    async def record_pageview(self, path: str, visitor_id: str) -> None:
        """记录一次页面访问。path 暂仅作未来按页面下钻的预留（当前只统计全站）。"""
        date = _today()
        pipe = self._redis.pipeline()
        pipe.incr(_PV_TOTAL)
        pipe.hincrby(_PV_DAILY, date, 1)
        if visitor_id:
            pipe.pfadd(_UV_DAILY.format(date=date), visitor_id)
            pipe.pfadd(_UV_TOTAL, visitor_id)
        await pipe.execute()

    # ---- 转录历史 + 质量计数 ----

    async def record_workspace(self, snapshot: dict) -> None:
        """把一个进入终态的 workspace 快照写入持久历史，并累加质量计数。

        幂等：聚合计数器（status / error_kind）只在 **首次** 记录该 workspace 时
        +1，避免同一 workspace 万一重复终态把成功率算错；快照本身每次都覆盖刷新。
        """
        workspace_id = snapshot.get("workspace_id")
        if not workspace_id:
            return

        item_key = _HISTORY_ITEM.format(id=workspace_id)
        status = str(snapshot.get("status", ""))
        error_kind = str(snapshot.get("error_kind", "") or "")
        finished_at = float(snapshot.get("finished_at", time.time()))

        # 首次记录判定（同一 workspace 串行处理，并发翻倍风险可忽略）
        is_new = not await self._redis.exists(item_key)

        mapping = {
            "workspace_id": workspace_id,
            "url": str(snapshot.get("url", "")),
            "title": str(snapshot.get("title", "")),
            "status": status,
            "error_kind": error_kind,
            "created_at": str(snapshot.get("created_at", "") or ""),
            "finished_at": str(finished_at),
            "timings": json.dumps(snapshot.get("timings") or {}, ensure_ascii=False),
        }

        pipe = self._redis.pipeline()
        pipe.hset(item_key, mapping=mapping)
        pipe.zadd(_HISTORY_INDEX, {workspace_id: finished_at})
        if is_new and status:
            pipe.hincrby(_STATUS, status, 1)
            if status == "failed":
                pipe.hincrby(_ERROR_KIND, error_kind or "unknown", 1)
        await pipe.execute()

    # ---- 读取（后台管理页面）----

    async def get_stats(self, days: int = 14) -> dict:
        """汇总仪表盘统计：累计 PV/UV、最近 N 天趋势、转录总数/成功率/失败分类。"""
        days = max(1, min(days, 90))

        pv_total = await self._redis.get(_PV_TOTAL)
        uv_total = await self._redis.pfcount(_UV_TOTAL)
        pv_daily = await self._redis.hgetall(_PV_DAILY)
        status_counts = await self._redis.hgetall(_STATUS)
        error_kind_counts = await self._redis.hgetall(_ERROR_KIND)

        # 最近 days 天（旧 → 新），逐日 PFCOUNT 取 UV
        today = datetime.now().date()
        date_strs = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days - 1, -1, -1)
        ]
        pipe = self._redis.pipeline()
        for d in date_strs:
            pipe.pfcount(_UV_DAILY.format(date=d))
        uv_counts = await pipe.execute()

        daily = [
            {
                "date": d,
                "pv": int(pv_daily.get(d, 0) or 0),
                "uv": int(uv or 0),
            }
            for d, uv in zip(date_strs, uv_counts, strict=True)
        ]

        ready = int(status_counts.get("ready", 0) or 0)
        failed = int(status_counts.get("failed", 0) or 0)
        total = ready + failed
        success_rate = round(ready / total, 4) if total else 0.0

        return {
            "pv_total": int(pv_total or 0),
            "uv_total": int(uv_total or 0),
            "transcribe_total": total,
            "ready_count": ready,
            "failed_count": failed,
            "success_rate": success_rate,
            "error_kind": {k: int(v or 0) for k, v in error_kind_counts.items()},
            "daily": daily,
        }

    async def list_history(
        self, offset: int, limit: int
    ) -> tuple[list[dict], int]:
        """按 finished_at 倒序分页返回转录历史快照，返回 (items, total)。"""
        offset = max(0, offset)
        limit = max(1, min(limit, 200))

        total = await self._redis.zcard(_HISTORY_INDEX)
        if total == 0:
            return [], 0

        ids = await self._redis.zrevrange(
            _HISTORY_INDEX, offset, offset + limit - 1
        )
        if not ids:
            return [], total

        pipe = self._redis.pipeline()
        for wid in ids:
            pipe.hgetall(_HISTORY_ITEM.format(id=wid))
        rows = await pipe.execute()

        items = [self._row_to_item(raw) for raw in rows if raw]
        return items, total

    @staticmethod
    def _row_to_item(raw: dict) -> dict:
        try:
            timings = json.loads(raw.get("timings") or "{}")
            if not isinstance(timings, dict):
                timings = {}
        except (json.JSONDecodeError, TypeError):
            timings = {}

        def _to_float(key: str) -> float:
            try:
                return float(raw.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0

        return {
            "workspace_id": raw.get("workspace_id", ""),
            "url": raw.get("url", ""),
            "title": raw.get("title", ""),
            "status": raw.get("status", ""),
            "error_kind": raw.get("error_kind", ""),
            "created_at": _to_float("created_at"),
            "finished_at": _to_float("finished_at"),
            "timings": timings,
        }
