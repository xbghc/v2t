"""认证服务"""

import random
import string
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, VerificationCode
from app.services.email import send_verification_code

logger = logging.getLogger(__name__)

# JWT 配置
ALGORITHM = "HS256"


def generate_code(length: int = 6) -> str:
    """生成数字验证码"""
    return "".join(random.choices(string.digits, k=length))


def create_access_token(user_id: int, email: str) -> str:
    """创建 JWT Token"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """验证 JWT Token"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug("Token 验证失败: %s", e)
        return None


async def send_code(db: AsyncSession, email: str) -> tuple[bool, str]:
    """
    发送验证码

    Returns:
        (成功, 消息)
    """
    # 检查是否频繁发送（60秒内只能发一次）
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    stmt = select(VerificationCode).where(
        VerificationCode.email == email,
        VerificationCode.created_at > one_minute_ago,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        return False, "发送太频繁，请稍后再试"

    # 生成验证码
    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    # 保存到数据库
    verification = VerificationCode(
        email=email,
        code=code,
        expires_at=expires_at,
    )
    db.add(verification)
    await db.commit()

    # 发送邮件
    success = await send_verification_code(email, code)
    if not success:
        return False, "邮件发送失败，请检查邮箱地址"

    return True, "验证码已发送"


async def verify_and_login(db: AsyncSession, email: str, code: str) -> tuple[bool, str, Optional[str]]:
    """
    验证验证码并登录

    Returns:
        (成功, 消息, token)
    """
    # 查找有效的验证码
    now = datetime.now(timezone.utc)
    stmt = select(VerificationCode).where(
        VerificationCode.email == email,
        VerificationCode.code == code,
        VerificationCode.used == False,
        VerificationCode.expires_at > now,
    ).order_by(VerificationCode.created_at.desc())

    result = await db.execute(stmt)
    verification = result.scalar_one_or_none()

    if not verification:
        return False, "验证码无效或已过期", None

    # 标记验证码已使用
    verification.used = True

    # 查找或创建用户
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # 新用户
        user = User(email=email, nickname=email.split("@")[0])
        db.add(user)
        await db.flush()  # 获取 user.id
        logger.info("新用户注册: %s", email)
    else:
        logger.info("用户登录: %s", email)

    await db.commit()

    # 生成 Token
    token = create_access_token(user.id, user.email)
    return True, "登录成功", token


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """根据 ID 获取用户"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def cleanup_expired_codes(db: AsyncSession):
    """清理过期验证码"""
    now = datetime.now(timezone.utc)
    stmt = delete(VerificationCode).where(VerificationCode.expires_at < now)
    await db.execute(stmt)
    await db.commit()
