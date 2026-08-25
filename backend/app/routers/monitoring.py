from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.schemas.monitoring import (
    AcknowledgeIn, AlertOut, MonitoringStats, MonitoringStatusOut, RunChecksOut, SuppressIn, VendorRiskEntry,
)
from app.security import require_admin_key
from app.services.monitoring import alert_engine, monitoring_service

router = APIRouter(prefix="/admin/monitoring", tags=["monitoring"], dependencies=[Depends(require_admin_key)])


def _alert_out(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"], "vendor_id": row["vendor_id"], "vendor_name": row["vendor_name"],
        "alert_type": row["alert_type"], "severity": row["severity"], "status": row["status"],
        "title": row["title"], "payload": row["payload"],
        "risk_score_delta": float(row["risk_score_delta"]) if row["risk_score_delta"] is not None else None,
        "detected_at": row["detected_at"], "acknowledged_at": row["acknowledged_at"],
        "escalated_at": row["escalated_at"], "resolved_at": row["resolved_at"],
    }


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    vendor_id: UUID | None = None, severity: str | None = None, status: str | None = None,
    alert_type: str | None = None, pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.*, v.legal_name AS vendor_name
            FROM monitoring_alerts a JOIN vendors v ON v.id = a.vendor_id
            WHERE ($1::uuid IS NULL OR a.vendor_id = $1)
              AND ($2::alert_severity IS NULL OR a.severity = $2)
              AND ($3::alert_status IS NULL OR a.status = $3)
              AND ($4::alert_type IS NULL OR a.alert_type = $4)
            ORDER BY a.detected_at DESC LIMIT 200
            """,
            vendor_id, severity, status, alert_type,
        )
    return [_alert_out(r) for r in rows]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge(alert_id: UUID, body: AcknowledgeIn, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        row = await alert_engine.acknowledge_alert(conn, str(alert_id), str(body.user_id) if body.user_id else None)
        if not row:
            raise HTTPException(status_code=400, detail="Alert not found or not in an acknowledgeable state")
        full = await conn.fetchrow(
            "SELECT a.*, v.legal_name AS vendor_name FROM monitoring_alerts a JOIN vendors v ON v.id = a.vendor_id WHERE a.id = $1",
            alert_id,
        )
    return _alert_out(full)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
async def resolve(alert_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        row = await alert_engine.resolve_alert(conn, str(alert_id))
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        full = await conn.fetchrow(
            "SELECT a.*, v.legal_name AS vendor_name FROM monitoring_alerts a JOIN vendors v ON v.id = a.vendor_id WHERE a.id = $1",
            alert_id,
        )
    return _alert_out(full)


@router.post("/alerts/{alert_id}/suppress", response_model=AlertOut)
async def suppress(alert_id: UUID, body: SuppressIn, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM monitoring_alerts WHERE id = $1", alert_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Alert not found")
        await alert_engine.suppress_from_alert(
            conn, str(alert_id), body.reason, str(body.user_id) if body.user_id else None,
        )
        full = await conn.fetchrow(
            "SELECT a.*, v.legal_name AS vendor_name FROM monitoring_alerts a JOIN vendors v ON v.id = a.vendor_id WHERE a.id = $1",
            alert_id,
        )
    return _alert_out(full)


@router.get("/status", response_model=MonitoringStatusOut)
async def monitoring_status(pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        sources = await conn.fetch(
            "SELECT code, name, is_enabled, last_checked_at, last_success_at, last_error FROM monitoring_sources ORDER BY code",
        )
        stats = await conn.fetchrow(
            """
            SELECT
                count(*) FILTER (WHERE detected_at > now() - interval '7 days') AS alerts_this_week,
                count(*) FILTER (WHERE escalated_at > now() - interval '7 days') AS escalated_this_week,
                count(*) FILTER (WHERE resolved_at > now() - interval '7 days') AS resolved_this_week,
                avg(EXTRACT(EPOCH FROM (acknowledged_at - detected_at)) / 60)
                    FILTER (WHERE acknowledged_at IS NOT NULL AND detected_at > now() - interval '30 days') AS avg_ack_minutes
            FROM monitoring_alerts
            """,
        )
    return {
        "sources": [dict(s) for s in sources],
        "stats": MonitoringStats(
            alerts_this_week=stats["alerts_this_week"], escalated_this_week=stats["escalated_this_week"],
            resolved_this_week=stats["resolved_this_week"],
            avg_ack_minutes=float(stats["avg_ack_minutes"]) if stats["avg_ack_minutes"] is not None else None,
        ),
    }


@router.get("/scoreboard", response_model=list[VendorRiskEntry])
async def scoreboard(pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT v.id, v.legal_name, v.tier, v.status, v.risk_score,
                   count(a.id) FILTER (WHERE a.status IN ('new','acknowledged','escalated')) AS open_alert_count
            FROM vendors v LEFT JOIN monitoring_alerts a ON a.vendor_id = v.id
            WHERE v.status != 'terminated'
            GROUP BY v.id
            ORDER BY v.risk_score DESC NULLS LAST
            """,
        )
    return [
        {"id": r["id"], "legal_name": r["legal_name"], "tier": r["tier"], "status": r["status"],
         "risk_score": float(r["risk_score"]) if r["risk_score"] is not None else None,
         "open_alert_count": r["open_alert_count"]}
        for r in rows
    ]


@router.post("/run-checks", response_model=RunChecksOut)
async def run_checks(pool: asyncpg.Pool = Depends(get_db)):
    return await monitoring_service.run_all_checks(pool)
