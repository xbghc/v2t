"""MetricsStore 单元测试：用内存版 FakeRedis，不依赖真实 Redis。"""

import pytest

from app.storage.metrics_store import MetricsStore


class FakeRedis:
    """覆盖 MetricsStore 用到的命令的内存假 Redis（含 pipeline）。

    HyperLogLog 用 set 精确模拟（测试不关心 HLL 的近似误差）；
    zset 用 {member: score} dict，zrevrange 按 score 降序。
    """

    def __init__(self) -> None:
        self.store: dict = {}

    # ---- 同步核心 ----
    def _incr(self, key):
        v = int(self.store.get(key, 0)) + 1
        self.store[key] = str(v)
        return v

    def _hincrby(self, key, field, n=1):
        h = self.store.setdefault(key, {})
        h[field] = str(int(h.get(field, 0)) + n)
        return int(h[field])

    def _pfadd(self, key, *values):
        s = self.store.setdefault(key, set())
        before = len(s)
        s.update(values)
        return int(len(s) != before)

    def _pfcount(self, *keys):
        merged: set = set()
        for k in keys:
            merged |= self.store.get(k, set())
        return len(merged)

    def _get(self, key):
        return self.store.get(key)

    def _hgetall(self, key):
        return dict(self.store.get(key, {}))

    def _exists(self, key):
        return 1 if key in self.store else 0

    def _hset(self, key, mapping=None):
        h = self.store.setdefault(key, {})
        if mapping:
            h.update({k: str(v) for k, v in mapping.items()})
        return len(mapping or {})

    def _zadd(self, key, mapping):
        z = self.store.setdefault(key, {})
        z.update(mapping)
        return len(mapping)

    def _zcard(self, key):
        return len(self.store.get(key, {}))

    def _zrevrange(self, key, start, end):
        z = self.store.get(key, {})
        ordered = [m for m, _ in sorted(z.items(), key=lambda kv: (-kv[1], kv[0]))]
        if end == -1:
            return ordered[start:]
        return ordered[start : end + 1]

    # ---- async 接口 ----
    async def incr(self, key):
        return self._incr(key)

    async def hincrby(self, key, field, n=1):
        return self._hincrby(key, field, n)

    async def pfadd(self, key, *values):
        return self._pfadd(key, *values)

    async def pfcount(self, *keys):
        return self._pfcount(*keys)

    async def get(self, key):
        return self._get(key)

    async def hgetall(self, key):
        return self._hgetall(key)

    async def exists(self, key):
        return self._exists(key)

    async def zcard(self, key):
        return self._zcard(key)

    async def zrevrange(self, key, start, end):
        return self._zrevrange(key, start, end)

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    """缓冲命令，execute() 时按序对 FakeRedis 同步核心执行，返回结果列表。"""

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple, dict]] = []

    def incr(self, key):
        self._ops.append(("_incr", (key,), {}))
        return self

    def hincrby(self, key, field, n=1):
        self._ops.append(("_hincrby", (key, field, n), {}))
        return self

    def pfadd(self, key, *values):
        self._ops.append(("_pfadd", (key, *values), {}))
        return self

    def pfcount(self, *keys):
        self._ops.append(("_pfcount", keys, {}))
        return self

    def hset(self, key, mapping=None):
        self._ops.append(("_hset", (key,), {"mapping": mapping}))
        return self

    def zadd(self, key, mapping):
        self._ops.append(("_zadd", (key, mapping), {}))
        return self

    def hgetall(self, key):
        self._ops.append(("_hgetall", (key,), {}))
        return self

    async def execute(self):
        return [
            getattr(self._redis, name)(*args, **kwargs)
            for name, args, kwargs in self._ops
        ]


@pytest.fixture
def store() -> MetricsStore:
    return MetricsStore(FakeRedis())


# ---- PV / UV ----


@pytest.mark.asyncio
async def test_pageview_pv_uv_accumulate(store):
    await store.record_pageview("/", "visitor-a")
    await store.record_pageview("/w/1", "visitor-b")
    await store.record_pageview("/", "visitor-a")  # 同访客重复一次

    stats = await store.get_stats(days=1)
    assert stats["pv_total"] == 3
    assert stats["uv_total"] == 2  # a、b 去重
    assert len(stats["daily"]) == 1
    assert stats["daily"][0]["pv"] == 3
    assert stats["daily"][0]["uv"] == 2


@pytest.mark.asyncio
async def test_pageview_uv_dedup_same_visitor(store):
    for _ in range(5):
        await store.record_pageview("/", "same")
    stats = await store.get_stats(days=1)
    assert stats["pv_total"] == 5
    assert stats["uv_total"] == 1


@pytest.mark.asyncio
async def test_pageview_no_visitor_id_counts_pv_only(store):
    await store.record_pageview("/", "")
    stats = await store.get_stats(days=1)
    assert stats["pv_total"] == 1
    assert stats["uv_total"] == 0


# ---- 转录历史 + 质量计数 ----


@pytest.mark.asyncio
async def test_record_workspace_success_and_stats(store):
    await store.record_workspace(
        {
            "workspace_id": "ws-1", "url": "u1", "title": "T1",
            "status": "ready", "error_kind": "", "created_at": 100.0,
            "finished_at": 200.0, "timings": {"total": 12.5},
        }
    )
    await store.record_workspace(
        {
            "workspace_id": "ws-2", "url": "u2", "title": "T2",
            "status": "failed", "error_kind": "download_failed",
            "created_at": 150.0, "finished_at": 250.0, "timings": {},
        }
    )
    stats = await store.get_stats()
    assert stats["transcribe_total"] == 2
    assert stats["ready_count"] == 1
    assert stats["failed_count"] == 1
    assert stats["success_rate"] == 0.5
    assert stats["error_kind"] == {"download_failed": 1}


@pytest.mark.asyncio
async def test_record_workspace_idempotent(store):
    snap = {
        "workspace_id": "ws-1", "status": "ready", "error_kind": "",
        "created_at": 1.0, "finished_at": 2.0, "timings": {},
    }
    await store.record_workspace(snap)
    await store.record_workspace(snap)  # 二次终态不应让计数翻倍
    await store.record_workspace(snap)
    stats = await store.get_stats()
    assert stats["ready_count"] == 1
    assert stats["transcribe_total"] == 1


@pytest.mark.asyncio
async def test_record_workspace_failed_blank_kind_falls_back_unknown(store):
    await store.record_workspace(
        {
            "workspace_id": "ws-x", "status": "failed", "error_kind": "",
            "created_at": 1.0, "finished_at": 2.0, "timings": {},
        }
    )
    stats = await store.get_stats()
    assert stats["error_kind"] == {"unknown": 1}
    assert stats["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_list_history_pagination_desc(store):
    for i in range(5):
        await store.record_workspace(
            {
                "workspace_id": f"ws-{i}", "url": f"u{i}", "title": f"T{i}",
                "status": "ready", "error_kind": "", "created_at": float(i),
                "finished_at": float(i * 10), "timings": {"total": float(i)},
            }
        )
    items, total = await store.list_history(offset=0, limit=2)
    assert total == 5
    assert [it["workspace_id"] for it in items] == ["ws-4", "ws-3"]
    assert items[0]["timings"] == {"total": 4.0}  # JSON 往返正确

    items2, _ = await store.list_history(offset=2, limit=2)
    assert [it["workspace_id"] for it in items2] == ["ws-2", "ws-1"]


@pytest.mark.asyncio
async def test_list_history_empty(store):
    items, total = await store.list_history(0, 50)
    assert items == []
    assert total == 0
