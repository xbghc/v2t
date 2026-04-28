"""视频下载统一入口

调用方只关心：
    video = await download_video(url, output_dir=...)

具体走 yt-dlp / xiazaitool / 未来的 lux 等由 select_provider 路由（按 URL 域名 first-match）。

资源结构:
    {output_dir}/{url_hash}/
        meta.json     # 标题、时长、封面、provider 名
        video.mp4
"""

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.utils.url_hash import compute_url_hash, normalize_url

from .base import (
    DownloadError,
    DownloadMeta,
    ProgressCallback,
    VideoDownloadProvider,
    VideoResult,
)
from .xiazaitool import XiazaitoolProvider
from .ytdlp import YtDlpProvider

logger = logging.getLogger(__name__)


# 顺序敏感：先匹配特殊域名（YouTube 等），再 fallback 到通用 xiazaitool
_PROVIDERS: list[VideoDownloadProvider] = [
    YtDlpProvider(),
    XiazaitoolProvider(),
]


def select_provider(url: str) -> VideoDownloadProvider:
    """按 URL 路由 Provider；找不到时抛 DownloadError"""
    for provider in _PROVIDERS:
        if provider.supports(url):
            return provider
    raise DownloadError(f"未找到能处理该链接的下载器: {url}")


def _read_meta(meta_path: Path) -> dict | None:
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_meta(meta_path: Path, meta: dict) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def download_video(
    url: str,
    output_dir: Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> VideoResult:
    """下载视频，按 url_hash 命名文件并复用已有结果

    progress_callback 可选，仅在真正发起下载时由 Provider 触发；
    复用已有视频时不调用（直接返回缓存结果）。
    """
    settings = get_settings()
    base_dir = output_dir or settings.temp_path

    # 规范化 URL：剔除 tracking 参数（spm_id_from / vd_source / utm_* 等）。
    # 不仅用于 hash，也用于实际请求 —— 上游解析 API（xiazaitool）对带 tracker 的 URL 会 500。
    url = normalize_url(url)
    url_hash = compute_url_hash(url)
    resource_dir = base_dir / url_hash
    video_path = resource_dir / "video.mp4"
    meta_path = resource_dir / "meta.json"

    # 复用
    if video_path.exists():
        meta = _read_meta(meta_path)
        if resource_dir.exists():
            resource_dir.touch()
        logger.info("复用已有视频: %s", url_hash)
        duration_raw = meta.get("duration") if meta else None
        return VideoResult(
            path=video_path,
            title=meta.get("title", "") if meta else "",
            url_hash=url_hash,
            duration=int(duration_raw) if isinstance(duration_raw, int | float) else None,
        )

    resource_dir.mkdir(parents=True, exist_ok=True)
    provider = select_provider(url)
    logger.info("使用 %s 下载: %s", provider.name, url)

    download_meta = await provider.download(
        url, video_path, progress_callback=progress_callback
    )

    _write_meta(meta_path, {
        "url": url,
        "title": download_meta.title,
        "duration": download_meta.duration,
        "cover_url": download_meta.cover_url,
        "provider": provider.name,
    })

    return VideoResult(
        path=video_path,
        title=download_meta.title,
        url_hash=url_hash,
        duration=download_meta.duration,
    )


__all__ = [
    "DownloadError",
    "DownloadMeta",
    "ProgressCallback",
    "VideoDownloadProvider",
    "VideoResult",
    "download_video",
    "select_provider",
]
