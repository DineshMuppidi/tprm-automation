"""Phase 5 hardening tests: security headers, rate limiting, staff RBAC,
health/metrics endpoints."""

import uuid

import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.middleware import RateLimitMiddleware
from app.security import create_staff_magic_link_token


# ---------------------------------------------------------------------------
# Security headers / health / metrics (against the real app, via `client`)
# ---------------------------------------------------------------------------

async def test_security_headers_present(client):
    r = await client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" in r.headers


async def test_health_live_is_dependency_free(client):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_health_ready_checks_real_db_connectivity(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_metrics_endpoint_returns_prometheus_format(client):
    await client.get("/health")  # generate at least one data point
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "tprm_http_requests_total" in r.text
    assert "tprm_db_pool_size" in r.text


# ---------------------------------------------------------------------------
# Rate limiting — isolated tiny app, not the full one (keeps this fast and
# independent of the real app's configured limit)
# ---------------------------------------------------------------------------

async def test_rate_limit_blocks_after_threshold():
    async def endpoint(request):
        return PlainTextResponse("ok")

    tiny_app = Starlette(routes=[Route("/thing", endpoint)])
    tiny_app.add_middleware(RateLimitMiddleware, requests_per_minute=3)

    transport = httpx.ASGITransport(app=tiny_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        statuses = [(await c.get("/thing")).status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]


async def test_rate_limit_exempts_health_and_metrics():
    async def endpoint(request):
        return PlainTextResponse("ok")

    tiny_app = Starlette(routes=[Route("/health", endpoint)])
    tiny_app.add_middleware(RateLimitMiddleware, requests_per_minute=1)

    transport = httpx.ASGITransport(app=tiny_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        statuses = [(await c.get("/health")).status_code for _ in range(5)]

    assert all(s == 200 for s in statuses)


# ---------------------------------------------------------------------------
# Staff RBAC
# ---------------------------------------------------------------------------

async def test_staff_login_flow_issues_role_bearing_session(client, pool):
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id, email FROM users WHERE role = 'compliance_officer' LIMIT 1")

    token = create_staff_magic_link_token(user["id"], user["email"])
    r = await client.post("/staff/auth/verify", json={"token": token})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "compliance_officer"
    assert "access_token" in body


async def test_staff_request_link_is_enumeration_safe(client):
    r = await client.post("/staff/auth/request-link", json={"email": f"{uuid.uuid4().hex}@example.com"})
    assert r.status_code == 202  # same response whether or not the email matches a real user


async def test_exception_approval_requires_staff_role_not_just_admin_key(client, pool):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) "
            "VALUES ($1, 'tier_2_high', 'active', 'confidential') RETURNING id",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        finding = await conn.fetchrow(
            "INSERT INTO findings (vendor_id, title, description, severity, status, due_at) "
            "VALUES ($1, 'T', 'D', 'medium', 'in_progress', now() + interval '30 days') RETURNING id",
            vendor["id"],
        )
        exception = await conn.fetchrow(
            "INSERT INTO exceptions (finding_id, justification, expires_at) "
            "VALUES ($1, 'cannot remediate', now() + interval '365 days') RETURNING id",
            finding["id"],
        )

    # Admin key alone (the old, pre-Phase-5 gate) is no longer sufficient for this action.
    r = await client.post(f"/admin/exceptions/{exception['id']}/approve", headers={"X-Admin-Key": "dev-admin-key"})
    assert r.status_code == 401  # missing staff bearer token

    async with pool.acquire() as conn:
        legal_user = await conn.fetchrow("SELECT id, email FROM users WHERE role = 'legal' LIMIT 1")
    wrong_role_token = create_staff_magic_link_token(legal_user["id"], legal_user["email"])
    session = await client.post("/staff/auth/verify", json={"token": wrong_role_token})
    wrong_role_bearer = session.json()["access_token"]

    r = await client.post(
        f"/admin/exceptions/{exception['id']}/approve",
        headers={"X-Admin-Key": "dev-admin-key", "Authorization": f"Bearer {wrong_role_bearer}"},
    )
    assert r.status_code == 403  # authenticated, but wrong role

    async with pool.acquire() as conn:
        compliance_user = await conn.fetchrow("SELECT id, email FROM users WHERE role = 'compliance_officer' LIMIT 1")
    right_role_token = create_staff_magic_link_token(compliance_user["id"], compliance_user["email"])
    session = await client.post("/staff/auth/verify", json={"token": right_role_token})
    right_role_bearer = session.json()["access_token"]

    r = await client.post(
        f"/admin/exceptions/{exception['id']}/approve",
        headers={"X-Admin-Key": "dev-admin-key", "Authorization": f"Bearer {right_role_bearer}"},
    )
    assert r.status_code == 200
    assert r.json()["approved_by_id"] == str(compliance_user["id"])  # real approver recorded, not NULL


# ---------------------------------------------------------------------------
# SQL injection — automated regression test for the manual check documented
# in docs/operations/security-hardening.md (run for real against a live
# Postgres instance during Phase 5 development)
# ---------------------------------------------------------------------------

async def test_sql_injection_attempt_is_stored_as_literal_data(client, pool):
    payload = {
        "legal_name": "Evil Corp'; DROP TABLE vendors; --",
        "tier": "tier_4_low",
        "data_access_level": "none",
        "primary_contact": {"full_name": "Attacker", "email": f"{uuid.uuid4().hex}@example.com"},
    }
    r = await client.post("/admin/vendors", headers={"X-Admin-Key": "dev-admin-key"}, json=payload)
    assert r.status_code == 201
    assert r.json()["legal_name"] == payload["legal_name"]  # stored verbatim, not executed

    async with pool.acquire() as conn:
        # If the injection had executed, this table would no longer exist.
        row = await conn.fetchrow("SELECT legal_name FROM vendors WHERE id = $1", r.json()["id"])
    assert row["legal_name"] == payload["legal_name"]
