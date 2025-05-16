import os
import secrets
import smtplib
from datetime import datetime
from email.message import EmailMessage

from fastapi import HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import UserVerification, RefreshToken

SMTP_CONFIG = {
    "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "port": int(os.getenv("SMTP_PORT", 587)),
    "user": os.getenv("SMTP_USER", "your-email@gmail.com"),
    "password": os.getenv("SMTP_PASSWORD", "your-app-password")
}


def generate_verification_code(email):
    code = str(secrets.randbelow(999999)).zfill(6)
    date = datetime.now()
    user_reg = UserVerification(email=email, code=code, created_at=date)
    return user_reg

def send_verification_code(email, code):
    msg = EmailMessage()
    msg["Subject"] = "Код подтверждения"
    msg["From"] = SMTP_CONFIG["user"]
    msg["To"] = email
    msg.set_content(f"Ваш код подтверждения: {code}")
    try:
        with smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"]) as server:
            server.starttls()
            server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
            server.send_message(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")


async def is_valid_refresh_token(token, db: AsyncSession = Depends(get_db)):
    query = (
        select(RefreshToken)
        .where(
            RefreshToken.token == token
        )
    )
    db_token = await db.execute(query).scalar_one_or_none()
    if not db_token:
        return False
    if db_token.revoked:
        return False
    if datetime.utcnow() > db_token.expires_at:
        return False
    return True