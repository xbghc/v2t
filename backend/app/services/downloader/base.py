"""视频下载 Provider 协议 + 基础数据类型

调用方只与统一入口 (`app.services.downloader.download_video`) 对话；
具体走 yt-dlp / xiazaitool / 未来的 lux 等由 __init__.py 路由决定。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DownloadError(Exception):
    """下载失败"""


@dataclass
class VideoResult:
    """对外的下载结果（包含资源目录信息）"""

    path: Path
    title: str
    url_hash: str
    duration: int | None = None


@dataclass
class DownloadMeta:
    """Provider 完成下载后回报的最小元数据，由入口拼装到 meta.json / VideoResult"""

    title: str
    duration: int | None = None
    cover_url: str = ""


class VideoDownloadProvider(Protocol):
    """视频下载 Provider 接口

    实现可走任意路径（API 解析 + 多线程下载 / 一步到位 CLI / 等等），
    上层通过 `download_video` 路由到具体 Provider，对调用方透明。

    路由按 supports(url) first-match 选择。
    """

    name: str

    def supports(self, url: str) -> bool:
        """是否能处理该 URL（按域名/特征判断，纯字符串操作，不做 IO）"""

    async def download(self, url: str, save_path: Path) -> DownloadMeta:
        """下载到 save_path（mp4），返回元数据；失败必须抛 DownloadError"""
        ...
