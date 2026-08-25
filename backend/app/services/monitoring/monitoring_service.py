"""Orchestration for the four monitoring checks (Phase 2 spec §2). Each
`run_*_check` function is exactly what an Airflow DAG task calls — see
airflow_dags/ for the (unexecuted-in-this-environment, see that
directory's README) DAG definitions that schedule these on the spec's
documented cadence. Kept here as plain async functions, independent of
Airflow, so they're directly unit-testable and callable from the
`/admin/monitoring/run-checks` endpoint for local demo/dev use.
"""

from datetime import datetime, timezone

import asyncpg

from app.services.monitoring import alert_engine
from app.services.monitoring.alert_engine import VendorRef
from app.services.monitoring.factory import (
    get_breach_provider, get_cert_registry_provider, get_financial_provider, get_news_provider,
)
from app.services.monitoring.impact_assessor import create_incident_finding
from app.services.monitoring.types import VendorInfo
from app.services.playbooks.playbook_engine import trigger_playbook
from app.services.remediation.finding_generator import create_finding_from_alert


async def _active_vendors(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT id, legal_name, primary_domain, tier, risk_score FROM vendors WHERE status != 'terminated'",
    )


def _vendor_ref(v: asyncpg.Record) -> VendorRef:
    return VendorRef(str(v["id"]), v["legal_name"], float(v["risk_score"]) if v["risk_score"] is not None else None)


def _vendor_info(v: asyncpg.Record) -> VendorInfo:
    return VendorInfo(id=str(v["id"]), legal_name=v["legal_name"], primary_domain=v["primary_domain"], tier=v["tier"])


async def _touch_source(conn: asyncpg.Connection, code: str, success: bool, error: str | None = None) -> None:
    await conn.execute(
        """
        UPDATE monitoring_sources SET last_checked_at = now(), last_error = $3,
            last_success_at = CASE WHEN $2 THEN now() ELSE last_success_at END
        WHERE code = $1
        """,
        code, success, error,
    )


def _cert_severity(days_until_expiry: int | None) -> str:
    days = days_until_expiry if days_until_expiry is not None else 999
    if days <= 30:
        return "critical"
    if days <= 60:
        return "high"
    return "medium"


def _cve_severity(cvss_score: float | None) -> str:
    score = cvss_score if cvss_score is not None else 5.0
    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


async def run_certification_check(pool: asyncpg.Pool) -> int:
    provider = get_cert_registry_provider()
    created = 0
    async with pool.acquire() as conn:
        try:
            for v in await _active_vendors(conn):
                for signal in await provider.check(_vendor_info(v)):
                    if signal.status not in ("expiring_soon", "expired"):
                        continue
                    severity = "critical" if signal.status == "expired" else _cert_severity(signal.days_until_expiry)
                    alert = await alert_engine.raise_alert(
                        conn, _vendor_ref(v), alert_type="cert_expiry", severity=severity,
                        title=f"{signal.certificate_type} {signal.status.replace('_', ' ')}",
                        payload={
                            "certificate_type": signal.certificate_type, "status": signal.status,
                            "expiration_date": signal.expiration_date.isoformat() if signal.expiration_date else None,
                            "days_until_expiry": signal.days_until_expiry, "auditor": signal.auditor,
                        },
                        detail_lines=[
                            f"Certificate: {signal.certificate_type}", f"Expiration: {signal.expiration_date}",
                            f"Days remaining: {signal.days_until_expiry}", f"Auditor: {signal.auditor}",
                        ],
                        source_code="cert_registry",
                    )
                    if alert:
                        created += 1
                        await create_finding_from_alert(conn, str(v["id"]), alert)
                        if severity == "critical":
                            await trigger_playbook(
                                conn, "alert.cert_expiry.critical", str(v["id"]),
                                {"vendor_name": v["legal_name"]}, alert_id=str(alert["id"]),
                            )
            await _touch_source(conn, "cert_registry", True)
        except Exception as e:  # noqa: BLE001 — recorded on the source row, then re-raised
            await _touch_source(conn, "cert_registry", False, str(e))
            raise
    return created


async def run_breach_check(pool: asyncpg.Pool) -> int:
    provider = get_breach_provider()
    created = 0
    async with pool.acquire() as conn:
        try:
            for v in await _active_vendors(conn):
                for signal in await provider.check(_vendor_info(v)):
                    if signal.kind == "breach":
                        alert = await alert_engine.raise_alert(
                            conn, _vendor_ref(v), alert_type="breach", severity="critical", title=signal.headline,
                            payload={"source": signal.source, **signal.detail},
                            detail_lines=[f"Source: {signal.source}", *(f"{k}: {v2}" for k, v2 in signal.detail.items())],
                            source_code="breach_vuln",
                        )
                        if alert:
                            created += 1
                            await create_incident_finding(conn, str(v["id"]), alert)
                            await trigger_playbook(
                                conn, "alert.breach.critical", str(v["id"]),
                                {"vendor_name": v["legal_name"]}, alert_id=str(alert["id"]),
                            )
                    else:  # 'cve'
                        severity = _cve_severity(signal.detail.get("cvss_score"))
                        alert = await alert_engine.raise_alert(
                            conn, _vendor_ref(v), alert_type="cve", severity=severity, title=signal.headline,
                            payload={"source": signal.source, **signal.detail},
                            detail_lines=[f"Source: {signal.source}", *(f"{k}: {v2}" for k, v2 in signal.detail.items())],
                            source_code="breach_vuln",
                        )
                        if alert:
                            created += 1
                            await create_finding_from_alert(conn, str(v["id"]), alert)
            await _touch_source(conn, "breach_vuln", True)
        except Exception as e:  # noqa: BLE001
            await _touch_source(conn, "breach_vuln", False, str(e))
            raise
    return created


async def run_news_check(pool: asyncpg.Pool) -> int:
    provider = get_news_provider()
    created = 0
    async with pool.acquire() as conn:
        try:
            for v in await _active_vendors(conn):
                for signal in await provider.check(_vendor_info(v)):
                    if signal.sentiment != "negative":
                        continue  # only material/negative news raises an alert
                    alert = await alert_engine.raise_alert(
                        conn, _vendor_ref(v), alert_type="news_reputation", severity="medium", title=signal.headline,
                        payload={
                            "source_url": signal.source_url, "sentiment": signal.sentiment,
                            "story_type": signal.story_type, "summary": signal.summary,
                            "published_at": signal.published_at.isoformat(),
                        },
                        detail_lines=[f"Story: {signal.headline}", f"Type: {signal.story_type}", signal.summary],
                        source_code="news",
                    )
                    if alert:
                        created += 1
            await _touch_source(conn, "news", True)
        except Exception as e:  # noqa: BLE001
            await _touch_source(conn, "news", False, str(e))
            raise
    return created


async def run_financial_check(pool: asyncpg.Pool) -> int:
    provider = get_financial_provider()
    created = 0
    async with pool.acquire() as conn:
        try:
            for v in await _active_vendors(conn):
                for signal in await provider.check(_vendor_info(v)):
                    alert = await alert_engine.raise_alert(
                        conn, _vendor_ref(v), alert_type="financial_distress", severity=signal.severity,
                        title=signal.detail,
                        payload={"signal_type": signal.signal_type, "source": signal.source},
                        detail_lines=[f"Signal: {signal.signal_type}", signal.detail, f"Source: {signal.source}"],
                        source_code="financial",
                    )
                    if alert:
                        created += 1
                        await create_finding_from_alert(conn, str(v["id"]), alert)
                        if signal.severity in ("critical", "high"):
                            await trigger_playbook(
                                conn, "alert.financial_distress.high", str(v["id"]),
                                {"vendor_name": v["legal_name"]}, alert_id=str(alert["id"]),
                            )
            await _touch_source(conn, "financial", True)
        except Exception as e:  # noqa: BLE001
            await _touch_source(conn, "financial", False, str(e))
            raise
    return created


async def run_all_checks(pool: asyncpg.Pool) -> dict:
    return {
        "cert_expiry": await run_certification_check(pool),
        "breach_cve": await run_breach_check(pool),
        "news": await run_news_check(pool),
        "financial": await run_financial_check(pool),
        "escalations": await alert_engine.run_escalation_check(pool),
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
