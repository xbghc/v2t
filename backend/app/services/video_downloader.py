"""视频下载服务 - 使用 xiazaitool API + aria2c 多线程下载"""

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn

from app.config import get_settings
from app.utils.url_hash import compute_url_hash

from .xiazaitool import XiazaitoolError, parse_video_url

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """下载错误"""

    pass


@dataclass
class VideoResult:
    """下载结果"""

    path: Path
    title: str
    url_hash: str
    duration: float | None = None  # 秒


def get_remote_video_duration(video_url: str, referer: str = "") -> float | None:
    """获取远程视频时长（秒）"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
    ]

    # 添加 Headers (User-Agent 和 Referer)
    headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    if referer:
        headers += f"\r\nReferer: {referer}"

    cmd.extend(["-headers", headers])
    cmd.append(video_url)

    try:
        # 设置超时防止卡死
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        logger.warning("ffprobe 获取时长失败: %s", e)

    return None


def get_local_video_duration(video_path: Path) -> float | None:
    """获取本地视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        logger.warning("ffprobe 获取本地时长失败: %s", e)
    return None


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
    match = re.search(r"\[#\w+ ([\d.]+)(\w+)/([\d.]+)(\w+)", line)
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


def _read_meta(resource_dir: Path) -> dict | None:
    """读取资源目录的元数据"""
    meta_path = resource_dir / "meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_meta(resource_dir: Path, meta: dict) -> None:
    """写入资源目录的元数据"""
    resource_dir.mkdir(parents=True, exist_ok=True)
    meta_path = resource_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _touch_dir(resource_dir: Path) -> None:
    """更新目录的访问时间"""
    if resource_dir.exists():
        resource_dir.touch()


async def _download_with_aria2c(
    url: str,
    video_url: str,
    save_path: Path,
) -> None:
    """
    使用 aria2c 多线程下载视频文件

    Args:
        url: 原始视频页面链接（用于获取 referer）
        video_url: 直接下载链接
        save_path: 保存路径
    """
    download_dir = save_path.parent
    save_name = save_path.name

    # 构建 aria2c 命令
    cmd = [
        "aria2c",
        "-x",
        "16",  # 最大连接数
        "-s",
        "16",  # 分段数
        "-k",
        "1M",  # 最小分片大小
        "-d",
        str(download_dir),  # 下载目录
        "-o",
        save_name,  # 输出文件名
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

    except FileNotFoundError:
        raise DownloadError(
            "aria2c 未安装，请先安装:\n"
            "  macOS: brew install aria2\n"
            "  Ubuntu: sudo apt install aria2"
        )


async def download_video(url: str, output_dir: Path | None = None) -> VideoResult:
    """
    下载视频，支持文件复用。

    文件组织结构：
        {output_dir}/{url_hash}/
            meta.json     # 元数据（标题、URL等）
            video.mp4     # 视频文件

    如果视频已存在，直接返回复用；否则下载并保存。

    Args:
        url: 视频页面链接
        output_dir: 输出目录（默认使用临时目录）

    Returns:
        VideoResult: 下载结果

    Raises:
        DownloadError: 下载失败
    """
    settings = get_settings()
    base_dir = output_dir or settings.temp_path

    # 计算 URL 哈希
    url_hash = compute_url_hash(url)
    resource_dir = base_dir / url_hash
    video_path = resource_dir / "video.mp4"

    # 检查是否已存在（复用）
    if video_path.exists():
        meta = _read_meta(resource_dir)
        title = meta.get("title", "") if meta else ""
        duration = meta.get("duration") if meta else None

        # 如果元数据没有时长，尝试从本地文件获取
        if duration is None:
            duration = get_local_video_duration(video_path)
            if duration and meta:
                meta["duration"] = duration
                _write_meta(resource_dir, meta)

        # 复用时也检查时长限制（防止历史下载的大文件被错误处理）
        if duration and duration > settings.max_video_duration:
            max_min = settings.max_video_duration // 60
            video_min = int(duration // 60)
            raise DownloadError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟（复用）")

        _touch_dir(resource_dir)  # 更新访问时间
        logger.info("复用已有视频: %s", url_hash)
        return VideoResult(
            path=video_path,
            title=title,
            url_hash=url_hash,
            duration=duration,
        )

    # 解析视频链接
    try:
        video_info = await parse_video_url(url)
    except XiazaitoolError as e:
        raise DownloadError(str(e)) from e

    if not video_info.video_url:
        raise DownloadError("无法获取视频下载链接")

    # 获取视频时长并检查限制
    referer = get_referer(video_info.video_url) or get_referer(url)
    duration = get_remote_video_duration(video_info.video_url, referer)

    if duration and duration > settings.max_video_duration:
        max_min = settings.max_video_duration // 60
        video_min = int(duration // 60)
        raise DownloadError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

    # 创建目录并保存元数据
    resource_dir.mkdir(parents=True, exist_ok=True)
    _write_meta(
        resource_dir,
        {
            "url": url,
            "title": video_info.title,
            "cover_url": video_info.cover_url,
            "duration": duration,
        },
    )

    # 下载视频
    await _download_with_aria2c(
        url=url,
        video_url=video_info.video_url,
        save_path=video_path,
    )

    # 如果远程获取时长失败，下载后再次检查
    if duration is None:
        duration = get_local_video_duration(video_path)
        if duration:
            # 更新元数据
            _write_meta(
                resource_dir,
                {
                    "url": url,
                    "title": video_info.title,
                    "cover_url": video_info.cover_url,
                    "duration": duration,
                },
            )

            # 检查限制
            if duration > settings.max_video_duration:
                # 删除文件
                try:
                    video_path.unlink()
                except OSError:
                    pass
                max_min = settings.max_video_duration // 60
                video_min = int(duration // 60)
                raise DownloadError(f"视频时长 {video_min} 分钟，超过限制 {max_min} 分钟")

    return VideoResult(
        path=video_path,
        title=video_info.title,
        url_hash=url_hash,
        duration=duration,
    )
