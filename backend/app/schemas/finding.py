from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class FindingCommentOut(BaseModel):
    id: UUID
    author_type: str
    body: str
    created_at: datetime


class FindingEvidenceOut(BaseModel):
    id: UUID
    document_type: str
    original_filename: str
    llm_validation_result: dict[str, Any] | None
    uploaded_at: datetime


class FindingSummary(BaseModel):
    id: UUID
    vendor_id: UUID
    vendor_name: str
    title: str
    severity: str
    status: str
    due_at: datetime
    created_at: datetime


class FindingDetail(FindingSummary):
    description: str
    risk_rationale: str | None
    required_evidence: str | None
    remediation_plan: str | None
    remediation_plan_review: dict[str, Any] | None
    rejection_count: int
    acknowledged_at: datetime | None
    submitted_at: datetime | None
    closed_at: datetime | None
    control_ref: str | None
    control_title: str | None
    comments: list[FindingCommentOut]
    evidence: list[FindingEvidenceOut]


class PlanIn(BaseModel):
    plan_text: str


class CommentIn(BaseModel):
    body: str


class AdminNoteIn(BaseModel):
    note: str | None = None


class ExceptionRequestIn(BaseModel):
    justification: str
    compensating_controls: str | None = None


class ExceptionOut(BaseModel):
    id: UUID
    finding_id: UUID
    justification: str
    compensating_controls: str | None
    approved_by_id: UUID | None
    approved_at: datetime | None
    expires_at: datetime
    created_at: datetime
