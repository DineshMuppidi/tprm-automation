"""Alert persistence, deduplication, suppression, risk-score impact, and
routing (Phase 2 spec §3, §7). This is the one place that writes to
`monitoring_alerts` and adjusts `vendors.risk_score` for monitoring-driven
changes — providers never touch the database directly (Phase 0 threat
model §6: a monitoring source can only ever *create an alert candidate*
through this reviewed path, never change vendor state on its own).

Dedup/suppression policy (documented, not hidden in the code):
  * Suppression: if an active `alert_suppressions` row matches this
    vendor+alert_type (or a global rule with vendor_id NULL), the alert is
    still recorded — status='suppressed' — so it stays in the audit trail,
    but it does not move the risk score and does not send email. Spec §7:
    "Track suppression decisions... if this alert fires again, we need to
    re-evaluate", which requires the row to exist, not be dropped.
  * Deduplication: at most one *open* alert (status new/acknowledged/
    escalated) per (vendor, alert_type) at a time. A source that reports
    the same ongoing issue on every run doesn't create N alerts — it
    creates one, which stays open until someone resolves it. Finer-grained
    fingerprinting (e.g. detecting a cert's expiry date itself changing)
    is a documented future refinement, not implemented here.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg

from app.config import get_settings
from app.services.email_service import send_alert_notification

logger = logging.getLogger("tprm.monitoring.alerts")

OPEN_STATUSES = ("new", "acknowledged", "escalated")

# severity -> internal roles notified (Phase 2 spec §3 "Recipients" table)
ROUTING = {
    "critical": ("ciso", "compliance_officer", "category_manager", "legal"),
    "high": ("ciso", "compliance_officer"),
    "medium": ("compliance_officer",),
    "low": (),
}

RISK_DELTA = {
    ("breach", None): 25.0,
    ("cert_expiry", "critical"): 10.0,
    ("cert_expiry", "high"): 6.0,
    ("cert_expiry", "medium"): 3.0,
    ("cve", "critical"): 8.0,
    ("cve", "high"): 5.0,
    ("cve", "medium"): 3.0,
    ("cve", "low"): 1.0,
    ("news_reputation", None): 5.0,
    ("financial_distress", "high"): 15.0,
    ("financial_distress", "medium"): 8.0,
    ("financial_distress", "low"): 3.0,
}


def compute_risk_delta(alert_type: str, severity: str) -> float:
    return RISK_DELTA.get((alert_type, severity), RISK_DELTA.get((alert_type, None), 3.0))


@dataclass
class VendorRef:
    id: str
    legal_name: str
    risk_score: float | None


async def _find_suppression(conn: asyncpg.Connection, vendor_id: str, alert_type: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT id FROM alert_suppressions
        WHERE (vendor_id = $1 OR vendor_id IS NULL) AND (alert_type = $2 OR alert_type IS NULL)
          AND expires_at > now()
        LIMIT 1
        """,
        vendor_id, alert_type,
    )


async def _find_open_alert(conn: asyncpg.Connection, vendor_id: str, alert_type: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT id FROM monitoring_alerts
        WHERE vendor_id = $1 AND alert_type = $2 AND status = ANY($3::alert_status[])
        LIMIT 1
        """,
        vendor_id, alert_type, list(OPEN_STATUSES),
    )


async def _recipients_for(conn: asyncpg.Connection, severity: str) -> list[str]:
    roles = ROUTING.get(severity, ())
    if not roles:
        return []
    rows = await conn.fetch("SELECT email FROM users WHERE role = ANY($1::user_role[]) AND is_active", list(roles))
    return [r["email"] for r in rows]


async def raise_alert(
    conn: asyncpg.Connection, vendor: VendorRef, *, alert_type: str, severity: str,
    title: str, payload: dict, detail_lines: list[str], source_code: str | None = None,
) -> asyncpg.Record | None:
    """Returns the persisted alert row, or None if a duplicate open alert
    already exists (nothing new was recorded)."""

    if await _find_open_alert(conn, vendor.id, alert_type):
        logger.info("Deduped %s alert for vendor %s (already open)", alert_type, vendor.id)
        return None

    suppressed = await _find_suppression(conn, vendor.id, alert_type)
    status = "suppressed" if suppressed else "new"
    risk_delta = 0.0 if suppressed else compute_risk_delta(alert_type, severity)

    source_row = await conn.fetchrow("SELECT id FROM monitoring_sources WHERE code = $1", source_code) if source_code else None

    alert = await conn.fetchrow(
        """
        INSERT INTO monitoring_alerts (vendor_id, source_id, alert_type, severity, status, title, payload, risk_score_delta)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        vendor.id, source_row["id"] if source_row else None, alert_type, severity, status, title, payload, risk_delta,
    )

    if status == "suppressed":
        return alert

    risk_before = vendor.risk_score
    risk_after = min(100.0, (risk_before or 0.0) + risk_delta) if risk_delta else risk_before
    if risk_delta:
        await conn.execute(
            "UPDATE vendors SET risk_score = $2, risk_score_updated_at = now() WHERE id = $1",
            vendor.id, risk_after,
        )

    recipients = await _recipients_for(conn, severity)
    for email in recipients:
        send_alert_notification(
            email, vendor_name=vendor.legal_name, severity=severity, alert_type=alert_type, title=title,
            detail_lines=detail_lines, risk_score_before=risk_before, risk_score_after=risk_after,
        )

    await conn.execute(
        """
        INSERT INTO audit_logs (action, entity_type, entity_id, after_state)
        VALUES ('alert.raised', 'monitoring_alert', $1, $2)
        """,
        alert["id"], {"alert_type": alert_type, "severity": severity, "risk_delta": risk_delta},
    )
    return alert


async def acknowledge_alert(conn: asyncpg.Connection, alert_id: str, user_id: str | None) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        UPDATE monitoring_alerts SET status = 'acknowledged', acknowledged_by_id = $2, acknowledged_at = now()
        WHERE id = $1 AND status IN ('new', 'escalated') RETURNING *
        """,
        alert_id, user_id,
    )


async def resolve_alert(conn: asyncpg.Connection, alert_id: str) -> asyncpg.Record:
    return await conn.fetchrow(
        "UPDATE monitoring_alerts SET status = 'resolved', resolved_at = now() WHERE id = $1 RETURNING *",
        alert_id,
    )


async def suppress_from_alert(conn: asyncpg.Connection, alert_id: str, reason: str, created_by_id: str | None) -> asyncpg.Record:
    settings = get_settings()
    alert = await conn.fetchrow("SELECT vendor_id, alert_type FROM monitoring_alerts WHERE id = $1", alert_id)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.alert_suppression_default_days)
    suppression = await conn.fetchrow(
        """
        INSERT INTO alert_suppressions (vendor_id, alert_type, reason, created_by_id, expires_at)
        VALUES ($1, $2, $3, $4, $5) RETURNING *
        """,
        alert["vendor_id"], alert["alert_type"], reason, created_by_id, expires_at,
    )
    await conn.execute("UPDATE monitoring_alerts SET status = 'suppressed' WHERE id = $1", alert_id)
    return suppression


async def run_escalation_check(pool: asyncpg.Pool) -> int:
    """Escalates unacknowledged critical/high alerts past their SLA (Phase
    2 spec §3/§4: "If no ack within 1 hour, escalate to CISO"). Intended to
    run on a short interval — see airflow_dags/escalation_check.py."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    escalated = 0
    async with pool.acquire() as conn:
        for severity, minutes in (
            ("critical", settings.escalation_sla_minutes_critical),
            ("high", settings.escalation_sla_minutes_high),
        ):
            cutoff = now - timedelta(minutes=minutes)
            rows = await conn.fetch(
                """
                UPDATE monitoring_alerts SET status = 'escalated', escalated_at = now()
                WHERE status = 'new' AND severity = $1 AND detected_at < $2
                RETURNING id, vendor_id, title
                """,
                severity, cutoff,
            )
            for row in rows:
                vendor = await conn.fetchrow("SELECT legal_name, risk_score FROM vendors WHERE id = $1", row["vendor_id"])
                ciso_emails = await conn.fetch("SELECT email FROM users WHERE role = 'ciso' AND is_active")
                for r in ciso_emails:
                    send_alert_notification(
                        r["email"], vendor_name=vendor["legal_name"], severity="critical", alert_type="escalation",
                        title=f"ESCALATED (no ack within SLA): {row['title']}",
                        detail_lines=[f"Original severity: {severity}", f"SLA: {minutes} minutes"],
                        risk_score_before=None, risk_score_after=None,
                    )
                escalated += 1
    return escalated
