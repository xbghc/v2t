"""邮箱 OTP 登录：验证码 + session token，全部存 redis。

- 验证码：otp:{email} → code，5min TTL，验证成功即消费
- 发送冷却：otp_cooldown:{email}，60s，防刷
- 会话：session:{token} → user_id，7天 TTL，可即时吊销
"""

import secrets

from app.storage import get_redis

_OTP_TTL = 300  # 验证码有效期（秒）
_COOLDOWN = 60  # 同邮箱两次发送的最小间隔
_SESSION_TTL = 7 * 24 * 3600  # 会话有效期


class CooldownError(Exception):
    """发送过于频繁。"""


def _otp_key(email: str) -> str:
    return f"otp:{email}"


def _cooldown_key(email: str) -> str:
    return f"otp_cooldown:{email}"


def _session_key(token: str) -> str:
    return f"session:{token}"


def _decode(v) -> str | None:
    if v is None:
        return None
    return v.decode() if isinstance(v, bytes) else v


async def issue_code(email: str) -> str:
    """生成验证码存 redis 并返回（调用方负责发邮件）。冷却期内抛 CooldownError。"""
    redis = get_redis()
    if await redis.get(_cooldown_key(email)):
        raise CooldownError("验证码发送太频繁，请稍后再试")
    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis.set(_otp_key(email), code, ex=_OTP_TTL)
    await redis.set(_cooldown_key(email), "1", ex=_COOLDOWN)
    return code


async def verify_code(email: str, code: str) -> bool:
    """校验验证码，成功即消费（删除），返回是否通过。"""
    redis = get_redis()
    stored = _decode(await redis.get(_otp_key(email)))
    if stored is None or stored != code:
        return False
    await redis.delete(_otp_key(email))
    return True


async def create_session(user_id: str) -> str:
    """签发 session token，存 redis。"""
    redis = get_redis()
    token = secrets.token_urlsafe(32)
    await redis.set(_session_key(token), user_id, ex=_SESSION_TTL)
    return token


async def resolve_session(token: str) -> str | None:
    """token → user_id（None 表示无效/过期）。"""
    return _decode(await get_redis().get(_session_key(token)))


async def revoke_session(token: str) -> None:
    """吊销 session（登出）。"""
    await get_redis().delete(_session_key(token))
