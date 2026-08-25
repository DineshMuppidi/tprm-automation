"""Incident impact assessment automation (Phase 2 spec §4): when a
critical breach alert fires, automatically determine blast radius — which
business units use this vendor, how many people, what data types — and
open an incident finding, exactly the "system checks... system auto-
creates incident ticket" sequence from the spec's own ransomware
walkthrough (docs/architecture/scenario-vendor-ransomware.md).

The `findings` table this writes into is the same one Phase 3 builds a
full remediation workflow around; Phase 2 only needs to create the row
with enough context for a human to act on, not the closure workflow.
"""

from datetime import datetime, timedelta, timezone

import asyncpg


async def assess_breach_impact(conn: asyncpg.Connection, vendor_id: str) -> dict:
    business_units = await conn.fetch(
        """
        SELECT bu.name, vbu.affected_user_count, vbu.data_types
        FROM vendor_business_units vbu JOIN business_units bu ON bu.id = vbu.business_unit_id
        WHERE vbu.vendor_id = $1
        """,
        vendor_id,
    )
    all_data_types: set[str] = set()
    total_users = 0
    for row in business_units:
        total_users += row["affected_user_count"] or 0
        all_data_types.update(row["data_types"] or [])

    vendor = await conn.fetchrow("SELECT data_access_level FROM vendors WHERE id = $1", vendor_id)

    regulations = []
    if "phi" in all_data_types or (vendor and vendor["data_access_level"] == "phi"):
        regulations.append("HIPAA")
    if "pii" in all_data_types or "payroll" in all_data_types:
        regulations.append("State data breach notification laws")

    contract = await conn.fetchrow(
        "SELECT extracted_terms FROM contracts WHERE vendor_id = $1 AND status = 'active' "
        "ORDER BY effective_date DESC LIMIT 1",
        vendor_id,
    )
    notification_sla = None
    if contract and contract["extracted_terms"]:
        notification_sla = contract["extracted_terms"].get("incident_notification_sla")

    return {
        "business_units_affected": [r["name"] for r in business_units],
        "affected_user_count": total_users,
        "data_types_involved": sorted(all_data_types),
        "applicable_regulations": regulations,
        # None here means "no contract on file with parsed terms" — expected
        # until Phase 4 implements contract ingestion/parsing.
        "contract_notification_sla": notification_sla,
    }


async def create_incident_finding(conn: asyncpg.Connection, vendor_id: str, alert: asyncpg.Record) -> asyncpg.Record:
    impact = await assess_breach_impact(conn, vendor_id)
    due_at = datetime.now(timezone.utc) + timedelta(days=1)

    finding = await conn.fetchrow(
        """
        INSERT INTO findings (vendor_id, source_alert_id, title, description, risk_rationale, severity, status, due_at)
        VALUES ($1, $2, $3, $4, $5, 'critical', 'new', $6)
        RETURNING *
        """,
        vendor_id, alert["id"],
        f"Vendor Breach — Incident Response: {alert['title']}",
        (
            f"Breach alert triggered for this vendor. Impact assessment: "
            f"{impact['affected_user_count']} affected users across "
            f"{', '.join(impact['business_units_affected']) or 'no mapped business units'}; "
            f"data types involved: {', '.join(impact['data_types_involved']) or 'unspecified'}."
        ),
        (
            f"Applicable regulations: {', '.join(impact['applicable_regulations']) or 'none identified'}. "
            f"Contract notification SLA: {impact['contract_notification_sla'] or 'not on file'}."
        ),
        due_at,
    )
    await conn.execute(
        "INSERT INTO audit_logs (action, entity_type, entity_id, after_state) VALUES ('finding.auto_created', 'finding', $1, $2)",
        finding["id"], {"source_alert_id": str(alert["id"]), "impact": impact},
    )
    return finding
