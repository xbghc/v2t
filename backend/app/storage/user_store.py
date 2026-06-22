"""用户存储（MongoDB）。email 唯一标识，登录时 upsert。"""

import time

from bson import ObjectId
from pymongo import ReturnDocument

from app.storage.mongo import get_mongo_db


def _serialize(doc: dict) -> dict:
    """Mongo 文档 → 对外 dict（ObjectId 转 str）。"""
    return {
        "user_id": str(doc["_id"]),
        "email": doc["email"],
        "created_at": doc.get("created_at", 0.0),
        "last_login_at": doc.get("last_login_at", 0.0),
    }


async def get_or_create_user(email: str) -> dict:
    """按 email 查用户，不存在则建。每次调用刷新 last_login_at。"""
    now = time.time()
    doc = await get_mongo_db().users.find_one_and_update(
        {"email": email},
        {
            "$setOnInsert": {"email": email, "created_at": now},
            "$set": {"last_login_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(doc)


async def get_user_by_id(user_id: str) -> dict | None:
    """按 id 查用户。id 非法或不存在返回 None。"""
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    doc = await get_mongo_db().users.find_one({"_id": oid})
    return _serialize(doc) if doc else None


async def ensure_indexes() -> None:
    """建 email 唯一索引（启动时调一次）。"""
    await get_mongo_db().users.create_index("email", unique=True)
