"""Board-level reporting (Phase 4 spec §6): a consolidated view spanning
Phases 2-4 — vendor risk distribution, remediation velocity (Phase 3),
top control gaps (Phase 4), and upcoming contract renewals (Phase 4).
This is what a quarterly board meeting slide deck pulls from — the spec's
own scenario is a healthcare org's board packet; this is that packet's
data source, not a mocked-up example.
"""

import asyncpg

from app.services.frameworks.coverage import control_coverage_scorecard
from app.services.remediation.reporting import build_kpi_report


async def build_board_summary(pool: asyncpg.Pool) -> dict:
    kpi_report = await build_kpi_report(pool)
    control_gaps = await control_coverage_scorecard(pool)

    async with pool.acquire() as conn:
        vendor_counts = await conn.fetchrow(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE risk_score > 70) AS critical,
                   count(*) FILTER (WHERE risk_score BETWEEN 40 AND 70) AS high,
                   count(*) FILTER (WHERE risk_score < 40) AS low
            FROM vendors WHERE status != 'terminated'
            """,
        )
        renewals_due = await conn.fetch(
            """
            SELECT c.id, c.contract_name, c.expiration_date, v.legal_name AS vendor_name
            FROM contracts c JOIN vendors v ON v.id = c.vendor_id
            WHERE c.status = 'active' AND c.expiration_date IS NOT NULL
              AND c.expiration_date <= (CURRENT_DATE + interval '90 days')
            ORDER BY c.expiration_date
            """,
        )
        high_risk_vendors = await conn.fetch(
            """
            SELECT id, legal_name, risk_score FROM vendors
            WHERE risk_score > 70 AND status != 'terminated'
            ORDER BY risk_score DESC LIMIT 10
            """,
        )

    return {
        "vendor_risk_distribution": dict(vendor_counts),
        "remediation": kpi_report,
        "top_control_gaps": control_gaps[:10],
        "contract_renewals_due": [
            {"id": r["id"], "contract_name": r["contract_name"], "expiration_date": r["expiration_date"], "vendor_name": r["vendor_name"]}
            for r in renewals_due
        ],
        "high_risk_vendors": [
            {"id": v["id"], "legal_name": v["legal_name"], "risk_score": float(v["risk_score"])} for v in high_risk_vendors
        ],
    }
