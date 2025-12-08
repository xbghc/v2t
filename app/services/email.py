"""邮件发送服务"""

import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_verification_code(to_email: str, code: str) -> bool:
    """
    发送验证码邮件

    Args:
        to_email: 收件人邮箱
        code: 验证码

    Returns:
        是否发送成功
    """
    settings = get_settings()

    if not settings.smtp_host or not settings.smtp_user:
        logger.error("SMTP 配置不完整，无法发送邮件")
        return False

    # 构建邮件
    message = MIMEMultipart("alternative")
    message["Subject"] = f"【v2t】验证码：{code}"
    message["From"] = settings.smtp_user
    message["To"] = to_email

    # 纯文本内容
    text_content = f"""您好！

您的验证码是：{code}

验证码有效期为 10 分钟，请尽快使用。

如果这不是您的操作，请忽略此邮件。

---
v2t - 视频转文字工具
"""

    # HTML 内容
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">v2t 验证码</h1>
    </div>
    <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="color: #333; font-size: 16px; margin-bottom: 20px;">您好！</p>
        <p style="color: #333; font-size: 16px; margin-bottom: 20px;">您的验证码是：</p>
        <div style="background: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <span style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px;">{code}</span>
        </div>
        <p style="color: #666; font-size: 14px; margin-bottom: 10px;">验证码有效期为 <strong>10 分钟</strong>，请尽快使用。</p>
        <p style="color: #999; font-size: 12px;">如果这不是您的操作，请忽略此邮件。</p>
    </div>
    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
        <p>v2t - 视频转文字工具</p>
    </div>
</body>
</html>
"""

    message.attach(MIMEText(text_content, "plain", "utf-8"))
    message.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_start_tls,
        )
        logger.info("验证码邮件已发送至 %s", to_email)
        return True
    except Exception as e:
        logger.error("发送邮件失败: %s", e)
        return False
