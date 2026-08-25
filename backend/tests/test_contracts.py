"""Phase 4 contract parsing & compliance tests."""

import io
import uuid

import pytest

from app.services.contracts.contract_compliance import check_contract_compliance, generate_obligations
from app.services.contracts.contract_parser import MockContractParserProvider
from app.services.contracts.pdf_text import extract_text

SAMPLE_CONTRACT = """
MASTER SERVICES AGREEMENT

1. Service Levels. Vendor shall maintain 99.9% monthly uptime for the Service.

2. Security Requirements. Vendor shall maintain SOC 2 Type II certification
throughout the term of this Agreement. Vendor shall encrypt all Customer Data
at rest and in transit using industry-standard encryption.

3. Incident Notification. In the event of a security incident affecting
Customer Data, Vendor shall notify Customer within 72 hours of discovery.

4. Audit Rights. Customer shall have the right to audit Vendor's security
controls annually upon 30 days written notice.

5. Liability. Vendor's aggregate liability under this Agreement shall not
exceed the fees paid in the preceding 12 months.

6. Indemnification. Vendor shall indemnify and hold harmless Customer from
any claims arising from Vendor's breach of this Agreement.

7. Term and Termination. Either party may terminate this Agreement upon 60
days prior written notice. This Agreement shall automatically renew for
successive one-year terms unless either party provides 90 days notice of
non-renewal.
"""


@pytest.fixture
def provider():
    return MockContractParserProvider()


async def test_extracts_uptime_and_notification_sla(provider):
    terms = await provider.extract_terms(SAMPLE_CONTRACT)
    assert terms.sla_uptime_pct == 99.9
    assert terms.incident_notification_sla_hours == 72


async def test_extracts_security_requirements(provider):
    terms = await provider.extract_terms(SAMPLE_CONTRACT)
    assert any("SOC 2 Type II" in r for r in terms.security_requirements)
    assert any("encrypt" in r.lower() for r in terms.security_requirements)


async def test_extracts_termination_and_renewal_terms(provider):
    terms = await provider.extract_terms(SAMPLE_CONTRACT)
    assert terms.termination_notice_days == 60
    assert terms.auto_renews is True
    assert terms.renewal_notice_days == 90


async def test_extracts_audit_and_liability_clauses(provider):
    """Also guards against a real bug found while smoke-testing: numbered
    section headings ("5. Liability.") contain the keyword too and would
    match first if the sentence-matcher didn't skip anything too short to
    be an actual clause — assert the *substantive* sentence, not the title."""
    terms = await provider.extract_terms(SAMPLE_CONTRACT)
    normalize = lambda s: " ".join(s.lower().split())  # the source text line-wraps mid-clause
    assert terms.audit_rights and "right to audit" in normalize(terms.audit_rights)
    assert terms.liability_cap and "shall not exceed the fees paid" in normalize(terms.liability_cap)
    assert terms.indemnification and "indemnify and hold harmless" in normalize(terms.indemnification)


async def test_contract_with_no_matching_clauses_returns_empty_terms(provider):
    terms = await provider.extract_terms("This is a short, generic services agreement with no specific terms.")
    assert terms.sla_uptime_pct is None
    assert terms.incident_notification_sla_hours is None
    assert terms.security_requirements == []
    assert terms.auto_renews is False


def test_extract_text_plain_txt_fallback():
    text = extract_text("contract.txt", SAMPLE_CONTRACT.encode("utf-8"))
    assert "SOC 2 Type II" in text


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

async def _create_vendor(pool):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "INSERT INTO vendors (legal_name, tier, status, data_access_level, risk_score) "
            "VALUES ($1, 'tier_1_critical', 'active', 'confidential', 20) RETURNING id, legal_name",
            f"Test Vendor {uuid.uuid4().hex[:8]}",
        )


async def test_generate_obligations_from_extracted_terms(pool):
    vendor = await _create_vendor(pool)
    provider = MockContractParserProvider()
    terms = await provider.extract_terms(SAMPLE_CONTRACT)

    async with pool.acquire() as conn:
        contract = await conn.fetchrow(
            "INSERT INTO contracts (vendor_id, contract_name, storage_uri, effective_date) "
            "VALUES ($1, 'MSA', 'x/y.txt', CURRENT_DATE) RETURNING id",
            vendor["id"],
        )
        obligations = await generate_obligations(conn, str(contract["id"]), terms)

    assert len(obligations) >= 3  # security requirements + notification SLA + uptime
    types = {o["obligation_type"] for o in obligations}
    assert "certification" in types
    assert "notification_sla" in types
    assert "sla_uptime" in types


async def test_compliance_check_flags_expired_certification(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        contract = await conn.fetchrow(
            "INSERT INTO contracts (vendor_id, contract_name, storage_uri, effective_date) "
            "VALUES ($1, 'MSA', 'x/y.txt', CURRENT_DATE) RETURNING id",
            vendor["id"],
        )
        await conn.execute(
            "INSERT INTO contract_obligations (contract_id, description, obligation_type, check_frequency) "
            "VALUES ($1, 'Vendor shall maintain SOC 2 Type II certification.', 'certification', 'annually')",
            contract["id"],
        )

        # No expired-cert alert yet -> compliant
        results = await check_contract_compliance(conn, str(vendor["id"]))
        assert results[0]["status"] == "compliant"

        # Now record an expired certification alert
        await conn.execute(
            "INSERT INTO monitoring_alerts (vendor_id, alert_type, severity, status, title, payload) "
            "VALUES ($1, 'cert_expiry', 'critical', 'new', 'SOC 2 expired', '{\"status\": \"expired\"}'::jsonb)",
            vendor["id"],
        )
        results = await check_contract_compliance(conn, str(vendor["id"]))
        assert results[0]["status"] == "non_compliant"

        violation_alert = await conn.fetchrow(
            "SELECT id FROM monitoring_alerts WHERE vendor_id = $1 AND alert_type = 'contract_violation'", vendor["id"],
        )
        assert violation_alert is not None


async def test_vendor_with_no_active_contract_has_nothing_to_check(pool):
    vendor = await _create_vendor(pool)
    async with pool.acquire() as conn:
        results = await check_contract_compliance(conn, str(vendor["id"]))
    assert results == []


async def test_contract_upload_endpoint_requires_admin_key(client):
    files = {"file": ("c.txt", b"some contract text", "text/plain")}
    r = await client.post(
        f"/admin/vendors/{uuid.uuid4()}/contracts", files=files,
        data={"contract_name": "MSA", "effective_date": "2026-01-01"},
    )
    assert r.status_code == 403
