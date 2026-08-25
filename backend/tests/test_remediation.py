"""Phase 3 remediation workflow tests. Unit tests for the mock plan/
evidence review heuristics, then integration tests against the live
Postgres instance covering the full state machine (acknowledge -> plan ->
in_progress -> evidence -> closed, and the rejection/resubmit loop), auto
-generated findings from both triggers, escalation, and exceptions.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.llm_analyzer import EvidenceContext
from app.services.remediation import escalation_engine, finding_generator, ticket_engine
from app.services.remediation.evidence_validator import FindingContext, MockRemediationReviewProvider
from app.services.remediation.ticket_engine import InvalidTransition


# ---------------------------------------------------------------------------
# Pure unit tests — mock review heuristics
# ---------------------------------------------------------------------------

@pytest.fixture
def provider():
    return MockRemediationReviewProvider()


async def test_vague_plan_is_not_credible(provider):
    finding = FindingContext(title="Enforce MFA", description="...", required_evidence="screenshot", severity="critical")
    result = await provider.review_plan(finding, "We will look into it and consider our options.")
    assert result.credible is False
    assert result.follow_up_question is not None


async def test_concrete_plan_with_timeline_is_credible(provider):
    finding = FindingContext(title="Enforce MFA", description="...", required_evidence="screenshot", severity="critical")
    result = await provider.review_plan(
        finding, "We will deploy Okta MFA to all admin accounts and complete rollout within 3 weeks, targeting 2026-09-15.",
    )
    assert result.credible is True


async def test_empty_plan_is_not_credible(provider):
    finding = FindingContext(title="X", description="...", required_evidence=None, severity="low")
    result = await provider.review_plan(finding, "")
    assert result.credible is False


async def test_no_evidence_is_rejected(provider):
    finding = FindingContext(title="X", description="...", required_evidence="screenshot", severity="high")
    result = await provider.validate_evidence(finding, [], "")
    assert result.recommendation == "reject"


async def test_audit_report_evidence_is_approved(provider):
    finding = FindingContext(title="X", description="...", required_evidence=None, severity="high")
    evidence = [EvidenceContext(document_type="audit_report", original_filename="q3-audit.pdf")]
    result = await provider.validate_evidence(finding, evidence, "")
    assert result.recommendation == "approve"


async def test_lone_screenshot_on_critical_finding_needs_clarification(provider):
    finding = FindingContext(title="MFA everywhere", description="...", required_evidence=None, severity="critical")
    evidence = [EvidenceContext(document_type="screenshot", original_filename="mfa-1-account.png")]
    result = await provider.validate_evidence(finding, evidence, "")
    assert result.recommendation == "request_clarification"
    assert "scope" in result.follow_up_question.lower() or "systems" in result.follow_up_question.lower()


# ---------------------------------------------------------------------------
# Integration tests (live Postgres)
# ---------------------------------------------------------------------------

async def _create_vendor_and_finding(pool, *, severity="high", status="new"):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            """
            INSERT INTO vendors (legal_name, tier, status, data_access_level, risk_score)
            VALUES ($1, 'tier_2_high', 'active', 'confidential', 50)
            RETURNING id, legal_name
            """,
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        contact = await conn.fetchrow(
            """
            INSERT INTO vendor_contacts (vendor_id, full_name, email, is_primary)
            VALUES ($1, 'Test Contact', $2, true) RETURNING id
            """,
            vendor["id"], f"{uuid.uuid4().hex[:8]}@example.com",
        )
        finding = await conn.fetchrow(
            """
            INSERT INTO findings (vendor_id, title, description, severity, status, vendor_owner_contact_id, due_at)
            VALUES ($1, 'Test finding', 'Test description', $2, $3, $4, now() + interval '30 days')
            RETURNING *
            """,
            vendor["id"], severity, status, contact["id"],
        )
    return vendor, finding


async def test_acknowledge_requires_new_status(pool):
    vendor, finding = await _create_vendor_and_finding(pool, status="in_progress")
    async with pool.acquire() as conn:
        with pytest.raises(InvalidTransition):
            await ticket_engine.acknowledge_finding(conn, str(finding["id"]))


async def test_full_happy_path_acknowledge_plan_evidence_close(pool):
    vendor, finding = await _create_vendor_and_finding(pool, severity="high")
    finding_id = str(finding["id"])

    async with pool.acquire() as conn:
        await ticket_engine.acknowledge_finding(conn, finding_id)
        row = await conn.fetchrow("SELECT status FROM findings WHERE id = $1", finding_id)
        assert row["status"] == "assigned"

        plan_result = await ticket_engine.submit_remediation_plan(
            conn, finding_id,
            "We will deploy MFA to all admin accounts within 2 weeks, completing by 2026-09-10.",
        )
        assert plan_result["status"] == "in_progress"

        await conn.execute(
            "INSERT INTO remediation_evidence (finding_id, document_type, storage_uri, original_filename) "
            "VALUES ($1, 'audit_report', 'x/y.pdf', 'audit.pdf')",
            finding_id,
        )

        result = await ticket_engine.submit_for_validation(conn, finding_id)
        assert result["status"] == "closed"
        assert result["recommendation"] == "approve"

        final = await conn.fetchrow("SELECT status, closed_at FROM findings WHERE id = $1", finding_id)
        assert final["status"] == "closed"
        assert final["closed_at"] is not None

        vendor_row = await conn.fetchrow("SELECT risk_score FROM vendors WHERE id = $1", vendor["id"])
        assert float(vendor_row["risk_score"]) == 50.0 - 6.0  # 'high' severity closure reduction

        comments = await conn.fetch("SELECT author_type FROM finding_comments WHERE finding_id = $1", finding_id)
        assert any(c["author_type"] == "vendor" for c in comments)
        assert any(c["author_type"] == "system" for c in comments)


async def test_vague_plan_is_rejected_and_resubmittable(pool):
    vendor, finding = await _create_vendor_and_finding(pool)
    finding_id = str(finding["id"])
    async with pool.acquire() as conn:
        await ticket_engine.acknowledge_finding(conn, finding_id)
        result = await ticket_engine.submit_remediation_plan(conn, finding_id, "We will look into it.")
        assert result["status"] == "rejected"
        assert result["credible"] is False

        row = await conn.fetchrow("SELECT rejection_count FROM findings WHERE id = $1", finding_id)
        assert row["rejection_count"] == 1

        # vendor revises and resubmits — allowed from 'rejected'
        result2 = await ticket_engine.submit_remediation_plan(
            conn, finding_id, "We will deploy hardware MFA keys to all admins within 4 weeks, by 2026-10-01.",
        )
        assert result2["status"] == "in_progress"


async def test_insufficient_evidence_bounces_back_to_in_progress(pool):
    vendor, finding = await _create_vendor_and_finding(pool, severity="critical", status="in_progress")
    finding_id = str(finding["id"])
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO remediation_evidence (finding_id, document_type, storage_uri, original_filename) "
            "VALUES ($1, 'screenshot', 'x/y.png', 'one-account.png')",
            finding_id,
        )
        result = await ticket_engine.submit_for_validation(conn, finding_id)
        assert result["status"] == "rejected"
        assert result["recommendation"] == "request_clarification"

        row = await conn.fetchrow("SELECT status, rejection_count FROM findings WHERE id = $1", finding_id)
        assert row["status"] == "rejected"
        assert row["rejection_count"] == 1


async def test_submit_without_evidence_raises(pool):
    vendor, finding = await _create_vendor_and_finding(pool, status="in_progress")
    async with pool.acquire() as conn:
        with pytest.raises(InvalidTransition):
            await ticket_engine.submit_for_validation(conn, str(finding["id"]))


async def test_exception_request_and_approval(pool):
    vendor, finding = await _create_vendor_and_finding(pool, severity="medium", status="in_progress")
    finding_id = str(finding["id"])
    async with pool.acquire() as conn:
        exception = await ticket_engine.request_exception(
            conn, finding_id, "Legacy system cannot support MFA until Q3 migration.", "Compensating: IP allowlisting in place.",
        )
        assert exception["approved_at"] is None

        approved = await ticket_engine.approve_exception(conn, str(exception["id"]), None)
        assert approved["approved_at"] is not None

        finding_row = await conn.fetchrow("SELECT status FROM findings WHERE id = $1", finding_id)
        assert finding_row["status"] == "exception_granted"


# ---------------------------------------------------------------------------
# Finding generation triggers
# ---------------------------------------------------------------------------

async def test_finding_generated_from_alert_only_for_critical_high(pool):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) VALUES ($1, 'tier_3_medium', 'active', 'confidential') RETURNING id",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        medium_alert = await conn.fetchrow(
            "INSERT INTO monitoring_alerts (vendor_id, alert_type, severity, title, payload) "
            "VALUES ($1, 'news_reputation', 'medium', 'Some news', '{}'::jsonb) RETURNING *",
            vendor["id"],
        )
        no_finding = await finding_generator.create_finding_from_alert(conn, str(vendor["id"]), medium_alert)
        assert no_finding is None

        critical_alert = await conn.fetchrow(
            "INSERT INTO monitoring_alerts (vendor_id, alert_type, severity, title, payload) "
            "VALUES ($1, 'cve', 'critical', 'Critical CVE', '{}'::jsonb) RETURNING *",
            vendor["id"],
        )
        finding = await finding_generator.create_finding_from_alert(conn, str(vendor["id"]), critical_alert)
        assert finding is not None
        assert finding["severity"] == "critical"
        assert (finding["due_at"] - datetime.now(timezone.utc)).days <= 30

        # calling again for the same alert doesn't create a duplicate
        dup = await finding_generator.create_finding_from_alert(conn, str(vendor["id"]), critical_alert)
        assert dup is None


async def test_finding_generated_from_weak_assessment_response(pool):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) VALUES ($1, 'tier_1_critical', 'active', 'confidential') RETURNING id",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        template = await conn.fetchrow("SELECT id FROM questionnaire_templates WHERE tier = 'tier_4_low' LIMIT 1")
        question = await conn.fetchrow("SELECT id, evidence_required FROM questions WHERE template_id = $1 LIMIT 1", template["id"])
        assessment = await conn.fetchrow(
            "INSERT INTO assessments (vendor_id, template_id, status) VALUES ($1, $2, 'in_progress') RETURNING id",
            vendor["id"], template["id"],
        )
        await conn.execute(
            "INSERT INTO assessment_responses (assessment_id, question_id, raw_answer, classification) "
            "VALUES ($1, $2, 'not sure', 'missing')",
            assessment["id"], question["id"],
        )

        findings = await finding_generator.generate_findings_from_assessment(conn, str(assessment["id"]))
        assert len(findings) == 1
        assert findings[0]["source_assessment_id"] == assessment["id"]
        assert findings[0]["severity"] in ("critical", "high")  # 'missing' classification

        # re-running for the same assessment doesn't duplicate an open finding
        again = await finding_generator.generate_findings_from_assessment(conn, str(assessment["id"]))
        assert len(again) == 0


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

async def test_overdue_finding_transitions_and_notifies(pool):
    vendor, finding = await _create_vendor_and_finding(pool, status="in_progress")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE findings SET due_at = now() - interval '1 day' WHERE id = $1", finding["id"])
        overdue_count = await escalation_engine.check_overdue_findings(conn)
        assert overdue_count >= 1
        row = await conn.fetchrow("SELECT status FROM findings WHERE id = $1", finding["id"])
        assert row["status"] == "overdue"


async def test_severely_overdue_escalates_to_legal_once(pool):
    vendor, finding = await _create_vendor_and_finding(pool, status="overdue")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE findings SET due_at = now() - interval '20 days' WHERE id = $1", finding["id"])
        first = await escalation_engine.check_severely_overdue_findings(conn)
        assert first >= 1
        second = await escalation_engine.check_severely_overdue_findings(conn)
        # already escalated (audit log marker present) — this specific finding shouldn't fire again
        marker = await conn.fetchrow(
            "SELECT count(*) AS n FROM audit_logs WHERE action = 'finding.legal_escalated' AND entity_id = $1", finding["id"],
        )
        assert marker["n"] == 1


async def test_repeated_rejections_escalate_once(pool):
    vendor, finding = await _create_vendor_and_finding(pool, status="in_progress")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE findings SET rejection_count = 2 WHERE id = $1", finding["id"])
        first = await escalation_engine.check_repeated_rejections(conn)
        assert first >= 1
        marker = await conn.fetchrow(
            "SELECT count(*) AS n FROM audit_logs WHERE action = 'finding.repeated_rejection_escalated' AND entity_id = $1",
            finding["id"],
        )
        assert marker["n"] == 1


async def test_finding_endpoints_require_admin_key(client):
    r = await client.get("/admin/findings")
    assert r.status_code == 403


async def test_vendor_cannot_access_another_vendors_finding(client, pool):
    _, finding1 = await _create_vendor_and_finding(pool)
    vendor2, _ = await _create_vendor_and_finding(pool)
    async with pool.acquire() as conn:
        contact2 = await conn.fetchrow("SELECT id, email FROM vendor_contacts WHERE vendor_id = $1", vendor2["id"])

    from app.security import create_magic_link_token
    token = create_magic_link_token(contact2["id"], contact2["email"])
    session_resp = await client.post("/auth/verify", json={"token": token})
    access_token = session_resp.json()["access_token"]

    r = await client.get(f"/findings/{finding1['id']}", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 404
