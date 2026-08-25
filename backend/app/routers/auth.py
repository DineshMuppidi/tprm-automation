import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.db import get_db
from app.schemas.auth import MagicLinkRequest, MagicLinkVerify, SessionToken
from app.security import create_magic_link_token, create_session_token, decode_token
from app.services.email_service import Email, get_email_provider

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("tprm.auth")


@router.post("/request-link", status_code=status.HTTP_202_ACCEPTED)
async def request_link(body: MagicLinkRequest, pool: asyncpg.Pool = Depends(get_db)):
    """Always returns 202 regardless of whether the email matches a vendor
    contact — an enumeration-safe response, same as most real login flows."""
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "SELECT id, email FROM vendor_contacts WHERE email = $1", body.email,
        )
    if contact:
        settings = get_settings()
        token = create_magic_link_token(contact["id"], contact["email"])
        login_url = f"{settings.app_base_url}/verify?token={token}"
        get_email_provider().send(Email(
            to=contact["email"],
            subject="Your TPRM portal sign-in link",
            body=f"Sign in here (expires in {settings.magic_link_ttl_minutes} minutes): {login_url}",
        ))
    else:
        logger.info("Magic-link requested for unknown email %s", body.email)
    return {"message": "If that email is registered, a sign-in link has been sent."}


@router.post("/verify", response_model=SessionToken)
async def verify(body: MagicLinkVerify, pool: asyncpg.Pool = Depends(get_db)):
    payload = decode_token(body.token, expected_purpose="magic_link")
    contact_id = payload["sub"]

    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            """
            SELECT vc.id, vc.vendor_id, v.legal_name
            FROM vendor_contacts vc JOIN vendors v ON v.id = vc.vendor_id
            WHERE vc.id = $1
            """,
            contact_id,
        )
    if not contact:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown account")

    session_token = create_session_token(contact["id"], contact["vendor_id"])
    return SessionToken(
        access_token=session_token,
        vendor_id=str(contact["vendor_id"]),
        vendor_contact_id=str(contact["id"]),
        vendor_name=contact["legal_name"],
    )
