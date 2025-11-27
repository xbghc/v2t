"""视频下载服务 - 使用 xiazaitool API + aria2c 多线程下载"""

import asyncio
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass
import re

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


async def download_file(
    url: str,
    video_url: str,
    title: str,
) -> VideoResult:
    """
    使用 aria2c 多线程下载视频文件

    Args:
        url: 原始视频页面链接（用于获取 referer）
        video_url: 直接下载链接
        title: 视频标题

    Returns:
        VideoResult: 下载结果
    """
    settings = get_settings()
    download_dir = settings.download_path

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
        "--console-log-level=warn",  # 减少输出
        "--summary-interval=0",  # 不显示摘要
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

    # 运行 aria2c
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await process.communicate()

        if process.returncode != 0:
            error_msg = stdout.decode() if stdout else "未知错误"
            raise DownloadError(f"aria2c 下载失败: {error_msg}")

        if not save_path.exists():
            raise DownloadError("下载完成但文件不存在")

        return VideoResult(path=save_path, title=title)

    except FileNotFoundError:
        raise DownloadError(
            "aria2c 未安装，请先安装:\n"
            "  macOS: brew install aria2\n"
            "  Ubuntu: sudo apt install aria2"
        )


async def download_video(url: str) -> VideoResult:
    """
    下载视频

    Args:
        url: 视频页面链接

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
    )
