import asyncio
import random
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import GMAIL_SENDER, GMAIL_APP_PASSWORD, OTP_EXPIRE_MINUTES


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _build_otp_email(to_email: str, otp: str, display_name: str = "") -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your OTP - Password Reset"
    msg["From"] = f"Entertainment Hub <{GMAIL_SENDER}>"
    msg["To"] = to_email

    name = display_name or to_email.split("@")[0]

    text = (
        f"Hi {name},\n\n"
        f"Your OTP for password reset is: {otp}\n\n"
        f"This OTP is valid for {OTP_EXPIRE_MINUTES} minutes.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"Entertainment Hub"
    )

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #0f0f0f; color: #fff; padding: 40px;">
        <div style="max-width: 480px; margin: 0 auto; background: #1a1a1a; border-radius: 12px; padding: 32px;">
          <h2 style="color: #00d4aa; margin-bottom: 8px;">Password Reset</h2>
          <p style="color: #aaa;">Hi <strong style="color:#fff">{name}</strong>,</p>
          <p style="color: #aaa;">Use the OTP below to reset your password. It expires in <strong style="color:#fff">{OTP_EXPIRE_MINUTES} minutes</strong>.</p>
          <div style="background: #111; border: 2px solid #00d4aa; border-radius: 8px; padding: 24px; text-align: center; margin: 24px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 12px; color: #00d4aa;">{otp}</span>
          </div>
          <p style="color: #666; font-size: 13px;">If you didn't request this, you can safely ignore this email.</p>
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    return msg


async def send_otp_email(to_email: str, otp: str, display_name: str = "") -> bool:
    """Send OTP email via Gmail SMTP. Returns True on success."""

    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        print("[email_service] Gmail not configured — OTP not sent.")
        print(f"[email_service] DEV OTP for {to_email}: {otp}")
        return False

    msg = _build_otp_email(to_email, otp, display_name)

    def _send():
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, to_email, msg.as_string())

    try:
        # Run blocking SMTP in thread pool to not block the event loop
        await asyncio.get_event_loop().run_in_executor(None, _send)
        print(f"[email_service] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[email_service] Failed to send OTP: {e}")
        return False