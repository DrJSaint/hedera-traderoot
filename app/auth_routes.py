"""
Auth routes: register, login, logout, me, forgot/reset password.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

import app.db as db
from app.auth import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    send_reset_email,
    verify_password,
)

router = APIRouter(prefix="/api/auth")

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


class RegisterIn(BaseModel):
    email: str
    password: str
    name: str
    company: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None


class ForgotPasswordIn(BaseModel):
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    password: str


def _set_auth_cookie(response: Response, user_id: int, role: str):
    token = create_access_token(user_id, role)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        secure=False,  # set True in production behind HTTPS
    )


@router.post("/register", status_code=201)
def register(body: RegisterIn, response: Response):
    if db.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = db.create_user(body.email, hash_password(body.password), role="designer")
    designer_id = db.add_designer(body.name, body.email, body.company)
    db.link_user_to_designer(user_id, designer_id)
    db.log_activity(user_id, "registered", {"name": body.name, "email": body.email, "company": body.company})

    _set_auth_cookie(response, user_id, "designer")
    return {"id": user_id, "role": "designer"}


@router.post("/login")
def login(body: LoginIn, response: Response):
    user = db.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    _set_auth_cookie(response, user["id"], user["role"])
    return {"id": user["id"], "role": user["role"]}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.patch("/profile")
def update_profile(body: ProfileIn, user: dict = Depends(get_current_user)):
    user_record = db.get_user_by_id(int(user["sub"]))
    if not user_record or not user_record.get("designer_id"):
        raise HTTPException(status_code=404, detail="No designer profile to edit")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.company is not None:
        updates["company"] = body.company
    if updates:
        db.patch_designer(user_record["designer_id"], updates)
        db.log_activity(int(user["sub"]), "profile_updated", updates)
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request):
    user = db.get_user_by_email(body.email)
    if user:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.create_password_reset_token(user["id"], token, expires_at)
        base_url = str(request.base_url).rstrip("/")
        reset_url = f"{base_url}/?reset_token={token}"
        try:
            send_reset_email(user["email"], reset_url)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")
    # Always return ok to prevent email enumeration
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn):
    row = db.get_password_reset_token(body.token)
    if not row or row["used"]:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    expires_at = row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Reset link has expired — please request a new one")

    db.consume_password_reset_token(body.token)
    db.update_user_password(row["user_id"], hash_password(body.password))
    return {"ok": True}


@router.get("/me")
def me(user: Optional[dict] = Depends(get_current_user_optional)):
    if user is None:
        return {"authenticated": False}
    user_record = db.get_user_by_id(int(user["sub"]))
    return {
        "authenticated": True,
        "id": int(user["sub"]),
        "role": user["role"],
        "email":       user_record["email"]           if user_record else None,
        "designer_id": user_record["designer_id"]     if user_record else None,
        "name":        user_record.get("designer_name")    if user_record else None,
        "company":     user_record.get("designer_company") if user_record else None,
    }
