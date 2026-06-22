"""邮箱 OTP 登录端点。

  POST /auth/request-code  {email}        → 发验证码（带冷却）
  POST /auth/verify        {email, code}  → 验码 → 查/建用户 → 签发 token
  GET  /auth/me                           → 当前用户（需登录）
  POST /auth/logout                       → 吊销 token（需登录）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import bearer_token, require_user
from app.models.schemas import (
    AuthResponse,
    RequestCodeRequest,
    UserResponse,
    VerifyCodeRequest,
)
from app.services.mailer import MailError, send_otp
from app.services.otp import (
    CooldownError,
    create_session,
    issue_code,
    revoke_session,
    verify_code,
)
from app.storage.user_store import get_or_create_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    return email


@router.post("/request-code")
async def request_code(body: RequestCodeRequest) -> dict:
    """发送登录验证码到邮箱。"""
    email = _normalize_email(body.email)
    try:
        code = await issue_code(email)
    except CooldownError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    try:
        await send_otp(email, code)
    except MailError as e:
        raise HTTPException(status_code=502, detail="验证码发送失败，请稍后重试") from e
    return {"ok": True}


@router.post("/verify", response_model=AuthResponse)
async def verify(body: VerifyCodeRequest) -> AuthResponse:
    """校验验证码，成功则登录（查/建用户 + 签发 token）。"""
    email = _normalize_email(body.email)
    if not await verify_code(email, body.code.strip()):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    user = await get_or_create_user(email)
    token = await create_session(user["user_id"])
    return AuthResponse(token=token, user=UserResponse(**user))


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(require_user)) -> UserResponse:
    """返回当前登录用户。"""
    return UserResponse(**user)


@router.post("/logout")
async def logout(token: str = Depends(bearer_token)) -> dict:
    """吊销当前 token。"""
    await revoke_session(token)
    return {"ok": True}
