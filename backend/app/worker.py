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


async def startup(ctx: dict) -> None:
    """Worker 启动时初始化"""
    from loguru import logger

    logger.info("arq worker 启动")


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
    job_timeout = 1800  # 30 分钟

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
