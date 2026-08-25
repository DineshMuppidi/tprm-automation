from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerify(BaseModel):
    token: str


class SessionToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    vendor_id: str
    vendor_contact_id: str
    vendor_name: str
