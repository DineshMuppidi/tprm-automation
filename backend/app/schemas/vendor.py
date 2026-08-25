from uuid import UUID

from pydantic import BaseModel, EmailStr


class VendorContactIn(BaseModel):
    full_name: str
    email: EmailStr
    role: str | None = None
    is_primary: bool = True


class VendorCreateIn(BaseModel):
    legal_name: str
    industry: str | None = None
    tier: str
    data_access_level: str
    primary_contact: VendorContactIn


class VendorOut(BaseModel):
    id: UUID
    legal_name: str
    tier: str
    status: str
    risk_score: float | None


class TemplateOut(BaseModel):
    id: UUID
    name: str
    tier: str
    question_count: int
