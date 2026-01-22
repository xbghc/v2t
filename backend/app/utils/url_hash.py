"""URL 规范化和哈希计算工具"""

import hashlib
import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

# 需要移除的追踪参数（黑名单）
TRACKING_PARAMS = frozenset(
    {
        # 通用追踪参数
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        # B站追踪参数
        "vd_source",
        "spm_id_from",
        "from_spmid",
        "share_source",
        "share_medium",
        "share_plat",
        "share_session_id",
        "share_tag",
        "share_times",
        "bbid",
        "ts",
        "from",
        "is_story_h5",
        "buvid",
        "mid",
        "plat_id",
        # 抖音追踪参数
        "previous_page",
        "enter_from",
        "extra_params",
        "enter_method",
        "launch_container",
        # 小红书追踪参数
        "xsec_token",
        "xsec_source",
        "app_platform",
        "app_version",
        # YouTube 追踪参数
        "si",
        "feature",
        "pp",
        # 通用社交分享参数
        "fbclid",
        "gclid",
        "ref",
        "source",
        "share",
        "timestamp",
    }
)

# 需要保留的重要参数（白名单）
IMPORTANT_PARAMS = frozenset(
    {
        # B站
        "p",  # 多 P 视频分 P
        "t",  # 时间戳跳转
        "bvid",
        "aid",
        # YouTube
        "v",  # 视频 ID
        "list",  # 播放列表
        "index",  # 播放列表索引
        # 抖音
        "modal_id",
        # 通用
        "id",
    }
)


def normalize_url(url: str) -> str:
    """
    规范化 URL，移除追踪参数并保留重要参数。

    - 追踪参数（TRACKING_PARAMS）：移除
    - 重要参数（IMPORTANT_PARAMS）：保留
    - 未知参数：保留，但记录 warning 日志

    Args:
        url: 原始 URL

    Returns:
        规范化后的 URL
    """
    parsed = urlparse(url)

    # 解析查询参数
    params = parse_qs(parsed.query, keep_blank_values=False)

    # 过滤参数
    filtered_params = {}
    for key, values in params.items():
        key_lower = key.lower()

        if key_lower in TRACKING_PARAMS:
            # 追踪参数，移除
            continue
        elif key_lower in IMPORTANT_PARAMS:
            # 重要参数，保留
            filtered_params[key] = values[0] if len(values) == 1 else values
        else:
            # 未知参数，保留但记录警告
            logger.warning("未知 URL 参数: %s=%s (URL: %s)", key, values, url)
            filtered_params[key] = values[0] if len(values) == 1 else values

    # 重建查询字符串（排序以确保一致性）
    query = urlencode(sorted(filtered_params.items()), doseq=True)

    # 重建 URL
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),  # 移除尾部斜杠
            parsed.params,
            query,
            "",  # 移除 fragment
        )
    )

    return normalized


def compute_url_hash(url: str) -> str:
    """
    计算 URL 的哈希值。

    先规范化 URL，再计算 SHA256 哈希。

    Args:
        url: 原始 URL

    Returns:
        64 位哈希字符串
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()
