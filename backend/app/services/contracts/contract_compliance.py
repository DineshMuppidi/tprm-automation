"""Turns extracted contract terms into trackable obligations (Phase 4 spec
§1c) and checks the vendor's current state against them — reusing Phase 2's
alert engine (`contract_violation` is one of the `alert_type` enum values
seeded there since Phase 0, unused until now) rather than building a
parallel notification path.
"""

import asyncpg

from app.services.contracts.contract_parser import ContractTerms
from app.services.monitoring.alert_engine import VendorRef, raise_alert


def _infer_obligation_type(security_requirement: str) -> str:
    text = security_requirement.lower()
    if "soc 2" in text or "iso 27001" in text or "iso/iec 27001" in text or "pci" in text:
        return "certification"
    if "audit" in text or "penetration test" in text:
        return "audit"
    return "other"


async def generate_obligations(conn: asyncpg.Connection, contract_id: str, terms: ContractTerms) -> list[asyncpg.Record]:
    created = []
    for requirement in terms.security_requirements:
        row = await conn.fetchrow(
            """
            INSERT INTO contract_obligations (contract_id, description, obligation_type, check_frequency, next_check_due)
            VALUES ($1, $2, $3, 'annually', now() + interval '90 days')
            RETURNING *
            """,
            contract_id, requirement, _infer_obligation_type(requirement),
        )
        created.append(row)

    if terms.incident_notification_sla_hours is not None:
        row = await conn.fetchrow(
            """
            INSERT INTO contract_obligations (contract_id, description, obligation_type, check_frequency)
            VALUES ($1, $2, 'notification_sla', 'once')
            RETURNING *
            """,
            contract_id, f"Vendor must notify us of a security incident within {terms.incident_notification_sla_hours} hours.",
        )
        created.append(row)

    if terms.sla_uptime_pct is not None:
        row = await conn.fetchrow(
            """
            INSERT INTO contract_obligations (contract_id, description, obligation_type, check_frequency, next_check_due)
            VALUES ($1, $2, 'sla_uptime', 'quarterly', now() + interval '90 days')
            RETURNING *
            """,
            contract_id, f"Vendor must maintain {terms.sla_uptime_pct}% uptime.",
        )
        created.append(row)

    return created


async def check_contract_compliance(conn: asyncpg.Connection, vendor_id: str) -> list[dict]:
    """Checks 'certification' obligations on the vendor's active contract
    against whether they currently have an *expired* (not merely expiring)
    certification alert on record. A vendor with no active contract, or no
    certification obligations, has nothing to check — returns [].

    This is a narrow, defensible check (one clear signal: a hard cert
    expiry), not a general contract-compliance engine — documented as a
    starting point, not a promise of exhaustive coverage.
    """
    contract = await conn.fetchrow(
        "SELECT * FROM contracts WHERE vendor_id = $1 AND status = 'active' ORDER BY effective_date DESC LIMIT 1",
        vendor_id,
    )
    if not contract:
        return []

    obligations = await conn.fetch(
        "SELECT * FROM contract_obligations WHERE contract_id = $1 AND obligation_type = 'certification'",
        contract["id"],
    )
    if not obligations:
        return []

    expired_alert = await conn.fetchrow(
        """
        SELECT id, title FROM monitoring_alerts
        WHERE vendor_id = $1 AND alert_type = 'cert_expiry' AND payload->>'status' = 'expired' AND status != 'resolved'
        ORDER BY detected_at DESC LIMIT 1
        """,
        vendor_id,
    )
    vendor = await conn.fetchrow("SELECT legal_name, risk_score FROM vendors WHERE id = $1", vendor_id)

    results = []
    for ob in obligations:
        if expired_alert:
            status, reason = "non_compliant", (
                f"Contract requires: {ob['description']} — but the vendor's certification has "
                f"expired (see monitoring alert '{expired_alert['title']}')."
            )
            await raise_alert(
                conn,
                VendorRef(str(vendor_id), vendor["legal_name"], float(vendor["risk_score"]) if vendor["risk_score"] is not None else None),
                alert_type="contract_violation", severity="high",
                title=f"Contract obligation violated: {ob['description'][:80]}",
                payload={"obligation_id": str(ob["id"]), "reason": reason},
                detail_lines=[reason],
            )
        else:
            status, reason = "compliant", "No expired-certification alert on record."

        await conn.execute(
            "UPDATE contract_obligations SET last_checked_at = now(), last_check_status = $2 WHERE id = $1",
            ob["id"], status,
        )
        results.append({"obligation_id": str(ob["id"]), "description": ob["description"], "status": status, "reason": reason})

    return results
