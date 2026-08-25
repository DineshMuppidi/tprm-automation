from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ContractOut(BaseModel):
    id: UUID
    vendor_id: UUID
    contract_name: str
    status: str
    effective_date: date
    expiration_date: date | None
    auto_renews: bool
    renewal_notice_days: int | None
    extracted_terms: dict[str, Any] | None
    parsed_at: datetime | None
    created_at: datetime


class ObligationOut(BaseModel):
    id: UUID
    contract_id: UUID
    description: str
    obligation_type: str
    check_frequency: str | None
    last_checked_at: datetime | None
    last_check_status: str | None
    next_check_due: datetime | None


class ComplianceCheckResult(BaseModel):
    obligation_id: UUID
    description: str
    status: str
    reason: str
