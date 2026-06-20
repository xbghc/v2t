"""time_stage 上下文管理器单测：成功/异常路径都要写 timings + 触发持久化"""

import asyncio

import pytest

from app.models.entities import Workspace
from app.tasks.workspace_task import time_stage


@pytest.fixture
def fake_persistence(monkeypatch):
    """收集 save / publish 调用次数，避免触达真 Redis"""
    saves: list[str] = []
    publishes: list[str] = []

    async def fake_save(ws: Workspace) -> None:
        saves.append(ws.workspace_id)

    async def fake_publish(ws: Workspace) -> None:
        publishes.append(ws.workspace_id)

    monkeypatch.setattr("app.tasks.workspace_task.save_workspace", fake_save)
    monkeypatch.setattr("app.tasks.workspace_task._publish_workspace", fake_publish)
    return saves, publishes


@pytest.mark.asyncio
async def test_time_stage_writes_key_on_success(fake_persistence):
    saves, publishes = fake_persistence
    ws = Workspace(workspace_id="ws-1")

    async with time_stage(ws, "download"):
        await asyncio.sleep(0.05)

    assert "download" in ws.timings
    assert ws.timings["download"] >= 0.04
    assert ws.timings["download"] < 1.0
    assert saves == ["ws-1"]
    assert publishes == ["ws-1"]


@pytest.mark.asyncio
async def test_time_stage_writes_key_on_exception(fake_persistence):
    saves, publishes = fake_persistence
    ws = Workspace(workspace_id="ws-2")

    with pytest.raises(RuntimeError, match="boom"):
        async with time_stage(ws, "stt_total"):
            await asyncio.sleep(0.02)
            raise RuntimeError("boom")

    # 即使抛异常也应该记录耗时，让失败的 workspace 也能在前端看到已完成阶段
    assert "stt_total" in ws.timings
    assert ws.timings["stt_total"] >= 0.01
    assert saves == ["ws-2"]
    assert publishes == ["ws-2"]


@pytest.mark.asyncio
async def test_time_stage_persistence_failure_does_not_swallow_original_exception(
    monkeypatch,
):
    """save 自身报错不能吞掉用户业务异常"""
    async def failing_save(ws: Workspace) -> None:
        raise ConnectionError("redis down")

    async def fake_publish(ws: Workspace) -> None:
        pass

    monkeypatch.setattr("app.tasks.workspace_task.save_workspace", failing_save)
    monkeypatch.setattr("app.tasks.workspace_task._publish_workspace", fake_publish)

    ws = Workspace(workspace_id="ws-3")
    with pytest.raises(ValueError, match="user-error"):
        async with time_stage(ws, "download"):
            raise ValueError("user-error")

    # timings 仍然写入了（finally 在 save 失败前已经执行）
    assert "download" in ws.timings
