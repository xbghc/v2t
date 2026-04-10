"""arq Worker 配置"""

from dotenv import load_dotenv

load_dotenv()

from app.logging_config import setup_logging

setup_logging()

from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks.workspace_task import process_workspace


async def run_process_workspace(ctx: dict, workspace_id: str, url: str) -> None:
    """arq 任务入口：处理工作区"""
    await process_workspace(workspace_id, url)


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
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 3
    job_timeout = 1800  # 30 分钟

    @staticmethod
    def redis_settings() -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.redis_url)
