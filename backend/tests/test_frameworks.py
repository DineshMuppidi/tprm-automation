"""Phase 4 control-framework mapping & coverage tests."""

import uuid

from app.services.frameworks import coverage


async def _create_vendor_with_covered_control(pool):
    """Creates a vendor with one completed assessment where a single
    response (mapped to NIST_CSF_2 PR.AC-1, which is cross-framework
    -mapped to SOC2/ISO27001/HIPAA controls in the Phase 0 seed data) is
    classified 'strong' — i.e. covered."""
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) "
            "VALUES ($1, 'tier_1_critical', 'active', 'confidential') RETURNING id",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        control = await conn.fetchrow(
            """
            SELECT c.id FROM controls c JOIN frameworks f ON f.id = c.framework_id
            WHERE f.code = 'NIST_CSF_2' AND c.control_ref = 'PR.AC-1'
            """,
        )
        template = await conn.fetchrow("SELECT id FROM questionnaire_templates WHERE tier = 'tier_1_critical' LIMIT 1")
        question = await conn.fetchrow(
            "SELECT id FROM questions WHERE template_id = $1 AND control_id = $2 LIMIT 1", template["id"], control["id"],
        )
        assessment = await conn.fetchrow(
            "INSERT INTO assessments (vendor_id, template_id, status, completed_at) "
            "VALUES ($1, $2, 'completed', now()) RETURNING id",
            vendor["id"], template["id"],
        )
        await conn.execute(
            "INSERT INTO assessment_responses (assessment_id, question_id, raw_answer, classification) "
            "VALUES ($1, $2, 'MFA enforced everywhere.', 'strong')",
            assessment["id"], question["id"],
        )
    return vendor, control


async def test_vendor_framework_coverage_reflects_strong_response(pool):
    vendor, control = await _create_vendor_with_covered_control(pool)
    async with pool.acquire() as conn:
        result = await coverage.vendor_framework_coverage(conn, str(vendor["id"]))
    assert result["NIST_CSF_2"]["covered"] >= 1
    assert result["NIST_CSF_2"]["pct"] > 0


async def test_cross_framework_coverage_credited_via_mapping(pool):
    """The vendor only answered a NIST_CSF_2 question — this asserts SOC2
    coverage is nonzero too, because PR.AC-1 is mapped to SOC2 CC6.1 in the
    Phase 0 seed data. This is the spec's own "vendor covers X% of NIST CSF,
    Y% of SOC 2" claim, made real."""
    vendor, control = await _create_vendor_with_covered_control(pool)
    async with pool.acquire() as conn:
        result = await coverage.vendor_framework_coverage(conn, str(vendor["id"]))
    assert result["SOC2"]["covered"] >= 1


async def test_gap_analysis_lists_uncovered_hipaa_controls(pool):
    vendor, control = await _create_vendor_with_covered_control(pool)
    async with pool.acquire() as conn:
        result = await coverage.framework_gap_analysis(conn, str(vendor["id"]), "HIPAA")
    assert result["framework_code"] == "HIPAA"
    assert len(result["gaps"]) > 0  # a vendor with one answered question doesn't cover all of HIPAA
    assert result["coverage_pct"] < 100.0


async def test_vendor_with_no_assessment_has_zero_coverage(pool):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level) "
            "VALUES ($1, 'tier_4_low', 'onboarding', 'none') RETURNING id",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )
        result = await coverage.vendor_framework_coverage(conn, str(vendor["id"]))
    assert all(fw["covered"] == 0 for fw in result.values())


async def test_related_controls_returns_seeded_cross_framework_mappings(pool):
    async with pool.acquire() as conn:
        control = await conn.fetchrow(
            """
            SELECT c.id FROM controls c JOIN frameworks f ON f.id = c.framework_id
            WHERE f.code = 'NIST_CSF_2' AND c.control_ref = 'PR.AC-1'
            """,
        )
        related = await coverage.related_controls(conn, str(control["id"]))
    frameworks_found = {r["framework_code"] for r in related}
    assert "SOC2" in frameworks_found
    assert "ISO27001" in frameworks_found
    assert all(0 <= r["confidence"] <= 1 for r in related)


async def test_control_coverage_scorecard_is_sorted_by_critical_gaps(pool):
    scorecard = await coverage.control_coverage_scorecard(pool)
    assert len(scorecard) > 0
    gap_counts = [s["critical_tier_gaps"] for s in scorecard]
    assert gap_counts == sorted(gap_counts, reverse=True)


async def test_framework_endpoints_require_admin_key(client):
    r = await client.get(f"/admin/vendors/{uuid.uuid4()}/framework-coverage")
    assert r.status_code == 403
