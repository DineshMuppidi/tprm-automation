"""Automated finding generation (Phase 3 spec §1) — two triggers:

  * Trigger 1 (`generate_findings_from_assessment`): a completed
    assessment's weak/missing/contradictory responses become findings.
  * Trigger 2 (`create_finding_from_alert`): a critical/high monitoring
    alert opens a finding. Breach alerts already get the richer
    impact-assessment treatment via monitoring/impact_assessor.py (Phase
    2) — this covers the other alert types (cert_expiry, cve,
    financial_distress) the spec calls out ("Cert expiring in 30 days →
    Finding: 'SOC 2 certification missing'").

Severity → due-date mapping matches the spec's own table exactly
(Critical: 30 days, High: 60, Medium: 90, Low: 120).
"""

from datetime import datetime, timedelta, timezone

import asyncpg

SEVERITY_DUE_DAYS = {"critical": 30, "high": 60, "medium": 90, "low": 120}

_ALERT_TITLE_PREFIX = {
    "cert_expiry": "Certification lapse risk",
    "cve": "Unpatched vulnerability",
    "financial_distress": "Vendor financial distress",
    "news_reputation": "Reputational risk",
}


def _severity_for_response(classification: str, evidence_required: bool) -> str:
    """Documented mapping (the spec's own severity table isn't 1:1 with
    classification, so this is a reasoned proxy, not an arbitrary guess):
    a *missing* control that required evidence is the worst case (an
    unaddressed, high-stakes gap) → critical. An unresolved contradiction
    is inherently high — the vendor's own story doesn't add up. A weak
    answer on a high-stakes control is a process gap (medium); on a
    low-stakes one, it's a nice-to-have (low)."""
    if classification == "missing":
        return "critical" if evidence_required else "high"
    if classification == "contradictory":
        return "high"
    if classification == "weak":
        return "medium" if evidence_required else "low"
    return "low"


async def generate_findings_from_assessment(conn: asyncpg.Connection, assessment_id: str) -> list[asyncpg.Record]:
    assessment = await conn.fetchrow("SELECT vendor_id FROM assessments WHERE id = $1", assessment_id)
    vendor_id = assessment["vendor_id"]
    contact = await conn.fetchrow(
        "SELECT id FROM vendor_contacts WHERE vendor_id = $1 AND is_primary LIMIT 1", vendor_id,
    )

    rows = await conn.fetch(
        """
        SELECT r.classification, r.extracted_claims,
               q.prompt, q.help_text, q.control_id, q.evidence_required,
               c.title AS control_title, c.control_ref
        FROM assessment_responses r
        JOIN questions q ON q.id = r.question_id
        LEFT JOIN controls c ON c.id = q.control_id
        WHERE r.assessment_id = $1 AND r.classification IN ('weak', 'missing', 'contradictory')
        """,
        assessment_id,
    )

    created = []
    for row in rows:
        title = f"Gap identified: {row['prompt'][:100]}"
        existing = await conn.fetchrow(
            "SELECT id FROM findings WHERE source_assessment_id = $1 AND title = $2 AND status NOT IN ('closed', 'rejected')",
            assessment_id, title,
        )
        if existing:
            continue

        severity = _severity_for_response(row["classification"], row["evidence_required"])
        due_at = datetime.now(timezone.utc) + timedelta(days=SEVERITY_DUE_DAYS[severity])
        claims = "; ".join(row["extracted_claims"] or [])
        description = f"Assessment response classified as '{row['classification']}'." + (f" Key claims: {claims}." if claims else "")
        risk_rationale = (
            f"Maps to control {row['control_ref']} ({row['control_title']})."
            if row["control_ref"] else "Not mapped to a specific control catalog entry."
        )

        finding = await conn.fetchrow(
            """
            INSERT INTO findings (vendor_id, source_assessment_id, control_id, title, description,
                                   risk_rationale, required_evidence, severity, status,
                                   vendor_owner_contact_id, due_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'new', $9, $10)
            RETURNING *
            """,
            vendor_id, assessment_id, row["control_id"], title, description, risk_rationale,
            row["help_text"], severity, contact["id"] if contact else None, due_at,
        )
        created.append(finding)

    return created


async def create_finding_from_alert(conn: asyncpg.Connection, vendor_id: str, alert: asyncpg.Record) -> asyncpg.Record | None:
    if alert["severity"] not in ("critical", "high"):
        return None
    if await conn.fetchrow("SELECT id FROM findings WHERE source_alert_id = $1", alert["id"]):
        return None

    contact = await conn.fetchrow(
        "SELECT id FROM vendor_contacts WHERE vendor_id = $1 AND is_primary LIMIT 1", vendor_id,
    )
    severity = alert["severity"]
    due_at = datetime.now(timezone.utc) + timedelta(days=SEVERITY_DUE_DAYS[severity])
    prefix = _ALERT_TITLE_PREFIX.get(alert["alert_type"], "Monitoring finding")

    return await conn.fetchrow(
        """
        INSERT INTO findings (vendor_id, source_alert_id, title, description, severity, status,
                               vendor_owner_contact_id, due_at)
        VALUES ($1, $2, $3, $4, $5, 'new', $6, $7)
        RETURNING *
        """,
        vendor_id, alert["id"], f"{prefix}: {alert['title']}",
        f"Auto-generated from a {severity} {alert['alert_type'].replace('_', ' ')} monitoring alert.",
        severity, contact["id"] if contact else None, due_at,
    )
