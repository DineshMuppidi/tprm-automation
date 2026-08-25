from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.db import get_db
from app.schemas.finding import (
    AdminNoteIn, CommentIn, ExceptionOut, ExceptionRequestIn, FindingDetail, FindingEvidenceOut, FindingSummary, PlanIn,
)
from app.security import AccessContext, VendorSession, get_access_context, require_admin_key, require_vendor_session
from app.services.email_service import send_finding_update_email
from app.services.remediation import escalation_engine, ticket_engine
from app.services.remediation.ticket_engine import InvalidTransition
from app.services.storage import infer_document_type, save_evidence_file

router = APIRouter(tags=["findings"])

FINDING_JOIN_SQL = """
    SELECT f.*, v.legal_name AS vendor_name, c.control_ref, c.title AS control_title
    FROM findings f
    JOIN vendors v ON v.id = f.vendor_id
    LEFT JOIN controls c ON c.id = f.control_id
"""


async def _load_finding(conn: asyncpg.Connection, finding_id: UUID) -> asyncpg.Record:
    row = await conn.fetchrow(FINDING_JOIN_SQL + " WHERE f.id = $1", finding_id)
    if not row:
        raise HTTPException(status_code=404, detail="Finding not found")
    return row


async def _finding_detail(conn: asyncpg.Connection, row: asyncpg.Record) -> dict:
    comments = await conn.fetch(
        "SELECT id, author_type, body, created_at FROM finding_comments WHERE finding_id = $1 ORDER BY created_at", row["id"],
    )
    evidence = await conn.fetch(
        "SELECT id, document_type, original_filename, llm_validation_result, uploaded_at FROM remediation_evidence "
        "WHERE finding_id = $1 ORDER BY uploaded_at", row["id"],
    )
    return {**dict(row), "comments": [dict(c) for c in comments], "evidence": [dict(e) for e in evidence]}


@router.get("/findings/mine", response_model=list[FindingSummary])
async def list_my_findings(session: VendorSession = Depends(require_vendor_session), pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(FINDING_JOIN_SQL + " WHERE f.vendor_id = $1 ORDER BY f.due_at", session.vendor_id)
    return [dict(r) for r in rows]


@router.get("/findings/{finding_id}", response_model=FindingDetail)
async def get_finding(finding_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        return await _finding_detail(conn, row)


@router.post("/findings/{finding_id}/acknowledge", response_model=FindingDetail)
async def acknowledge(finding_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        try:
            await ticket_engine.acknowledge_finding(conn, str(finding_id))
        except InvalidTransition as e:
            raise HTTPException(status_code=400, detail=str(e))
        row = await _load_finding(conn, finding_id)
        return await _finding_detail(conn, row)


@router.put("/findings/{finding_id}/plan", response_model=FindingDetail)
async def submit_plan(
    finding_id: UUID, body: PlanIn, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        try:
            await ticket_engine.submit_remediation_plan(conn, str(finding_id), body.plan_text)
        except InvalidTransition as e:
            raise HTTPException(status_code=400, detail=str(e))
        row = await _load_finding(conn, finding_id)
        return await _finding_detail(conn, row)


@router.post("/findings/{finding_id}/evidence", response_model=FindingEvidenceOut)
async def upload_finding_evidence(
    finding_id: UUID, file: UploadFile, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        if row["status"] not in ("in_progress", "rejected"):
            raise HTTPException(status_code=400, detail=f"Cannot upload evidence while status is '{row['status']}'")

        content = await file.read()
        doc_type = infer_document_type(file.filename or "evidence", None)
        storage_uri = save_evidence_file(f"finding-{finding_id}", file.filename or "evidence", content)
        evidence = await conn.fetchrow(
            """
            INSERT INTO remediation_evidence (finding_id, document_type, storage_uri, original_filename)
            VALUES ($1, $2, $3, $4) RETURNING id, document_type, original_filename, llm_validation_result, uploaded_at
            """,
            finding_id, doc_type, storage_uri, file.filename or "evidence",
        )
    return dict(evidence)


@router.post("/findings/{finding_id}/submit", response_model=FindingDetail)
async def submit_finding(finding_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        try:
            await ticket_engine.submit_for_validation(conn, str(finding_id))
        except InvalidTransition as e:
            raise HTTPException(status_code=400, detail=str(e))
        row = await _load_finding(conn, finding_id)
        detail = await _finding_detail(conn, row)

    contact = await _primary_contact_email(pool, row["vendor_id"])
    if contact:
        if row["status"] == "closed":
            send_finding_update_email(contact, row["vendor_name"], row["title"], "Your evidence was reviewed and this finding is now closed. Thank you.")
        elif row["status"] == "rejected":
            last_comment = detail["comments"][-1]["body"] if detail["comments"] else "Please review and resubmit."
            send_finding_update_email(contact, row["vendor_name"], row["title"], last_comment)
    return detail


async def _primary_contact_email(pool: asyncpg.Pool, vendor_id: UUID) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT email FROM vendor_contacts WHERE vendor_id = $1 AND is_primary LIMIT 1", vendor_id)
    return row["email"] if row else None


@router.post("/findings/{finding_id}/comments", response_model=FindingDetail)
async def add_comment(
    finding_id: UUID, body: CommentIn, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        author_type = "internal" if ctx.is_admin else "vendor"
        await ticket_engine.add_comment(
            conn, str(finding_id), author_type, body.body,
            author_vendor_contact_id=ctx.vendor_contact_id if not ctx.is_admin else None,
        )
        row = await _load_finding(conn, finding_id)
        return await _finding_detail(conn, row)


@router.post("/findings/{finding_id}/request-exception", response_model=ExceptionOut)
async def request_exception(
    finding_id: UUID, body: ExceptionRequestIn, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_finding(conn, finding_id)
        ctx.check_vendor(row["vendor_id"])
        exception = await ticket_engine.request_exception(conn, str(finding_id), body.justification, body.compensating_controls)
    return dict(exception)


# --- Admin -------------------------------------------------------------

admin_router = APIRouter(prefix="/admin", tags=["findings-admin"], dependencies=[Depends(require_admin_key)])


@admin_router.get("/findings", response_model=list[FindingSummary])
async def list_all_findings(
    vendor_id: UUID | None = None, status: str | None = None, severity: str | None = None,
    pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            FINDING_JOIN_SQL + """
            WHERE ($1::uuid IS NULL OR f.vendor_id = $1)
              AND ($2::finding_status IS NULL OR f.status = $2)
              AND ($3::finding_severity IS NULL OR f.severity = $3)
            ORDER BY f.due_at
            """,
            vendor_id, status, severity,
        )
    return [dict(r) for r in rows]


@admin_router.post("/findings/{finding_id}/close", response_model=FindingDetail)
async def admin_close(finding_id: UUID, body: AdminNoteIn, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        try:
            await ticket_engine.admin_close_finding(conn, str(finding_id), body.note)
        except InvalidTransition as e:
            raise HTTPException(status_code=400, detail=str(e))
        row = await _load_finding(conn, finding_id)
        return await _finding_detail(conn, row)


@admin_router.post("/findings/{finding_id}/reject", response_model=FindingDetail)
async def admin_reject(finding_id: UUID, body: AdminNoteIn, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        try:
            await ticket_engine.admin_reject_finding(conn, str(finding_id), body.note or "Rejected by reviewer.")
        except InvalidTransition as e:
            raise HTTPException(status_code=400, detail=str(e))
        row = await _load_finding(conn, finding_id)
        return await _finding_detail(conn, row)


@admin_router.post("/findings/run-escalation-check")
async def run_escalation_check(pool: asyncpg.Pool = Depends(get_db)):
    return await escalation_engine.run_finding_escalation_check(pool)


@admin_router.get("/exceptions", response_model=list[ExceptionOut])
async def list_exceptions(pending_only: bool = True, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM exceptions WHERE ($1::boolean IS FALSE OR approved_at IS NULL) ORDER BY created_at DESC",
            pending_only,
        )
    return [dict(r) for r in rows]


@admin_router.post("/exceptions/{exception_id}/approve", response_model=ExceptionOut)
async def approve_exception(exception_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        try:
            exception = await ticket_engine.approve_exception(conn, str(exception_id), None)
        except InvalidTransition as e:
            raise HTTPException(status_code=400, detail=str(e))
    return dict(exception)
