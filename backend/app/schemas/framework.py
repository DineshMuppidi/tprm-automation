from typing import Any

from pydantic import BaseModel


class FrameworkCoverageOut(BaseModel):
    covered: int
    total: int
    pct: float


class GapAnalysisOut(BaseModel):
    framework_code: str
    covered: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    coverage_pct: float


class RelatedControlOut(BaseModel):
    control_ref: str
    title: str
    framework_code: str
    confidence: float
    rationale: str | None


class ControlScorecardEntry(BaseModel):
    control_ref: str
    title: str
    framework_code: str
    vendors_covered: int
    vendors_total: int
    coverage_pct: float
    critical_tier_gaps: int
