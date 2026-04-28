"""arq Worker 配置"""

from dotenv import load_dotenv

load_dotenv()

from app.logging_config import setup_logging

setup_logging()

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks.workspace_task import process_workspace


async def run_process_workspace(ctx: dict, workspace_id: str, url: str) -> None:
    """arq 任务入口：处理工作区"""
    await process_workspace(workspace_id, url)


async def cleanup_old_files_job(ctx: dict) -> None:
    """定时清理过期的本地文件（Redis TTL 只清理元数据，文件需要手动清理）"""
    from loguru import logger

    from app.storage import cleanup_old_files, get_file_storage

    settings = get_settings()
    storage = get_file_storage()

    # 清理数据目录中过期的资源
    cleaned = cleanup_old_files(storage.base_dir, expire_seconds=86400)
    if cleaned > 0:
        logger.info("清理过期资源目录: %d 个", cleaned)

    # 清理临时文件目录
    cleaned = cleanup_old_files(settings.temp_path, expire_seconds=86400)
    if cleaned > 0:
        logger.info("清理过期临时目录: %d 个", cleaned)


_INFLIGHT_STATUSES = {"processing", "downloading", "transcribing"}


async def _mark_inflight_workspaces_failed(redis) -> int:
    """把 Redis 里所有非终态的 workspace 标 failed（worker 重启场景）

    背景：worker 进程崩溃/重启时，进行中的 workspace 在 Redis 里仍然是
    processing 状态，但实际已无任务在跑——前端 SSE 一直挂着等不到结束。
    新 worker 启动时清理这些"幽灵任务"，让前端能收到 failed 终态。
    """
    cleaned = 0
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="workspace:*", count=100)
        for key in keys:
            tail = key[len("workspace:"):]
            # 跳过子键：workspace:{id}:resources / workspace:lookup:* 等
            if ":" in tail or tail.startswith("lookup"):
                continue
            status = await redis.hget(key, "status")
            if status in _INFLIGHT_STATUSES:
                await redis.hset(key, mapping={
                    "status": "failed",
                    "error": "worker 重启，任务中断",
                    "progress": "已中断",
                })
                cleaned += 1
        if cursor == 0:
            break
    return cleaned


async def startup(ctx: dict) -> None:
    """Worker 启动时初始化"""
    import asyncio

    from loguru import logger

    logger.info("arq worker 启动")

    # 1. 预热 silero-vad ONNX runtime（避免首个请求冷启动 ~1-2s）
    try:
        from app.services.vad import _load_model

        await asyncio.to_thread(_load_model)
        logger.info("silero-vad 已预热")
    except Exception as e:
        logger.warning("silero-vad 预热失败（不影响启动）: %s", e)

    # 2. 清理上次未完成的 in-flight workspace（worker 崩溃/重启场景）
    try:
        from app.storage import get_redis

        cleaned = await _mark_inflight_workspaces_failed(get_redis())
        if cleaned > 0:
            logger.warning("清理 in-flight 工作区 %d 个（worker 重启）", cleaned)
    except Exception as e:
        logger.warning("in-flight 清理失败（不影响启动）: %s", e)


async def shutdown(ctx: dict) -> None:
    """Worker 关闭时清理"""
    from loguru import logger

    from app.storage import reset_stores

    reset_stores()
    logger.info("arq worker 关闭")


class WorkerSettings:
    """arq worker 配置"""

    functions = [run_process_workspace]
    cron_jobs = [
        cron(cleanup_old_files_job, hour=3, minute=0),  # 每天凌晨 3 点清理
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 3
    job_timeout = 3600  # 1 小时；与 max_video_duration=4h 匹配（实际 4h 视频约 10-15min 跑完）

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
