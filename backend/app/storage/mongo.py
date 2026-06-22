"""MongoDB 连接（用户系统）。

motor 异步客户端单例。连接 lazy 建立；web 与 worker 各自持有自己的 client，
事件循环切换时通过 reset_mongo() 重置（对齐 storage.reset_stores 的约定）。
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_mongo_db() -> AsyncIOMotorDatabase:
    """获取 Mongo 数据库句柄（单例 client）。"""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongo_uri)
        logger.info("MongoDB 客户端已创建")
    return _client[get_settings().mongo_db]


async def check_mongo_connection() -> tuple[bool, str]:
    """检测 Mongo 连接（启动自检用）。"""
    try:
        await get_mongo_db().command("ping")
        return True, "连接正常"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def reset_mongo() -> None:
    """重置客户端（事件循环切换时调用）。"""
    global _client
    if _client is not None:
        _client.close()
        _client = None
