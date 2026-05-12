"""
Auth utilities: password hashing, JWT creation/validation, FastAPI dependencies, email.
"""

import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Cookie, HTTPException, status
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

SMTP_USER         = os.environ.get("SMTP_USER", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
SMTP_HOST         = "smtp.gmail.com"
SMTP_PORT         = 587
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")


# ── FastAPI dependencies ───────────────────────────────────────────────────────

def get_current_user(access_token: Optional[str] = Cookie(default=None)) -> dict:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    return _decode_token(access_token)


def get_current_user_optional(access_token: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    if not access_token:
        return None
    try:
        return _decode_token(access_token)
    except HTTPException:
        return None


def require_admin(access_token: Optional[str] = Cookie(default=None)) -> dict:
    user = get_current_user(access_token)
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


def require_designer_or_admin(access_token: Optional[str] = Cookie(default=None)) -> dict:
    user = get_current_user(access_token)
    if user["role"] not in ("admin", "designer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


def send_reset_email(to_email: str, reset_url: str) -> None:
    if not SMTP_USER or not SMTP_APP_PASSWORD:
        raise RuntimeError("SMTP_USER and SMTP_APP_PASSWORD environment variables must be set to send email")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your TradeRoot password"
    msg["From"]    = SMTP_USER
    msg["To"]      = to_email

    plain = (
        f"Click the link below to reset your TradeRoot password (valid for 1 hour):\n\n"
        f"{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    html = (
        f"<p>Click the link below to reset your <strong>TradeRoot</strong> password "
        f"(valid for 1 hour):</p>"
        f'<p><a href="{reset_url}">{reset_url}</a></p>'
        f"<p>If you didn't request this, you can safely ignore this email.</p>"
    )

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=ctx)
        server.login(SMTP_USER, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
