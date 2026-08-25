"""Auth for the vendor portal (magic-link email JWTs), real staff RBAC
(also magic-link, added in Phase 5 — see StaffSession/require_role below),
and a shared-secret gate for internal/admin endpoints not yet migrated to
staff RBAC.

The admin gate (`X-Admin-Key`) was a deliberate Phase 1 simplification,
carried forward as the outer perimeter check on the whole `/admin` surface
even after Phase 5 added real per-role auth — see
docs/operations/security-hardening.md for why a full retrofit of every
admin endpoint was judged riskier than worth doing in this final phase,
and for the migration path `require_role` establishes (one endpoint,
exception approval, is migrated as a working proof of the pattern).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings

ALGORITHM = "HS256"


def create_magic_link_token(vendor_contact_id: UUID, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "magic_link",
        "sub": str(vendor_contact_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.magic_link_ttl_minutes),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGORITHM)


def create_session_token(vendor_contact_id: UUID, vendor_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "session",
        "sub": str(vendor_contact_id),
        "vendor_id": str(vendor_id),
        "iat": now,
        "exp": now + timedelta(hours=settings.vendor_session_ttl_hours),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGORITHM)


def decode_token(token: str, expected_purpose: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


class VendorSession:
    def __init__(self, vendor_contact_id: UUID, vendor_id: UUID):
        self.vendor_contact_id = vendor_contact_id
        self.vendor_id = vendor_id


def require_vendor_session(authorization: str = Header(default="")) -> VendorSession:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token, expected_purpose="session")
    return VendorSession(
        vendor_contact_id=UUID(payload["sub"]),
        vendor_id=UUID(payload["vendor_id"]),
    )


def create_staff_magic_link_token(user_id: UUID, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "staff_magic_link", "sub": str(user_id), "email": email,
        "iat": now, "exp": now + timedelta(minutes=settings.magic_link_ttl_minutes),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGORITHM)


def create_staff_session_token(user_id: UUID, role: str, full_name: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "staff_session", "sub": str(user_id), "role": role, "full_name": full_name,
        "iat": now, "exp": now + timedelta(hours=settings.staff_session_ttl_hours),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGORITHM)


class StaffSession:
    def __init__(self, user_id: UUID, role: str, full_name: str):
        self.user_id = user_id
        self.role = role
        self.full_name = full_name


def require_staff_session(authorization: str = Header(default="")) -> StaffSession:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token, expected_purpose="staff_session")
    return StaffSession(user_id=UUID(payload["sub"]), role=payload["role"], full_name=payload.get("full_name", ""))


def require_role(*roles: str):
    """Real per-role authorization, backed by `users.role` at login time
    (baked into the session JWT, same self-contained-token pattern as
    vendor sessions — no DB round trip needed to authorize a request)."""

    def _dependency(staff: StaffSession = Depends(require_staff_session)) -> StaffSession:
        if staff.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires role: {', '.join(roles)}")
        return staff

    return _dependency


def require_admin_key(x_admin_key: str = Header(default="")) -> None:
    settings = get_settings()
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")


class AccessContext:
    """Either an admin (X-Admin-Key) or a vendor session. Assessment
    endpoints use this to serve both audiences from one implementation
    while still enforcing per-vendor isolation (Phase 0 threat model §4):
    a non-admin caller only ever sees rows for their own vendor_id."""

    def __init__(self, is_admin: bool, vendor_id: UUID | None, vendor_contact_id: UUID | None):
        self.is_admin = is_admin
        self.vendor_id = vendor_id
        self.vendor_contact_id = vendor_contact_id

    def check_vendor(self, resource_vendor_id: UUID) -> None:
        if not self.is_admin and resource_vendor_id != self.vendor_id:
            # 404, not 403 — a vendor probing another vendor's assessment
            # ID should not even learn that it exists.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def get_access_context(
    authorization: str = Header(default=""), x_admin_key: str = Header(default=""),
) -> AccessContext:
    settings = get_settings()
    if x_admin_key and x_admin_key == settings.admin_api_key:
        return AccessContext(is_admin=True, vendor_id=None, vendor_contact_id=None)
    if authorization.startswith("Bearer "):
        session = require_vendor_session(authorization)
        return AccessContext(
            is_admin=False, vendor_id=session.vendor_id, vendor_contact_id=session.vendor_contact_id,
        )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
