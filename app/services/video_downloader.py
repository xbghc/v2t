"""视频下载服务 - 使用 xiazaitool API + aria2c 多线程下载"""

import asyncio
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass
import re

from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

from app.config import get_settings
from app.services.xiazaitool import parse_video_url, XiazaitoolError


class DownloadError(Exception):
    """下载错误"""
    pass


@dataclass
class VideoResult:
    """下载结果"""
    path: Path
    title: str
    duration: int | None = None  # 秒


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    if len(filename) > 200:
        filename = filename[:200]
    return filename.strip()


def get_referer(url: str) -> str:
    """根据 URL 获取对应的 Referer"""
    domain = urlparse(url).netloc.lower()
    referer_map = {
        "bilivideo.com": "https://www.bilibili.com/",
        "bilibili.com": "https://www.bilibili.com/",
        "douyinvod.com": "https://www.douyin.com/",
        "douyin.com": "https://www.douyin.com/",
        "kuaishou.com": "https://www.kuaishou.com/",
        "xiaohongshu.com": "https://www.xiaohongshu.com/",
    }
    for key, referer in referer_map.items():
        if key in domain:
            return referer
    return ""


def parse_aria2c_progress(line: str) -> tuple[int, int] | None:
    """
    解析 aria2c 进度输出

    Args:
        line: aria2c 输出行

    Returns:
        (downloaded_bytes, total_bytes) 或 None
    """
    # 匹配格式: [#xxx 1.2MiB/10MiB(12%) ...]
    match = re.search(r'\[#\w+ ([\d.]+)(\w+)/([\d.]+)(\w+)', line)
    if not match:
        return None

    def to_bytes(value: str, unit: str) -> int:
        value = float(value)
        unit = unit.upper()
        multipliers = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}
        return int(value * multipliers.get(unit, 1))

    downloaded = to_bytes(match.group(1), match.group(2))
    total = to_bytes(match.group(3), match.group(4))
    return downloaded, total


async def download_file(
    url: str,
    video_url: str,
    title: str,
    output_dir: Path | None = None,
) -> VideoResult:
    """
    使用 aria2c 多线程下载视频文件

    Args:
        url: 原始视频页面链接（用于获取 referer）
        video_url: 直接下载链接
        title: 视频标题
        output_dir: 输出目录（默认使用临时目录）

    Returns:
        VideoResult: 下载结果
    """
    settings = get_settings()
    download_dir = output_dir or settings.temp_path

    save_name = f"{sanitize_filename(title)}.mp4" if title else "video.mp4"
    save_path = download_dir / save_name

    # 已存在则直接返回
    if save_path.exists():
        return VideoResult(path=save_path, title=title)

    # 构建 aria2c 命令
    cmd = [
        "aria2c",
        "-x", "16",  # 最大连接数
        "-s", "16",  # 分段数
        "-k", "1M",  # 最小分片大小
        "-d", str(download_dir),  # 下载目录
        "-o", save_name,  # 输出文件名
        "--continue=true",  # 断点续传
        "--auto-file-renaming=false",  # 不自动重命名
        "--allow-overwrite=false",  # 不覆盖
        "--summary-interval=1",  # 每秒更新进度
    ]

    # 添加 referer
    referer = get_referer(video_url) or get_referer(url)
    if referer:
        cmd.extend(["--referer", referer])

    # 添加 User-Agent
    cmd.extend([
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ])

    # 添加下载链接
    cmd.append(video_url)

    # 运行 aria2c 并显示进度
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        error_output = []
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

                # 解析进度
                result = parse_aria2c_progress(line_str)
                if result:
                    downloaded, total = result
                    if progress.tasks[task].total is None:
                        progress.update(task, total=total)
                    progress.update(task, completed=downloaded)

        await process.wait()

        if process.returncode != 0:
            error_msg = "".join(error_output[-10:])  # 只取最后几行
            raise DownloadError(f"aria2c 下载失败: {error_msg}")

        if not save_path.exists():
            # aria2c 可能使用了服务器指定的文件名，查找最新下载的文件
            recent_files = sorted(
                download_dir.iterdir(),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            # 找到最新的非 .aria2 文件
            downloaded_file = None
            for f in recent_files:
                if f.is_file() and not f.suffix == ".aria2":
                    downloaded_file = f
                    break

            if downloaded_file:
                # 重命名为预期的文件名
                downloaded_file.rename(save_path)
            else:
                raise DownloadError("下载完成但文件不存在")

        return VideoResult(path=save_path, title=title)

    except FileNotFoundError:
        raise DownloadError(
            "aria2c 未安装，请先安装:\n"
            "  macOS: brew install aria2\n"
            "  Ubuntu: sudo apt install aria2"
        )


async def download_video(url: str, output_dir: Path | None = None) -> VideoResult:
    """
    下载视频

    Args:
        url: 视频页面链接
        output_dir: 输出目录（默认使用临时目录）

    Returns:
        VideoResult: 下载结果

    Raises:
        DownloadError: 下载失败
    """
    try:
        video_info = await parse_video_url(url)
    except XiazaitoolError as e:
        raise DownloadError(str(e)) from e

    if not video_info.video_url:
        raise DownloadError("无法获取视频下载链接")

    return await download_file(
        url=url,
        video_url=video_info.video_url,
        title=video_info.title,
        output_dir=output_dir,
    )
