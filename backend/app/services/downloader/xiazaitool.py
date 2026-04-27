"""国内站点（B 站、抖音、快手、小红书…）通用：xiazaitool 解析 + aria2c 多线程下载"""

import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn

from app.services.xiazaitool import XiazaitoolError, parse_video_url

from .base import DownloadError, DownloadMeta

logger = logging.getLogger(__name__)


_REFERER_MAP = {
    "bilivideo.com": "https://www.bilibili.com/",
    "bilibili.com": "https://www.bilibili.com/",
    "douyinvod.com": "https://www.douyin.com/",
    "douyin.com": "https://www.douyin.com/",
    "kuaishou.com": "https://www.kuaishou.com/",
    "xiaohongshu.com": "https://www.xiaohongshu.com/",
}


def _get_referer(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    for key, referer in _REFERER_MAP.items():
        if key in domain:
            return referer
    return ""


def _parse_aria2c_progress(line: str) -> tuple[int, int] | None:
    """解析 aria2c 进度行，例如 `[#xxx 1.2MiB/10MiB(12%) ...]`"""
    match = re.search(r"\[#\w+ ([\d.]+)(\w+)/([\d.]+)(\w+)", line)
    if not match:
        return None
    multipliers = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}

    def to_bytes(value: str, unit: str) -> int:
        return int(float(value) * multipliers.get(unit.upper(), 1))

    return (
        to_bytes(match.group(1), match.group(2)),
        to_bytes(match.group(3), match.group(4)),
    )


async def _download_with_aria2c(
    page_url: str, video_url: str, save_path: Path
) -> None:
    download_dir = save_path.parent
    cmd = [
        "aria2c",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        "-d", str(download_dir),
        "-o", save_path.name,
        "--continue=true",
        "--auto-file-renaming=false",
        "--allow-overwrite=false",
        "--summary-interval=1",
    ]
    referer = _get_referer(video_url) or _get_referer(page_url)
    if referer:
        cmd.extend(["--referer", referer])
    cmd.extend([
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ])
    cmd.append(video_url)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        raise DownloadError(
            "aria2c 未安装：macOS `brew install aria2`，Ubuntu `apt install aria2`"
        )

    error_output: list[str] = []
    error_lines: list[str] = []
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("下载中", total=None)
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line_str = line.decode(errors="ignore")
            error_output.append(line_str)
            if any(kw in line_str for kw in ("[ERROR]", "errorCode=", "Exception")):
                error_lines.append(line_str.strip())
            result = _parse_aria2c_progress(line_str)
            if result:
                downloaded, total = result
                if progress.tasks[task].total is None:
                    progress.update(task, total=total)
                progress.update(task, completed=downloaded)

    await process.wait()
    if process.returncode != 0:
        msg = (
            "; ".join(error_lines)
            if error_lines
            else "".join(error_output[-5:]).strip()
        )
        raise DownloadError(msg)

    if not save_path.exists():
        # aria2c 偶尔会用上游指定的文件名落盘；把最新非 .aria2 文件改名过来
        recent = sorted(
            download_dir.iterdir(),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in recent:
            if f.is_file() and f.suffix != ".aria2":
                f.rename(save_path)
                return
        raise DownloadError("下载完成但文件不存在")


class XiazaitoolProvider:
    """xiazaitool API 拿直链 → aria2c 16 路并发下载"""

    name = "xiazaitool"

    def supports(self, url: str) -> bool:
        # xiazaitool 走通用 fallback；其他 provider 不接的都给它
        return True

    async def download(self, url: str, save_path: Path) -> DownloadMeta:
        try:
            info = await parse_video_url(url)
        except XiazaitoolError as e:
            raise DownloadError(str(e)) from e
        if not info.video_url:
            raise DownloadError("无法获取视频下载链接")
        await _download_with_aria2c(url, info.video_url, save_path)
        return DownloadMeta(title=info.title, cover_url=info.cover_url or "")
