"""Phase 2 monitoring tests. Unit tests for pure logic (risk deltas, mock
provider determinism, news classification) plus integration tests against
the live Postgres instance (same conftest.py pool/client fixtures as
Phase 1's tests)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.monitoring import alert_engine
from app.services.monitoring.alert_engine import VendorRef, compute_risk_delta
from app.services.monitoring.mock_providers import (
    INCIDENT_VENDOR_DOMAIN, MockBreachProvider, MockCertRegistryProvider, MockFinancialProvider, MockNewsProvider,
)
from app.services.monitoring.monitoring_service import run_all_checks
from app.services.monitoring.news_classifier import classify_news_article
from app.services.monitoring.types import VendorInfo


# ---------------------------------------------------------------------------
# Pure unit tests
# ---------------------------------------------------------------------------

def test_risk_delta_matches_spec_examples():
    # Phase 2 spec §4 example: "Auto-update vendor risk score: +25 points (serious incident)"
    assert compute_risk_delta("breach", "critical") == 25.0
    assert compute_risk_delta("cert_expiry", "critical") == 10.0
    assert compute_risk_delta("financial_distress", "high") == 15.0


def test_news_classifier_detects_negative_breach_story():
    sentiment, story_type = classify_news_article("Acme Corp discloses ransomware breach", "")
    assert sentiment == "negative"
    assert story_type == "breach"


def test_news_classifier_detects_positive_story():
    sentiment, story_type = classify_news_article("Acme Corp announces new funding round and partnership", "")
    assert sentiment == "positive"


async def test_mock_providers_are_deterministic_across_calls():
    vendor = VendorInfo(id="v1", legal_name="Some Vendor", primary_domain="somevendor.example.com", tier="tier_3_medium")
    provider = MockCertRegistryProvider()
    first = await provider.check(vendor)
    second = await provider.check(vendor)
    assert first == second  # same vendor -> same signal every run (no alert spam)


async def test_incident_vendor_triggers_full_scenario_across_all_sources():
    vendor = VendorInfo(id="v2", legal_name="Acme HR Solutions, Inc.", primary_domain=INCIDENT_VENDOR_DOMAIN, tier="tier_1_critical")

    cert_signals = await MockCertRegistryProvider().check(vendor)
    assert cert_signals[0].status == "expiring_soon"
    assert cert_signals[0].days_until_expiry == 21

    breach_signals = await MockBreachProvider().check(vendor)
    assert breach_signals[0].kind == "breach"
    assert breach_signals[0].detail["estimated_records_affected"] == 50000

    news_signals = await MockNewsProvider().check(vendor)
    assert news_signals[0].sentiment == "negative"

    financial_signals = await MockFinancialProvider().check(vendor)
    assert financial_signals[0].signal_type == "credit_downgrade"


# ---------------------------------------------------------------------------
# Integration tests (live Postgres — see conftest.py)
# ---------------------------------------------------------------------------

async def _create_vendor(pool, *, domain: str | None = None, risk_score: float | None = None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO vendors (legal_name, primary_domain, tier, status, data_access_level, risk_score)
            VALUES ($1, $2, 'tier_1_critical', 'active', 'restricted_pii', $3)
            RETURNING id, legal_name, risk_score
            """,
            f"Test Vendor {uuid.uuid4().hex[:8]}", domain, risk_score,
        )
    return row


async def test_raise_alert_is_deduped_on_second_call(pool):
    vendor = await _create_vendor(pool)
    ref = VendorRef(str(vendor["id"]), vendor["legal_name"], None)
    async with pool.acquire() as conn:
        first = await alert_engine.raise_alert(
            conn, ref, alert_type="breach", severity="critical", title="Test breach",
            payload={"x": 1}, detail_lines=["line"],
        )
        second = await alert_engine.raise_alert(
            conn, ref, alert_type="breach", severity="critical", title="Test breach (again)",
            payload={"x": 1}, detail_lines=["line"],
        )
    assert first is not None
    assert second is None  # deduped — an open alert of this type already exists


async def test_raise_alert_applies_risk_delta_and_caps_at_100(pool):
    vendor = await _create_vendor(pool, risk_score=95.0)
    ref = VendorRef(str(vendor["id"]), vendor["legal_name"], 95.0)
    async with pool.acquire() as conn:
        await alert_engine.raise_alert(
            conn, ref, alert_type="breach", severity="critical", title="Test breach",
            payload={}, detail_lines=[],
        )
        updated = await conn.fetchrow("SELECT risk_score FROM vendors WHERE id = $1", vendor["id"])
    assert float(updated["risk_score"]) == 100.0  # 95 + 25 capped at 100


async def test_suppressed_alert_does_not_move_risk_score(pool):
    vendor = await _create_vendor(pool, risk_score=10.0)
    ref = VendorRef(str(vendor["id"]), vendor["legal_name"], 10.0)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO alert_suppressions (vendor_id, alert_type, reason, expires_at) "
            "VALUES ($1, 'breach', 'known false positive', now() + interval '90 days')",
            vendor["id"],
        )
        alert = await alert_engine.raise_alert(
            conn, ref, alert_type="breach", severity="critical", title="Test breach",
            payload={}, detail_lines=[],
        )
        updated = await conn.fetchrow("SELECT risk_score FROM vendors WHERE id = $1", vendor["id"])

    assert alert["status"] == "suppressed"
    assert float(updated["risk_score"]) == 10.0  # unchanged


async def test_full_incident_scenario_end_to_end(pool):
    """Reproduces the ransomware scenario end to end: run_all_checks against
    the incident-vendor domain raises one alert per source for THIS vendor,
    auto-creates a critical incident finding, and updates its risk score —
    then a second run creates nothing new for it (dedup holds).

    Assertions are scoped to this test's own vendor_id rather than
    run_all_checks' global counts, deliberately — run_all_checks processes
    every active vendor in the database, including ones other tests (or a
    developer's own manual testing session) may have left behind sharing
    the same demo incident domain, and this test's correctness shouldn't
    depend on the database being pristine.
    """
    vendor = await _create_vendor(pool, domain=INCIDENT_VENDOR_DOMAIN)

    await run_all_checks(pool)

    async with pool.acquire() as conn:
        alerts = await conn.fetch("SELECT alert_type, severity FROM monitoring_alerts WHERE vendor_id = $1", vendor["id"])
        finding = await conn.fetchrow("SELECT severity, status FROM findings WHERE vendor_id = $1", vendor["id"])
        updated_vendor = await conn.fetchrow("SELECT risk_score FROM vendors WHERE id = $1", vendor["id"])

    alert_types = {a["alert_type"] for a in alerts}
    assert alert_types == {"cert_expiry", "breach", "news_reputation", "financial_distress"}
    assert finding is not None
    assert finding["severity"] == "critical"
    assert float(updated_vendor["risk_score"]) == 48.0  # 10 + 25 + 5 + 8, see alert-routing.md

    await run_all_checks(pool)
    async with pool.acquire() as conn:
        alerts_after_second_run = await conn.fetch(
            "SELECT id FROM monitoring_alerts WHERE vendor_id = $1", vendor["id"],
        )
    assert len(alerts_after_second_run) == len(alerts)  # nothing new for this vendor — dedup held


async def test_escalation_after_sla_breach(pool):
    vendor = await _create_vendor(pool)
    ref = VendorRef(str(vendor["id"]), vendor["legal_name"], None)
    async with pool.acquire() as conn:
        alert = await alert_engine.raise_alert(
            conn, ref, alert_type="breach", severity="critical", title="Test breach",
            payload={}, detail_lines=[],
        )
        await conn.execute(
            "UPDATE monitoring_alerts SET detected_at = $2 WHERE id = $1",
            alert["id"], datetime.now(timezone.utc) - timedelta(hours=2),
        )

    escalated_count = await alert_engine.run_escalation_check(pool)
    assert escalated_count >= 1

    async with pool.acquire() as conn:
        updated = await conn.fetchrow("SELECT status FROM monitoring_alerts WHERE id = $1", alert["id"])
    assert updated["status"] == "escalated"


async def test_monitoring_endpoints_require_admin_key(client):
    r = await client.get("/admin/monitoring/alerts")
    assert r.status_code == 403
