"""Compliance reporting & KPIs (Phase 3 spec §5).

One documented gap: "risk improvement" per the spec means *before/after*
trend — this reports the current risk-score distribution only, because
nothing in the platform snapshots a vendor's risk score over time yet. A
proper trend needs a `risk_score_history` table (or equivalent time-series
capture) that doesn't exist — noted here rather than faked with a made-up
delta.
"""

import asyncpg


async def remediation_velocity(conn: asyncpg.Connection) -> dict:
    by_status = await conn.fetch("SELECT status, count(*) AS n FROM findings GROUP BY status")
    mttr = await conn.fetchrow(
        "SELECT avg(EXTRACT(EPOCH FROM (closed_at - created_at)) / 86400) AS mttr_days "
        "FROM findings WHERE closed_at IS NOT NULL",
    )
    mttr_by_severity = await conn.fetch(
        "SELECT severity, avg(EXTRACT(EPOCH FROM (closed_at - created_at)) / 86400) AS mttr_days "
        "FROM findings WHERE closed_at IS NOT NULL GROUP BY severity",
    )
    closed_last_30d = await conn.fetchrow(
        "SELECT count(*) AS n FROM findings WHERE closed_at > now() - interval '30 days'",
    )
    return {
        "by_status": {r["status"]: r["n"] for r in by_status},
        "mttr_days": float(mttr["mttr_days"]) if mttr["mttr_days"] is not None else None,
        "mttr_by_severity": {r["severity"]: round(float(r["mttr_days"]), 1) for r in mttr_by_severity if r["mttr_days"] is not None},
        "closed_last_30_days": closed_last_30d["n"],
    }


async def vendor_performance(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT v.id, v.legal_name,
               count(f.id) AS total_findings,
               count(f.id) FILTER (WHERE f.status = 'closed') AS closed,
               count(f.id) FILTER (WHERE f.status = 'overdue') AS overdue
        FROM vendors v LEFT JOIN findings f ON f.vendor_id = v.id
        WHERE v.status != 'terminated'
        GROUP BY v.id
        HAVING count(f.id) > 0
        ORDER BY overdue DESC, total_findings DESC
        """,
    )
    result = []
    for r in rows:
        closure_rate = (r["closed"] / r["total_findings"] * 100) if r["total_findings"] else 0.0
        result.append({
            "vendor_id": r["id"], "legal_name": r["legal_name"], "total_findings": r["total_findings"],
            "closed": r["closed"], "overdue": r["overdue"], "closure_rate_pct": round(closure_rate, 1),
        })
    return result


async def quality_metrics(conn: asyncpg.Connection) -> dict:
    closed = await conn.fetchrow("SELECT count(*) AS n FROM findings WHERE status = 'closed'")
    reworked = await conn.fetchrow("SELECT count(*) AS n FROM findings WHERE status = 'closed' AND rejection_count > 0")
    total = await conn.fetchrow("SELECT count(*) AS n FROM findings")
    exceptions = await conn.fetchrow("SELECT count(*) AS n FROM findings WHERE status = 'exception_granted'")
    closed_n = closed["n"] or 0
    total_n = total["n"] or 0
    return {
        "rework_rate_pct": round(reworked["n"] / closed_n * 100, 1) if closed_n else 0.0,
        "exception_rate_pct": round(exceptions["n"] / total_n * 100, 1) if total_n else 0.0,
    }


async def risk_and_regulatory_readiness(conn: asyncpg.Connection) -> dict:
    risk = await conn.fetchrow(
        """
        SELECT avg(risk_score) AS avg_risk,
               count(*) FILTER (WHERE risk_score < 40) AS low,
               count(*) FILTER (WHERE risk_score BETWEEN 40 AND 70) AS medium,
               count(*) FILTER (WHERE risk_score > 70) AS high
        FROM vendors WHERE risk_score IS NOT NULL
        """,
    )
    closed_with_evidence = await conn.fetchrow(
        "SELECT count(DISTINCT f.id) AS n FROM findings f JOIN remediation_evidence re ON re.finding_id = f.id WHERE f.status = 'closed'",
    )
    closed_total = await conn.fetchrow("SELECT count(*) AS n FROM findings WHERE status = 'closed'")
    closed_total_n = closed_total["n"] or 0
    return {
        "avg_vendor_risk_score": round(float(risk["avg_risk"]), 1) if risk["avg_risk"] is not None else None,
        "vendor_risk_band_counts": {"low": risk["low"], "medium": risk["medium"], "high": risk["high"]},
        "evidence_coverage_pct": round(closed_with_evidence["n"] / closed_total_n * 100, 1) if closed_total_n else 0.0,
    }


async def build_kpi_report(pool: asyncpg.Pool) -> dict:
    async with pool.acquire() as conn:
        return {
            "remediation_velocity": await remediation_velocity(conn),
            "vendor_performance": await vendor_performance(conn),
            "quality": await quality_metrics(conn),
            "risk_and_regulatory": await risk_and_regulatory_readiness(conn),
        }
