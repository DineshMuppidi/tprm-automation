from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: UUID
    vendor_id: UUID
    vendor_name: str
    alert_type: str
    severity: str
    status: str
    title: str
    payload: dict[str, Any]
    risk_score_delta: float | None
    detected_at: datetime
    acknowledged_at: datetime | None
    escalated_at: datetime | None
    resolved_at: datetime | None


class AcknowledgeIn(BaseModel):
    user_id: UUID | None = None


class SuppressIn(BaseModel):
    reason: str
    user_id: UUID | None = None


class MonitoringSourceStatus(BaseModel):
    code: str
    name: str
    is_enabled: bool
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None


class MonitoringStats(BaseModel):
    alerts_this_week: int
    escalated_this_week: int
    resolved_this_week: int
    avg_ack_minutes: float | None


class MonitoringStatusOut(BaseModel):
    sources: list[MonitoringSourceStatus]
    stats: MonitoringStats


class RunChecksOut(BaseModel):
    cert_expiry: int
    breach_cve: int
    news: int
    financial: int
    escalations: int
    ran_at: str


class VendorRiskEntry(BaseModel):
    id: UUID
    legal_name: str
    tier: str
    status: str
    risk_score: float | None
    open_alert_count: int
