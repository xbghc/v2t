"""端到端 smoke 测试：process_workspace 流式管道串联

mock 掉网络相关：
    - download_video → 返回指向预合成 mp4 的 VideoResult
    - STT provider transcribe_chunk → 假 segments
    - Redis（hash/list/pubsub）+ FileStorage → 内存版

真用：silero-vad、ffmpeg（VAD + 切片）。

验证：
    - 状态序列 pending → processing(多次) → ready
    - 三个资源都 ready=True 且按顺序 emit
    - SSE envelope 同时包含 workspace 与 transcript.append 两种 type
    - transcript.txt 落盘内容包含每段
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.models.entities import Workspace
from app.models.enums import WorkspaceStatus
from app.services.downloader import VideoResult
from app.services.stt.base import (
    AudioChunk,
    TranscribeContext,
    TranscriptSegment,
)


@pytest.fixture
def synthetic_mp4(tmp_path: Path) -> Path:
    """合成一段 70s 含 sine 波音频的 mp4（含视频流，模拟真 mp4 容器）"""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    out = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=70",
            "-f", "lavfi", "-i", "color=size=320x240:rate=10:duration=70",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            "-shortest",
            str(out),
        ],
        check=True,
    )
    return out


class _FakeRedis:
    """收集 pub/sub 消息；hash/list 操作用 dict 模拟"""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))


class _FakeStorage:
    """内存版 LocalFileStorage（仅 smoke 用到的方法）"""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def save_file(self, key: str, local_path: Path) -> None:
        self.files[key] = Path(local_path).read_bytes()

    async def save_bytes(self, key: str, data: bytes) -> None:
        self.files[key] = data

    async def get_bytes(self, key: str) -> bytes:
        return self.files[key]


class _FakeProvider:
    """假 STT Provider：每个切片产出 1 段 fake transcript"""

    name = "fake"

    async def is_available(self) -> tuple[bool, str]:
        return True, "OK"

    async def transcribe_chunk(
        self,
        chunk: AudioChunk,
        context: TranscribeContext,
    ) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                start=chunk.start,
                end=chunk.end,
                text=f"fake-text-{chunk.index}",
                chunk_index=chunk.index,
            )
        ]


@pytest.fixture
def smoke_env(tmp_path: Path, synthetic_mp4: Path, monkeypatch):
    """搭建 smoke 测试环境，返回 (workspaces dict, redis 收集器, storage, video_path)"""
    workspaces: dict[str, Workspace] = {}
    redis = _FakeRedis()
    storage = _FakeStorage()

    async def fake_get_workspace(wid: str) -> Workspace | None:
        return workspaces.get(wid)

    async def fake_save_workspace(ws: Workspace) -> None:
        workspaces[ws.workspace_id] = ws

    # 把 download_video 的产物落到 tmp_path 下，stream_audio_chunks 会用同目录
    video_dir = tmp_path / "abc12345"
    video_dir.mkdir()
    video_path = video_dir / "video.mp4"
    video_path.write_bytes(synthetic_mp4.read_bytes())

    async def fake_download_video(url: str, output_dir: Path | None = None, progress_callback=None):
        return VideoResult(
            path=video_path, title="Smoke Test", url_hash="abc12345",
            duration=70,
        )

    # patch workspace_task 中通过名字 import 的符号
    monkeypatch.setattr(
        "app.tasks.workspace_task.get_workspace", fake_get_workspace
    )
    monkeypatch.setattr(
        "app.tasks.workspace_task.save_workspace", fake_save_workspace
    )
    monkeypatch.setattr("app.tasks.workspace_task.get_redis", lambda: redis)
    monkeypatch.setattr(
        "app.tasks.workspace_task.get_file_storage", lambda: storage
    )
    monkeypatch.setattr(
        "app.tasks.workspace_task.download_video", fake_download_video
    )
    # build_workspace_response 内部读取 TEXT content 时也用 storage
    monkeypatch.setattr("app.utils.response.get_file_storage", lambda: storage)

    # 把 STT router 的 candidate 列表 mock 成只有假 provider
    from app.services.stt.router import reset_router
    reset_router()
    monkeypatch.setattr(
        "app.services.stt.router._build_candidates",
        lambda: [_FakeProvider()],
    )

    # 让 max_video_duration 不卡 70s 测试音频
    from app.config import get_settings

    get_settings().max_video_duration = 7200
    get_settings().temp_dir = str(tmp_path)

    return workspaces, redis, storage, video_path


@pytest.mark.asyncio
async def test_process_workspace_end_to_end(smoke_env):
    workspaces, redis, storage, _ = smoke_env

    workspace_id = "ws-smoke-001"
    workspaces[workspace_id] = Workspace(workspace_id=workspace_id, url="https://x")

    from app.tasks.workspace_task import process_workspace

    await process_workspace(workspace_id, "https://x")

    final = workspaces[workspace_id]
    assert final.status == WorkspaceStatus.READY, (
        f"最终状态非 READY: {final.status} (error={final.error})"
    )
    assert final.title == "Smoke Test"

    # 资源顺序 video → transcript（音频是流式管道内部细节，不单独 emit）
    names = [r.name for r in final.resources]
    assert names == ["video", "transcript"]
    assert all(r.ready for r in final.resources)

    # transcript 文件落盘了
    transcript_key = next(
        r.storage_key for r in final.resources if r.name == "transcript"
    )
    assert transcript_key
    transcript_text = storage.files[transcript_key].decode("utf-8")
    assert "fake-text-0" in transcript_text

    # SSE envelope：包含 workspace + transcript.append 两种类型
    types = []
    for _, msg in redis.published:
        env = json.loads(msg)
        types.append(env["type"])
    assert "workspace" in types
    assert "transcript.append" in types

    # 工作区状态推送序列：第一条 processing，最后一条 ready
    workspace_msgs = [
        json.loads(msg)["data"]
        for _, msg in redis.published
        if json.loads(msg)["type"] == "workspace"
    ]
    statuses = [m["status"] for m in workspace_msgs]
    assert statuses[0] == "processing"
    assert statuses[-1] == "ready"
    assert "failed" not in statuses

    # transcript.append 至少有 1 条（70s 视频按 30s 切应有 2-3 片）
    seg_msgs = [
        json.loads(msg)["data"]
        for _, msg in redis.published
        if json.loads(msg)["type"] == "transcript.append"
    ]
    assert len(seg_msgs) >= 1
    assert all("fake-text-" in s["text"] for s in seg_msgs)
