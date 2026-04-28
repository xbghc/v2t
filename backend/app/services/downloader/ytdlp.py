"""yt-dlp 一步完成解析 + 下载（含代理转发）

目前覆盖 YouTube 域名；将来要扩 Twitter / Vimeo / TikTok 等只需扩展 _DOMAINS。
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from app.config import get_settings

from .base import DownloadError, DownloadMeta, ProgressCallback

logger = logging.getLogger(__name__)

_DOMAINS = ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com")


def _domain_matches(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in _DOMAINS)


def _do_download(
    url: str,
    outtmpl: str,
    proxy: str,
    progress_hook: Callable[[dict], None] | None,
) -> dict:
    """同步 yt-dlp 调用，必须在 to_thread 中执行"""
    opts: dict = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "concurrent_fragment_downloads": 16,
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "noprogress": True,  # 关闭 yt-dlp 自身的 stderr 进度条；hook 仍会被调用
    }
    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    if proxy:
        opts["proxy"] = proxy
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


class YtDlpProvider:
    """YouTube 一步到位（解析 + 分轨下载 + ffmpeg 合并 mp4）"""

    name = "yt-dlp"

    def supports(self, url: str) -> bool:
        return _domain_matches(urlparse(url).netloc.lower())

    async def download(
        self,
        url: str,
        save_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadMeta:
        proxy = get_settings().effective_proxy
        # outtmpl 留扩展名占位符给 yt-dlp，merge_output_format 决定最终 .mp4
        outtmpl = str(save_path.with_suffix("")) + ".%(ext)s"

        progress_hook: Callable[[dict], None] | None = None
        if progress_callback is not None:
            loop = asyncio.get_running_loop()

            def progress_hook(d: dict) -> None:
                """yt-dlp 在下载线程中调用；fire-and-forget 调度到主 loop。"""
                if d.get("status") != "downloading":
                    return
                downloaded = int(d.get("downloaded_bytes") or 0)
                total = int(
                    d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                )
                if total <= 0:
                    return
                asyncio.run_coroutine_threadsafe(
                    progress_callback(downloaded, total), loop
                )

        logger.info("yt-dlp 启动: %s (proxy=%s)", url, proxy or "<none>")
        try:
            info = await asyncio.to_thread(
                _do_download, url, outtmpl, proxy, progress_hook
            )
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
