from uuid import UUID

from pydantic import BaseModel


class RemediationVelocity(BaseModel):
    by_status: dict[str, int]
    mttr_days: float | None
    mttr_by_severity: dict[str, float]
    closed_last_30_days: int


class VendorPerformanceEntry(BaseModel):
    vendor_id: UUID
    legal_name: str
    total_findings: int
    closed: int
    overdue: int
    closure_rate_pct: float


class QualityMetrics(BaseModel):
    rework_rate_pct: float
    exception_rate_pct: float


class RiskAndRegulatory(BaseModel):
    avg_vendor_risk_score: float | None
    vendor_risk_band_counts: dict[str, int]
    evidence_coverage_pct: float


class KPIReport(BaseModel):
    remediation_velocity: RemediationVelocity
    vendor_performance: list[VendorPerformanceEntry]
    quality: QualityMetrics
    risk_and_regulatory: RiskAndRegulatory
