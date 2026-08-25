from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.db import get_db
from app.security import AccessContext, VendorSession, get_access_context, require_vendor_session
from app.schemas.assessment import (
    AnalysisOut, AssessmentDetail, AssessmentSummary, EvidenceOut, ResponseIn, ResponseOut,
    RiskBreakdown,
)
from app.services import assessment_service as svc
from app.services.email_service import send_completion_email, send_findings_assigned_email
from app.services.llm_analyzer import EvidenceContext, QuestionContext, get_llm_provider
from app.services.remediation import finding_generator
from app.services.report_generator import generate_assessment_report_pdf
from app.services.storage import infer_document_type, save_evidence_file

router = APIRouter(prefix="/assessments", tags=["assessments"])

ACTIVE_STATUSES = ("draft", "assigned", "in_progress")


async def _load_assessment_row(conn: asyncpg.Connection, assessment_id: UUID) -> asyncpg.Record:
    row = await conn.fetchrow(
        """
        SELECT a.*, v.legal_name AS vendor_name, t.name AS template_name, v.tier
        FROM assessments a
        JOIN vendors v ON v.id = a.vendor_id
        JOIN questionnaire_templates t ON t.id = a.template_id
        WHERE a.id = $1
        """,
        assessment_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return row


async def _audit(conn: asyncpg.Connection, ctx: AccessContext, action: str, entity_id: UUID, after: dict | None = None):
    await conn.execute(
        """
        INSERT INTO audit_logs (actor_vendor_contact_id, action, entity_type, entity_id, after_state)
        VALUES ($1, $2, 'assessment', $3, $4)
        """,
        ctx.vendor_contact_id, action, entity_id, after,
    )


@router.get("/mine", response_model=list[AssessmentSummary])
async def list_my_assessments(
    session: VendorSession = Depends(require_vendor_session), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.*, v.legal_name AS vendor_name, t.name AS template_name, v.tier
            FROM assessments a
            JOIN vendors v ON v.id = a.vendor_id
            JOIN questionnaire_templates t ON t.id = a.template_id
            WHERE a.vendor_id = $1
            ORDER BY a.created_at DESC
            """,
            session.vendor_id,
        )
        out = []
        for row in rows:
            questions = await svc.fetch_template_questions(conn, row["template_id"])
            responses = await svc.fetch_responses_by_question(conn, row["id"])
            out.append(_summary(row, questions, responses))
        return out


def _summary(row: asyncpg.Record, questions, responses) -> dict:
    return {
        "id": row["id"], "vendor_id": row["vendor_id"], "vendor_name": row["vendor_name"],
        "template_name": row["template_name"], "tier": row["tier"], "status": row["status"],
        "assigned_at": row["assigned_at"], "due_at": row["due_at"], "completed_at": row["completed_at"],
        "overall_score": float(row["overall_score"]) if row["overall_score"] is not None else None,
        "progress_pct": svc.compute_progress_pct(questions, responses),
    }


@router.get("/{assessment_id}", response_model=AssessmentDetail)
async def get_assessment(
    assessment_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])
        questions = await svc.fetch_template_questions(conn, row["template_id"])
        responses = await svc.fetch_responses_by_question(conn, assessment_id)
        evidence_rows = await svc.fetch_evidence(conn, assessment_id)

    visible = svc.visible_questions(questions, responses)
    return {
        **_summary(row, questions, responses),
        "questions": [svc.build_question_out(q) for q in visible],
        "responses": {str(q["id"]): svc.build_response_out(q["id"], responses.get(str(q["id"]))) for q in visible},
        "evidence": [dict(e) for e in evidence_rows],
    }


@router.put("/{assessment_id}/responses/{question_id}", response_model=ResponseOut)
async def save_response(
    assessment_id: UUID, question_id: UUID, body: ResponseIn,
    ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])
        if row["status"] not in ACTIVE_STATUSES:
            raise HTTPException(status_code=400, detail=f"Assessment is {row['status']}, cannot edit responses")

        question = await conn.fetchrow("SELECT id FROM questions WHERE id = $1 AND template_id = $2",
                                        question_id, row["template_id"])
        if not question:
            raise HTTPException(status_code=404, detail="Question not in this assessment's template")

        await conn.execute(
            """
            INSERT INTO assessment_responses (assessment_id, question_id, raw_answer, updated_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (assessment_id, question_id) DO UPDATE SET
                raw_answer = EXCLUDED.raw_answer, updated_at = now()
            """,
            assessment_id, question_id, body.raw_answer,
        )
        if row["status"] == "assigned":
            await conn.execute("UPDATE assessments SET status = 'in_progress' WHERE id = $1", assessment_id)

        resp = await conn.fetchrow(
            "SELECT * FROM assessment_responses WHERE assessment_id = $1 AND question_id = $2",
            assessment_id, question_id,
        )
    return svc.build_response_out(question_id, resp)


@router.post("/{assessment_id}/responses/{question_id}/analyze", response_model=AnalysisOut)
async def analyze_response(
    assessment_id: UUID, question_id: UUID,
    ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])

        question = await conn.fetchrow(
            """
            SELECT q.prompt, q.evidence_required, q.scoring_rubric, c.title AS control_title
            FROM questions q LEFT JOIN controls c ON c.id = q.control_id
            WHERE q.id = $1 AND q.template_id = $2
            """,
            question_id, row["template_id"],
        )
        if not question:
            raise HTTPException(status_code=404, detail="Question not in this assessment's template")
        resp = await conn.fetchrow(
            "SELECT raw_answer FROM assessment_responses WHERE assessment_id = $1 AND question_id = $2",
            assessment_id, question_id,
        )
        raw_answer = resp["raw_answer"] if resp else ""
        evidence_rows = await conn.fetch(
            "SELECT document_type, original_filename FROM assessment_evidence WHERE response_id IN "
            "(SELECT id FROM assessment_responses WHERE assessment_id = $1 AND question_id = $2)",
            assessment_id, question_id,
        )

    result = await _run_analysis(question, raw_answer or "", evidence_rows)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE assessment_responses SET
                classification = $3, confidence_score = $4, extracted_claims = $5,
                evidence_status = $6, follow_up_needed = $7, follow_up_question = $8,
                analyzed_at = now(), updated_at = now()
            WHERE assessment_id = $1 AND question_id = $2
            """,
            assessment_id, question_id, result.classification, result.confidence_score,
            result.extracted_claims, result.evidence_status,
            result.follow_up_needed, result.follow_up_question,
        )
    return {
        "classification": result.classification, "confidence_score": result.confidence_score,
        "extracted_claims": result.extracted_claims, "evidence_status": result.evidence_status,
        "follow_up_needed": result.follow_up_needed, "follow_up_question": result.follow_up_question,
        "analyzed_at": None,
    }


async def _run_analysis(question: asyncpg.Record, raw_answer: str, evidence_rows: list[asyncpg.Record]):
    provider = get_llm_provider()
    return await provider.analyze(
        QuestionContext(
            prompt=question["prompt"], control_title=question["control_title"],
            scoring_rubric=question["scoring_rubric"], evidence_required=question["evidence_required"],
        ),
        raw_answer,
        [EvidenceContext(document_type=e["document_type"], original_filename=e["original_filename"]) for e in evidence_rows],
    )


@router.post("/{assessment_id}/responses/{question_id}/evidence", response_model=EvidenceOut)
async def upload_evidence(
    assessment_id: UUID, question_id: UUID, file: UploadFile,
    ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])
        if row["status"] not in ACTIVE_STATUSES:
            raise HTTPException(status_code=400, detail=f"Assessment is {row['status']}, cannot upload evidence")

        response_row = await conn.fetchrow(
            "SELECT id FROM assessment_responses WHERE assessment_id = $1 AND question_id = $2",
            assessment_id, question_id,
        )
        if not response_row:
            response_row = await conn.fetchrow(
                "INSERT INTO assessment_responses (assessment_id, question_id) VALUES ($1, $2) RETURNING id",
                assessment_id, question_id,
            )

        content = await file.read()
        doc_type = infer_document_type(file.filename or "evidence", None)
        storage_uri = save_evidence_file(str(assessment_id), file.filename or "evidence", content)

        evidence = await conn.fetchrow(
            """
            INSERT INTO assessment_evidence
                (assessment_id, response_id, document_type, storage_uri, original_filename,
                 uploaded_by_vendor_contact_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            assessment_id, response_row["id"], doc_type, storage_uri, file.filename or "evidence",
            ctx.vendor_contact_id,
        )
        await _audit(conn, ctx, "evidence.uploaded", assessment_id, {"filename": file.filename, "document_type": doc_type})
    return dict(evidence)


@router.get("/{assessment_id}/risk", response_model=RiskBreakdown)
async def get_risk(
    assessment_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])
        questions = await svc.fetch_template_questions(conn, row["template_id"])
        responses = await svc.fetch_responses_by_question(conn, assessment_id)
    breakdown = svc.build_risk_breakdown(questions, responses)
    return {"assessment_id": assessment_id, **breakdown}


@router.post("/{assessment_id}/submit", response_model=AssessmentDetail)
async def submit_assessment(
    assessment_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])
        if row["status"] == "completed":
            raise HTTPException(status_code=400, detail="Assessment already completed")

        questions = await svc.fetch_template_questions(conn, row["template_id"])
        responses = await svc.fetch_responses_by_question(conn, assessment_id)
        missing = svc.missing_required_codes(questions, responses)
        if missing:
            raise HTTPException(status_code=400, detail={"message": "Answer all questions before submitting", "missing": missing})

        # Analyze any visible response that hasn't been analyzed yet.
        for q in svc.visible_questions(questions, responses):
            resp = responses.get(str(q["id"]))
            if resp and resp["classification"] is None:
                evidence_rows = await conn.fetch(
                    "SELECT document_type, original_filename FROM assessment_evidence WHERE response_id = $1",
                    resp["id"],
                )
                question_row = await conn.fetchrow(
                    """
                    SELECT q.prompt, q.evidence_required, q.scoring_rubric, c.title AS control_title
                    FROM questions q LEFT JOIN controls c ON c.id = q.control_id WHERE q.id = $1
                    """,
                    q["id"],
                )
                result = await _run_analysis(question_row, resp["raw_answer"] or "", evidence_rows)
                await conn.execute(
                    """
                    UPDATE assessment_responses SET
                        classification = $2, confidence_score = $3, extracted_claims = $4,
                        evidence_status = $5, follow_up_needed = $6, follow_up_question = $7, analyzed_at = now()
                    WHERE id = $1
                    """,
                    resp["id"], result.classification, result.confidence_score,
                    result.extracted_claims, result.evidence_status,
                    result.follow_up_needed, result.follow_up_question,
                )

        responses = await svc.fetch_responses_by_question(conn, assessment_id)
        breakdown = svc.build_risk_breakdown(questions, responses)

        await conn.execute(
            "UPDATE assessments SET status = 'completed', submitted_at = now(), completed_at = now(), overall_score = $2 WHERE id = $1",
            assessment_id, breakdown["overall_score"],
        )
        await conn.execute(
            "UPDATE vendors SET risk_score = $2, risk_score_updated_at = now(), status = 'active' WHERE id = $1",
            row["vendor_id"], breakdown["vendor_risk_score"],
        )
        await _audit(conn, ctx, "assessment.submitted", assessment_id, {"overall_score": breakdown["overall_score"]})

        new_findings = await finding_generator.generate_findings_from_assessment(conn, assessment_id)

        contact = await conn.fetchrow("SELECT email FROM vendor_contacts WHERE vendor_id = $1 AND is_primary LIMIT 1", row["vendor_id"])

        row = await _load_assessment_row(conn, assessment_id)
        evidence_rows = await svc.fetch_evidence(conn, assessment_id)

    if contact:
        send_completion_email(contact["email"], row["vendor_name"], breakdown["overall_score"])
        if new_findings:
            send_findings_assigned_email(contact["email"], row["vendor_name"], len(new_findings))

    visible = svc.visible_questions(questions, responses)
    return {
        **_summary(row, questions, responses),
        "questions": [svc.build_question_out(q) for q in visible],
        "responses": {str(q["id"]): svc.build_response_out(q["id"], responses.get(str(q["id"]))) for q in visible},
        "evidence": [dict(e) for e in evidence_rows],
    }


@router.get("/{assessment_id}/report")
async def download_report(
    assessment_id: UUID, ctx: AccessContext = Depends(get_access_context), pool: asyncpg.Pool = Depends(get_db),
):
    async with pool.acquire() as conn:
        row = await _load_assessment_row(conn, assessment_id)
        ctx.check_vendor(row["vendor_id"])
        questions = await svc.fetch_template_questions(conn, row["template_id"])
        responses = await svc.fetch_responses_by_question(conn, assessment_id)
        evidence_rows = await svc.fetch_evidence(conn, assessment_id)

    breakdown = svc.build_risk_breakdown(questions, responses)
    visible = svc.visible_questions(questions, responses)
    response_dicts = []
    for q in visible:
        resp = responses.get(str(q["id"]))
        response_dicts.append({
            "section": q["section"], "prompt": q["prompt"],
            "raw_answer": resp["raw_answer"] if resp else None,
            "classification": resp["classification"] if resp else None,
            "confidence_score": float(resp["confidence_score"]) if resp and resp["confidence_score"] is not None else None,
            "follow_up_question": resp["follow_up_question"] if resp else None,
        })

    pdf_bytes = generate_assessment_report_pdf(
        vendor_name=row["vendor_name"], tier=row["tier"], template_name=row["template_name"],
        status=row["status"], completed_at=row["completed_at"],
        overall_score=float(row["overall_score"]) if row["overall_score"] is not None else breakdown["overall_score"],
        vendor_risk_score=breakdown["vendor_risk_score"],
        classification_counts=breakdown["classification_counts"], control_scores=breakdown["control_scores"],
        responses=response_dicts, evidence=[dict(e) for e in evidence_rows],
    )
    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="assessment-{assessment_id}.pdf"',
    })
