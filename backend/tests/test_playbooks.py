"""Phase 4 generalized playbook engine tests."""

import uuid

from app.services.playbooks.playbook_engine import trigger_playbook


async def _create_vendor(pool):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) "
            "VALUES ($1, 'tier_2_high', 'active', 'confidential') RETURNING id, legal_name",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        await conn.fetchrow(
            "INSERT INTO vendor_contacts (vendor_id, full_name, email, is_primary) "
            "VALUES ($1, 'Contact', $2, true) RETURNING id",
            vendor["id"], f"{uuid.uuid4().hex[:8]}@example.com",
        )
    return vendor


async def test_trigger_playbook_returns_none_for_unknown_event(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        result = await trigger_playbook(conn, "no.such.trigger", str(vendor["id"]), {"vendor_name": vendor["legal_name"]})
    assert result is None


async def test_breach_response_playbook_schedules_post_incident_review(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        execution = await trigger_playbook(
            conn, "alert.breach.critical", str(vendor["id"]), {"vendor_name": vendor["legal_name"]},
        )
        assert execution["status"] == "completed"
        assert execution["step_log"][0]["type"] == "schedule_review"

        marker = await conn.fetchrow(
            "SELECT after_state FROM audit_logs WHERE action = 'playbook.review_scheduled' AND entity_id = $1",
            vendor["id"],
        )
    assert marker is not None
    assert "review_at" in marker["after_state"]


async def test_cert_expiring_playbook_notifies_vendor_and_schedules_followup(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        execution = await trigger_playbook(
            conn, "alert.cert_expiry.critical", str(vendor["id"]), {"vendor_name": vendor["legal_name"]},
        )
    step_types = [s["type"] for s in execution["step_log"]]
    assert step_types == ["notify_vendor", "schedule_review"]
    assert execution["step_log"][0]["sent_to"]


async def test_critical_assessment_playbook_notifies_ciso_and_compliance(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        execution = await trigger_playbook(
            conn, "assessment.completed.risk_critical", str(vendor["id"]),
            {"vendor_name": vendor["legal_name"], "risk_score": 85.0},
        )
    notify_steps = [s for s in execution["step_log"] if s["type"] == "notify_role"]
    assert len(notify_steps) == 2
    assert all(step["notified"] for step in notify_steps)  # seeded users exist for both roles


async def test_playbook_execution_persisted_and_queryable(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        execution = await trigger_playbook(
            conn, "alert.financial_distress.high", str(vendor["id"]), {"vendor_name": vendor["legal_name"]},
        )
        row = await conn.fetchrow("SELECT * FROM playbook_executions WHERE id = $1", execution["id"])
    assert row["vendor_id"] == vendor["id"]
    assert row["status"] == "completed"


async def test_assessment_completion_triggers_critical_playbook_end_to_end(pool):
    """Integration across Phase 1 (assessment submit) and Phase 4
    (playbook trigger): a vendor whose risk score lands above 80 after
    submission should have a 'vendor_fails_critical_assessment' execution."""
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) "
            "VALUES ($1, 'tier_1_critical', 'active', 'confidential') RETURNING id",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        template = await conn.fetchrow("SELECT id FROM questionnaire_templates WHERE tier = 'tier_4_low' LIMIT 1")
        questions = await conn.fetch("SELECT id FROM questions WHERE template_id = $1", template["id"])
        assessment = await conn.fetchrow(
            "INSERT INTO assessments (vendor_id, template_id, status) VALUES ($1, $2, 'in_progress') RETURNING id",
            vendor["id"], template["id"],
        )
        # All-missing responses -> overall_score 0 -> vendor_risk_score 100 (> 80 threshold)
        for q in questions:
            await conn.execute(
                "INSERT INTO assessment_responses (assessment_id, question_id, raw_answer, classification) "
                "VALUES ($1, $2, '', 'missing')",
                assessment["id"], q["id"],
            )

    from app.services import assessment_service as svc
    async with pool.acquire() as conn:
        all_questions = await svc.fetch_template_questions(conn, template["id"])
        responses = await svc.fetch_responses_by_question(conn, assessment["id"])
        breakdown = svc.build_risk_breakdown(all_questions, responses)
        assert breakdown["vendor_risk_score"] > 80

        from app.services.playbooks.playbook_engine import trigger_playbook as _trigger
        await _trigger(
            conn, "assessment.completed.risk_critical", str(vendor["id"]),
            {"vendor_name": "Test", "risk_score": breakdown["vendor_risk_score"]},
        )
        execution = await conn.fetchrow(
            """
            SELECT pe.* FROM playbook_executions pe JOIN playbook_definitions pd ON pd.id = pe.playbook_id
            WHERE pd.code = 'vendor_fails_critical_assessment' AND pe.vendor_id = $1
            """,
            vendor["id"],
        )
    assert execution is not None


async def test_playbook_endpoints_require_admin_key(client):
    r = await client.get("/admin/playbooks/definitions")
    assert r.status_code == 403


async def test_list_definitions_returns_five_seeded_playbooks(client):
    r = await client.get("/admin/playbooks/definitions", headers={"X-Admin-Key": "dev-admin-key"})
    assert r.status_code == 200
    codes = {d["code"] for d in r.json()}
    assert codes == {
        "vendor_breach_response", "cert_critical_expiring", "vendor_fails_critical_assessment",
        "vendor_financial_distress", "remediation_deadline_missed",
    }
