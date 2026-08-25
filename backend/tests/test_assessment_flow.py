"""Integration tests against a real Postgres instance (DATABASE_URL from
.env, schema + seed data applied via db/init_db.py — see README). Uses the
Tier 4 template deliberately: it's the smallest, so a full submit-flow test
stays fast and isn't coupled to Tier 1's larger question set.
"""

import uuid

from app.security import create_magic_link_token


async def _create_vendor_with_assessment(pool, tier="tier_4_low"):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            """
            INSERT INTO vendors (legal_name, tier, status, data_access_level)
            VALUES ($1, $2, 'onboarding', 'none') RETURNING id
            """,
            f"Test Vendor {uuid.uuid4().hex[:8]}", tier,
        )
        contact = await conn.fetchrow(
            """
            INSERT INTO vendor_contacts (vendor_id, full_name, email, is_primary)
            VALUES ($1, 'Test Contact', $2, true) RETURNING id, email
            """,
            vendor["id"], f"{uuid.uuid4().hex[:8]}@example.com",
        )
        template = await conn.fetchrow(
            "SELECT id FROM questionnaire_templates WHERE tier = $1 LIMIT 1", tier,
        )
        assessment = await conn.fetchrow(
            """
            INSERT INTO assessments (vendor_id, template_id, status, assigned_at, due_at)
            VALUES ($1, $2, 'assigned', now(), now() + interval '14 days') RETURNING id
            """,
            vendor["id"], template["id"],
        )
    return vendor["id"], contact["id"], contact["email"], assessment["id"]


async def _login(client, contact_id, email):
    token = create_magic_link_token(contact_id, email)
    r = await client.post("/auth/verify", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_full_tier4_assessment_flow(client, pool):
    _, contact_id, email, assessment_id = await _create_vendor_with_assessment(pool)
    access_token = await _login(client, contact_id, email)
    headers = {"Authorization": f"Bearer {access_token}"}

    detail = (await client.get(f"/assessments/{assessment_id}", headers=headers)).json()
    qid = {q["question_code"]: q["id"] for q in detail["questions"]}
    assert "T4-DATA-2" not in qid  # conditional follow-up hidden until T4-DATA-1 == Yes

    for code, answer in [
        ("T4-INFO-1", "We provide payroll processing software."),
        ("T4-DATA-1", "No"),
        ("T4-SEC-1", "Yes"),
    ]:
        r = await client.put(
            f"/assessments/{assessment_id}/responses/{qid[code]}", headers=headers,
            json={"raw_answer": answer},
        )
        assert r.status_code == 200, r.text

    updated = (await client.get(f"/assessments/{assessment_id}", headers=headers)).json()
    assert updated["progress_pct"] == 100.0

    r = await client.post(f"/assessments/{assessment_id}/submit", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["overall_score"] is not None

    report = await client.get(f"/assessments/{assessment_id}/report", headers=headers)
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"


async def test_submit_blocked_until_all_visible_questions_answered(client, pool):
    _, contact_id, email, assessment_id = await _create_vendor_with_assessment(pool)
    access_token = await _login(client, contact_id, email)
    headers = {"Authorization": f"Bearer {access_token}"}

    r = await client.post(f"/assessments/{assessment_id}/submit", headers=headers)
    assert r.status_code == 400


async def test_vendor_cannot_access_another_vendors_assessment(client, pool):
    _, _, _, assessment1 = await _create_vendor_with_assessment(pool)
    _, contact2, email2, _ = await _create_vendor_with_assessment(pool)

    token2 = await _login(client, contact2, email2)
    r = await client.get(f"/assessments/{assessment1}", headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code == 404


async def test_admin_endpoints_require_admin_key(client):
    r = await client.get("/admin/vendors")
    assert r.status_code == 403

    r = await client.get("/admin/vendors", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 403
