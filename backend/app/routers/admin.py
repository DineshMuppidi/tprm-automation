from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.db import get_db
from app.schemas.assessment import AssignAssessmentIn, AssignAssessmentOut, AssessmentSummary
from app.schemas.vendor import TemplateOut, VendorCreateIn, VendorOut
from app.security import create_magic_link_token, require_admin_key
from app.services import assessment_service as svc
from app.services.email_service import send_assignment_email

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


@router.get("/vendors", response_model=list[VendorOut])
async def list_vendors(pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, legal_name, tier, status, risk_score FROM vendors ORDER BY legal_name",
        )
    return [
        {"id": r["id"], "legal_name": r["legal_name"], "tier": r["tier"], "status": r["status"],
         "risk_score": float(r["risk_score"]) if r["risk_score"] is not None else None}
        for r in rows
    ]


@router.post("/vendors", response_model=VendorOut, status_code=201)
async def create_vendor(body: VendorCreateIn, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow(
            """
            INSERT INTO vendors (legal_name, industry, tier, status, data_access_level)
            VALUES ($1, $2, $3, 'onboarding', $4)
            RETURNING id, legal_name, tier, status, risk_score
            """,
            body.legal_name, body.industry, body.tier, body.data_access_level,
        )
        await conn.execute(
            """
            INSERT INTO vendor_contacts (vendor_id, full_name, email, role, is_primary)
            VALUES ($1, $2, $3, $4, $5)
            """,
            vendor["id"], body.primary_contact.full_name, body.primary_contact.email,
            body.primary_contact.role, body.primary_contact.is_primary,
        )
    return {"id": vendor["id"], "legal_name": vendor["legal_name"], "tier": vendor["tier"],
            "status": vendor["status"], "risk_score": None}


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.tier, count(q.id) AS question_count
            FROM questionnaire_templates t LEFT JOIN questions q ON q.template_id = t.id
            WHERE t.is_active
            GROUP BY t.id ORDER BY t.tier
            """,
        )
    return [{"id": r["id"], "name": r["name"], "tier": r["tier"], "question_count": r["question_count"]} for r in rows]


@router.get("/assessments", response_model=list[AssessmentSummary])
async def list_all_assessments(vendor_id: UUID | None = None, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.*, v.legal_name AS vendor_name, t.name AS template_name, v.tier
            FROM assessments a
            JOIN vendors v ON v.id = a.vendor_id
            JOIN questionnaire_templates t ON t.id = a.template_id
            WHERE $1::uuid IS NULL OR a.vendor_id = $1
            ORDER BY a.created_at DESC
            """,
            vendor_id,
        )
        out = []
        for row in rows:
            questions = await svc.fetch_template_questions(conn, row["template_id"])
            responses = await svc.fetch_responses_by_question(conn, row["id"])
            out.append({
                "id": row["id"], "vendor_id": row["vendor_id"], "vendor_name": row["vendor_name"],
                "template_name": row["template_name"], "tier": row["tier"], "status": row["status"],
                "assigned_at": row["assigned_at"], "due_at": row["due_at"], "completed_at": row["completed_at"],
                "overall_score": float(row["overall_score"]) if row["overall_score"] is not None else None,
                "progress_pct": svc.compute_progress_pct(questions, responses),
            })
        return out


@router.post("/assessments", response_model=AssignAssessmentOut, status_code=201)
async def assign_assessment(body: AssignAssessmentIn, pool: asyncpg.Pool = Depends(get_db)):
    settings = get_settings()
    async with pool.acquire() as conn:
        vendor = await conn.fetchrow("SELECT legal_name, tier FROM vendors WHERE id = $1", body.vendor_id)
        template = await conn.fetchrow("SELECT name FROM questionnaire_templates WHERE id = $1", body.template_id)
        contact = await conn.fetchrow(
            "SELECT id, email FROM vendor_contacts WHERE vendor_id = $1 AND is_primary LIMIT 1", body.vendor_id,
        )

        due_at = datetime.now(timezone.utc) + timedelta(days=body.due_in_days or 14)
        row = await conn.fetchrow(
            """
            INSERT INTO assessments (vendor_id, template_id, status, assigned_at, due_at)
            VALUES ($1, $2, 'assigned', now(), $3)
            RETURNING *
            """,
            body.vendor_id, body.template_id, due_at,
        )

        login_url = None
        if contact:
            token = create_magic_link_token(contact["id"], contact["email"])
            login_url = f"{settings.app_base_url}/verify?token={token}"
            send_assignment_email(contact["email"], vendor["legal_name"], login_url, due_at.strftime("%Y-%m-%d"))

    return {
        "id": row["id"], "vendor_id": row["vendor_id"], "vendor_name": vendor["legal_name"],
        "template_name": template["name"], "tier": vendor["tier"],
        "status": row["status"], "assigned_at": row["assigned_at"], "due_at": row["due_at"],
        "completed_at": row["completed_at"], "overall_score": None,
        "progress_pct": 0.0,
        "dev_login_url": login_url if settings.email_provider == "console" else None,
    }
