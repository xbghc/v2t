"""邮件发送（SMTP，用于邮箱 OTP 登录验证码）。

直连邮箱服务商的 SMTP（默认 QQ 邮箱 smtp.qq.com:465 SSL），借其信誉投递，
不经过本机 MTA。配置见 config.Settings.smtp_*。
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


class MailError(Exception):
    """邮件发送失败。"""


async def send_email(to: str, subject: str, body: str) -> None:
    """发送一封纯文本邮件。抛 MailError 由调用方分类处理。"""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_user:
        raise MailError("SMTP 未配置（缺 SMTP_HOST / SMTP_USER）")

    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    # 465 → 隐式 SSL（use_tls）；587 → STARTTLS。由 smtp_secure 决定走哪条。
    use_tls = settings.smtp_secure.strip().lower() in ("true", "1", "yes", "ssl")
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=int(settings.smtp_port),
            username=settings.smtp_user,
            password=settings.smtp_pass,
            use_tls=use_tls,
            start_tls=not use_tls,
            timeout=15,
        )
        logger.info("邮件已发送至 %s", to)
    except Exception as e:  # noqa: BLE001
        logger.warning("邮件发送失败 (%s): %s", to, e)
        raise MailError(f"邮件发送失败: {e}") from e


async def send_otp(to: str, code: str) -> None:
    """发送 OTP 登录验证码。"""
    await send_email(
        to,
        subject="Gist 登录验证码",
        body=f"你的登录验证码是：{code}\n\n5 分钟内有效，请勿向他人泄露。",
    )
