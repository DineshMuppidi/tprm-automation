"""Escalation & accountability workflows for findings (Phase 3 spec §4).
Intended to run daily — see airflow_dags/daily_finding_escalation_check.py.

Idempotency note: "notify again every time this check runs while the
finding is still unacknowledged" is deliberate (a live reminder should
keep nagging until acted on). The two escalation *thresholds* (overdue →
legal at 14 days, repeated weak submissions) fire exactly once by
recording a marker in `audit_logs` and checking for it first — reusing the
existing audit trail as the idempotency store rather than adding new
state, the same trick Phase 2's alert engine could have used but didn't
need to (its escalation is a status change, which is self-idempotent).
"""

from datetime import datetime, timedelta, timezone

import asyncpg

from app.services.email_service import send_finding_update_email, send_internal_finding_alert

ACK_GRACE_DAYS = 3
LEGAL_ESCALATION_OVERDUE_DAYS = 14
REJECTION_ESCALATION_THRESHOLD = 2


async def _internal_emails(conn: asyncpg.Connection, role: str) -> list[str]:
    rows = await conn.fetch("SELECT email FROM users WHERE role = $1 AND is_active", role)
    return [r["email"] for r in rows]


async def check_unacknowledged_findings(conn: asyncpg.Connection) -> int:
    """New findings not acknowledged within ACK_GRACE_DAYS -> remind vendor,
    notify category manager. Fires on every run while still unacknowledged
    (a live reminder), by design."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACK_GRACE_DAYS)
    rows = await conn.fetch(
        """
        SELECT f.id, f.title, v.legal_name, vc.email AS vendor_email
        FROM findings f
        JOIN vendors v ON v.id = f.vendor_id
        LEFT JOIN vendor_contacts vc ON vc.id = f.vendor_owner_contact_id
        WHERE f.status = 'new' AND f.created_at < $1
        """,
        cutoff,
    )
    for row in rows:
        if row["vendor_email"]:
            send_finding_update_email(
                row["vendor_email"], row["legal_name"], row["title"],
                "This finding has not yet been acknowledged. Please log in to the vendor portal to acknowledge it and begin remediation.",
            )
        for email in await _internal_emails(conn, "category_manager"):
            send_internal_finding_alert(
                email, row["legal_name"], row["title"],
                f"Vendor has not acknowledged this finding within {ACK_GRACE_DAYS} days of assignment.",
            )
    return len(rows)


async def check_overdue_findings(conn: asyncpg.Connection) -> int:
    """Findings past due_at (not yet closed/exempted) -> status=overdue,
    notify category manager + compliance officer. This UPDATE only matches
    a finding once (its status leaves the WHERE clause's set once set to
    'overdue'), so the initial notification fires exactly once."""
    rows = await conn.fetch(
        """
        UPDATE findings SET status = 'overdue', updated_at = now()
        WHERE due_at < now() AND status IN ('new', 'assigned', 'in_progress', 'submitted', 'validating')
        RETURNING id, title, vendor_id
        """,
    )
    for row in rows:
        vendor = await conn.fetchrow("SELECT legal_name FROM vendors WHERE id = $1", row["vendor_id"])
        for role in ("category_manager", "compliance_officer"):
            for email in await _internal_emails(conn, role):
                send_internal_finding_alert(
                    email, vendor["legal_name"], row["title"], "Finding has passed its remediation deadline.",
                )
    return len(rows)


async def check_severely_overdue_findings(conn: asyncpg.Connection) -> int:
    """Findings overdue by 14+ days -> escalate to Legal, once."""
    rows = await conn.fetch(
        """
        SELECT f.id, f.title, f.due_at, f.vendor_id, v.legal_name
        FROM findings f JOIN vendors v ON v.id = f.vendor_id
        WHERE f.status = 'overdue' AND f.due_at < now() - interval '14 days'
        """,
    )
    count = 0
    for row in rows:
        already = await conn.fetchrow(
            "SELECT 1 FROM audit_logs WHERE action = 'finding.legal_escalated' AND entity_id = $1", row["id"],
        )
        if already:
            continue
        days_overdue = (datetime.now(timezone.utc) - row["due_at"]).days
        for email in await _internal_emails(conn, "legal"):
            send_internal_finding_alert(
                email, row["legal_name"], row["title"],
                f"Finding is {days_overdue} days overdue (threshold: {LEGAL_ESCALATION_OVERDUE_DAYS}). Consider contract enforcement action.",
            )
        await conn.execute(
            "INSERT INTO audit_logs (action, entity_type, entity_id, after_state) VALUES ('finding.legal_escalated', 'finding', $1, $2)",
            row["id"], {"days_overdue": days_overdue},
        )
        count += 1
    return count


async def check_repeated_rejections(conn: asyncpg.Connection) -> int:
    """rejection_count >= REJECTION_ESCALATION_THRESHOLD -> escalate to
    Compliance once (vendor keeps submitting inadequate plans/evidence)."""
    rows = await conn.fetch(
        """
        SELECT id, title, vendor_id, rejection_count FROM findings
        WHERE rejection_count >= $1 AND status NOT IN ('closed', 'exception_granted')
        """,
        REJECTION_ESCALATION_THRESHOLD,
    )
    count = 0
    for row in rows:
        already = await conn.fetchrow(
            "SELECT 1 FROM audit_logs WHERE action = 'finding.repeated_rejection_escalated' AND entity_id = $1", row["id"],
        )
        if already:
            continue
        vendor = await conn.fetchrow("SELECT legal_name FROM vendors WHERE id = $1", row["vendor_id"])
        for email in await _internal_emails(conn, "compliance_officer"):
            send_internal_finding_alert(
                email, vendor["legal_name"], row["title"],
                f"Vendor has submitted {row['rejection_count']} inadequate plan/evidence attempt(s) on this finding — consider escalating to vendor leadership.",
            )
        await conn.execute(
            "INSERT INTO audit_logs (action, entity_type, entity_id, after_state) VALUES ('finding.repeated_rejection_escalated', 'finding', $1, $2)",
            row["id"], {"rejection_count": row["rejection_count"]},
        )
        count += 1
    return count


async def run_finding_escalation_check(pool: asyncpg.Pool) -> dict:
    async with pool.acquire() as conn:
        return {
            "unacknowledged_reminders": await check_unacknowledged_findings(conn),
            "newly_overdue": await check_overdue_findings(conn),
            "legal_escalations": await check_severely_overdue_findings(conn),
            "repeated_rejection_escalations": await check_repeated_rejections(conn),
        }
