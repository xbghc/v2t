"""系统依赖检查"""

import shutil

REQUIRED_DEPS = [
    ("ffmpeg", "音频提取"),
    ("aria2c", "视频下载"),
]


class DependencyError(Exception):
    """系统依赖缺失错误"""

    pass


def check_dependencies() -> list[tuple[str, str]]:
    """检查系统依赖，返回缺失的依赖列表

    Returns:
        缺失依赖的列表，每项为 (命令名, 用途描述)
    """
    return [(cmd, desc) for cmd, desc in REQUIRED_DEPS if not shutil.which(cmd)]


def get_install_hint() -> str:
    """获取安装提示信息"""
    return """安装方法:
  macOS: brew install ffmpeg aria2
  Ubuntu: sudo apt install ffmpeg aria2"""
