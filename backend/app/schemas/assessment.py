from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class QuestionOut(BaseModel):
    id: UUID
    question_code: str
    section: str
    prompt: str
    help_text: str | None
    input_type: str
    options: dict[str, Any] | None
    evidence_required: bool
    display_order: int


class ResponseIn(BaseModel):
    raw_answer: str


class AnalysisOut(BaseModel):
    classification: Literal["strong", "adequate", "weak", "missing", "contradictory"] | None
    confidence_score: float | None
    extracted_claims: list[str] | None
    evidence_status: str
    follow_up_needed: bool
    follow_up_question: str | None
    analyzed_at: datetime | None


class ResponseOut(BaseModel):
    id: UUID | None   # assessment_responses.id — None until the vendor's first save; used to correlate evidence
    question_id: UUID
    raw_answer: str | None
    analysis: AnalysisOut


class EvidenceOut(BaseModel):
    id: UUID
    response_id: UUID | None
    document_type: str
    original_filename: str
    uploaded_at: datetime


class AssessmentSummary(BaseModel):
    id: UUID
    vendor_id: UUID
    vendor_name: str
    template_name: str
    tier: str
    status: str
    assigned_at: datetime | None
    due_at: datetime | None
    completed_at: datetime | None
    overall_score: float | None
    progress_pct: float


class AssessmentDetail(AssessmentSummary):
    questions: list[QuestionOut]
    responses: dict[str, ResponseOut]   # keyed by question_id (str)
    evidence: list[EvidenceOut]


class ControlScore(BaseModel):
    control_id: UUID
    control_ref: str
    control_title: str
    framework_code: str
    score: float
    question_count: int


class RiskBreakdown(BaseModel):
    assessment_id: UUID
    overall_score: float
    vendor_risk_score: float
    classification_counts: dict[str, int]
    control_scores: list[ControlScore]
    framework_scores: dict[str, float]


class AssignAssessmentIn(BaseModel):
    vendor_id: UUID
    template_id: UUID
    due_in_days: int | None = None


class AssignAssessmentOut(AssessmentSummary):
    # Only populated when EMAIL_PROVIDER=console (i.e. no real mail is being
    # sent) — a local-dev convenience so the admin UI can hand the vendor a
    # working link without tailing backend logs. Never populated once a real
    # email provider is configured.
    dev_login_url: str | None = None
