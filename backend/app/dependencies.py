"""FastAPI 鉴权依赖。

require_user 卡在需要登录的端点上：从 Authorization: Bearer <token> 解析 token，
查 redis session → 查 mongo user，任一步失败返回 401。
"""

from fastapi import Header, HTTPException

from app.services.otp import resolve_session
from app.storage.user_store import get_user_by_id


async def bearer_token(authorization: str = Header(default="")) -> str:
    """从 Authorization 头取 Bearer token，缺失则 401。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    return token


async def require_user(authorization: str = Header(default="")) -> dict:
    """解析当前登录用户（dict），未登录/过期返回 401。"""
    token = await bearer_token(authorization)
    user_id = await resolve_session(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
