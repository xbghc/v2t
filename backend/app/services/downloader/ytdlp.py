"""yt-dlp 一步完成解析 + 下载（含代理转发）

目前覆盖 YouTube 域名；将来要扩 Twitter / Vimeo / TikTok 等只需扩展 _DOMAINS。
"""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from app.config import get_settings

from .base import DownloadError, DownloadMeta

logger = logging.getLogger(__name__)

_DOMAINS = ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com")


def _domain_matches(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in _DOMAINS)


def _do_download(url: str, outtmpl: str, proxy: str) -> dict:
    """同步 yt-dlp 调用，必须在 to_thread 中执行"""
    opts = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "concurrent_fragment_downloads": 16,
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "noprogress": True,
    }
    if proxy:
        opts["proxy"] = proxy
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


class YtDlpProvider:
    """YouTube 一步到位（解析 + 分轨下载 + ffmpeg 合并 mp4）"""

    name = "yt-dlp"

    def supports(self, url: str) -> bool:
        return _domain_matches(urlparse(url).netloc.lower())

    async def download(self, url: str, save_path: Path) -> DownloadMeta:
        proxy = get_settings().effective_proxy
        # outtmpl 留扩展名占位符给 yt-dlp，merge_output_format 决定最终 .mp4
        outtmpl = str(save_path.with_suffix("")) + ".%(ext)s"

        logger.info("yt-dlp 启动: %s (proxy=%s)", url, proxy or "<none>")
        try:
            info = await asyncio.to_thread(_do_download, url, outtmpl, proxy)
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(f"yt-dlp 下载失败: {e}") from e
        except Exception as e:
            raise DownloadError(f"yt-dlp 异常: {e}") from e

        if not save_path.exists():
            raise DownloadError("yt-dlp 完成但 video.mp4 不存在（merge 可能失败）")

        if not isinstance(info, dict):
            return DownloadMeta(title="", duration=None, cover_url="")

        title = (info.get("title") or "").strip()
        duration_raw = info.get("duration")
        duration = (
            int(duration_raw) if isinstance(duration_raw, int | float) else None
        )
        thumbnail = info.get("thumbnail") or ""
        return DownloadMeta(title=title, duration=duration, cover_url=thumbnail)
