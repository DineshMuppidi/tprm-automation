"""Staff (internal) authentication — magic-link, same UX as the vendor
portal (see routers/auth.py), issuing a session JWT that carries the
user's role from `users.role`. This is Phase 5 closing the "real RBAC
deferred" note carried in security.py's docstring since Phase 1: genuine
per-role auth, not the `X-Admin-Key` shared-secret placeholder.
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.db import get_db
from app.schemas.auth import MagicLinkRequest, MagicLinkVerify
from app.security import create_staff_magic_link_token, create_staff_session_token, decode_token
from app.services.email_service import Email, get_email_provider

router = APIRouter(prefix="/staff/auth", tags=["staff-auth"])
logger = logging.getLogger("tprm.staff_auth")


@router.post("/request-link", status_code=status.HTTP_202_ACCEPTED)
async def request_link(body: MagicLinkRequest, pool: asyncpg.Pool = Depends(get_db)):
    """Always 202 regardless of match — enumeration-safe, same as the vendor flow."""
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id, email FROM users WHERE email = $1 AND is_active", body.email)
    if user:
        settings = get_settings()
        token = create_staff_magic_link_token(user["id"], user["email"])
        login_url = f"{settings.app_base_url}/staff/verify?token={token}"
        get_email_provider().send(Email(
            to=user["email"], subject="Your TPRM staff sign-in link",
            body=f"Sign in here (expires in {settings.magic_link_ttl_minutes} minutes): {login_url}",
        ))
    else:
        logger.info("Staff magic-link requested for unknown/inactive email %s", body.email)
    return {"message": "If that email is registered, a sign-in link has been sent."}


@router.post("/verify")
async def verify(body: MagicLinkVerify, pool: asyncpg.Pool = Depends(get_db)):
    payload = decode_token(body.token, expected_purpose="staff_magic_link")
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, full_name, role FROM users WHERE id = $1 AND is_active", payload["sub"],
        )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown or inactive account")

    session_token = create_staff_session_token(user["id"], user["role"], user["full_name"])
    return {
        "access_token": session_token, "token_type": "bearer",
        "user_id": str(user["id"]), "full_name": user["full_name"], "role": user["role"],
    }
