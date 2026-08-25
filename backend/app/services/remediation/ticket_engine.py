"""Remediation ticket state machine (Phase 3 spec §2):

    NEW -> ASSIGNED -> IN_PROGRESS -> SUBMITTED -> VALIDATING -> CLOSED
                  ^                         |              |
                  '------ REJECTED <--------+--------------'
                      (vendor revises plan/evidence, resubmits)

`rejected` is not a dead end — it's the spec's own wording for "send it
back for revision" at two different points (a non-credible plan, or
insufficient evidence), and the vendor moves forward again by taking the
next action (resubmitting a plan, or uploading more evidence and
resubmitting). `submitted` -> `validating` happens synchronously inside
`submit_for_validation` (evidence review runs immediately, same pattern as
Phase 1's analyze-on-submit) rather than needing a separate manual trigger
— the intermediate status is still written and audit-logged, just not
something a caller has to wait through separately.
"""

from datetime import datetime, timedelta, timezone

import asyncpg

from app.services.llm_analyzer import EvidenceContext
from app.services.remediation.evidence_validator import FindingContext, get_remediation_review_provider

CLOSURE_RISK_REDUCTION = {"critical": 10.0, "high": 6.0, "medium": 3.0, "low": 1.0}


class InvalidTransition(Exception):
    pass


async def _add_comment(
    conn: asyncpg.Connection, finding_id: str, author_type: str, body: str,
    author_vendor_contact_id: str | None = None, author_user_id: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO finding_comments (finding_id, author_type, author_vendor_contact_id, author_user_id, body)
        VALUES ($1, $2, $3, $4, $5)
        """,
        finding_id, author_type, author_vendor_contact_id, author_user_id, body,
    )


def _finding_context(finding: asyncpg.Record) -> FindingContext:
    return FindingContext(
        title=finding["title"], description=finding["description"],
        required_evidence=finding["required_evidence"], severity=finding["severity"],
    )


async def acknowledge_finding(conn: asyncpg.Connection, finding_id: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        "UPDATE findings SET status = 'assigned', acknowledged_at = now(), updated_at = now() "
        "WHERE id = $1 AND status = 'new' RETURNING *",
        finding_id,
    )
    if not row:
        raise InvalidTransition("Finding must be in 'new' status to acknowledge")
    return row


async def submit_remediation_plan(conn: asyncpg.Connection, finding_id: str, plan_text: str) -> dict:
    finding = await conn.fetchrow("SELECT * FROM findings WHERE id = $1", finding_id)
    if finding["status"] not in ("assigned", "in_progress", "rejected"):
        raise InvalidTransition(f"Cannot submit a plan while status is '{finding['status']}'")

    provider = get_remediation_review_provider()
    review = await provider.review_plan(_finding_context(finding), plan_text)
    review_json = {"credible": review.credible, "reasoning": review.reasoning, "follow_up_question": review.follow_up_question}
    new_status = "in_progress" if review.credible else "rejected"

    await conn.execute(
        """
        UPDATE findings SET remediation_plan = $2, remediation_plan_submitted_at = now(),
            remediation_plan_review = $3, status = $4,
            rejection_count = rejection_count + $5, updated_at = now()
        WHERE id = $1
        """,
        finding_id, plan_text, review_json, new_status, 0 if review.credible else 1,
    )
    await _add_comment(conn, finding_id, "vendor", plan_text)
    await _add_comment(
        conn, finding_id, "system",
        "Plan accepted — remediation is now in progress." if review.credible
        else (review.follow_up_question or review.reasoning),
    )
    return {"status": new_status, "credible": review.credible, "reasoning": review.reasoning}


async def submit_for_validation(conn: asyncpg.Connection, finding_id: str) -> dict:
    finding = await conn.fetchrow("SELECT * FROM findings WHERE id = $1", finding_id)
    if finding["status"] not in ("in_progress", "rejected"):
        raise InvalidTransition(f"Cannot submit for validation while status is '{finding['status']}'")

    evidence_rows = await conn.fetch(
        "SELECT id, document_type, original_filename FROM remediation_evidence WHERE finding_id = $1", finding_id,
    )
    if not evidence_rows:
        raise InvalidTransition("At least one piece of evidence is required before submitting for validation")

    await conn.execute(
        "UPDATE findings SET status = 'submitted', submitted_at = now(), updated_at = now() WHERE id = $1", finding_id,
    )
    await conn.execute("UPDATE findings SET status = 'validating', updated_at = now() WHERE id = $1", finding_id)

    provider = get_remediation_review_provider()
    evidence_ctx = [EvidenceContext(document_type=r["document_type"], original_filename=r["original_filename"]) for r in evidence_rows]
    result = await provider.validate_evidence(_finding_context(finding), evidence_ctx, finding["remediation_plan"] or "")

    validation_json = {"recommendation": result.recommendation, "confidence": result.confidence, "reasoning": result.reasoning}
    await conn.execute(
        "UPDATE remediation_evidence SET llm_validation_result = $2, reviewed_at = now() WHERE finding_id = $1",
        finding_id, validation_json,
    )

    if result.recommendation == "approve":
        await conn.execute(
            "UPDATE findings SET status = 'closed', closed_at = now(), updated_at = now() WHERE id = $1", finding_id,
        )
        await _add_comment(conn, finding_id, "system", f"Evidence approved: {result.reasoning}")
        await _reduce_risk_on_closure(conn, finding["vendor_id"], finding["severity"], factor=1.0)
        new_status = "closed"
    else:
        await conn.execute(
            "UPDATE findings SET status = 'rejected', rejection_count = rejection_count + 1, updated_at = now() WHERE id = $1",
            finding_id,
        )
        await _add_comment(conn, finding_id, "system", result.follow_up_question or result.reasoning)
        new_status = "rejected"

    return {"status": new_status, "recommendation": result.recommendation, "reasoning": result.reasoning}


async def _reduce_risk_on_closure(conn: asyncpg.Connection, vendor_id: str, severity: str, factor: float) -> None:
    delta = CLOSURE_RISK_REDUCTION.get(severity, 1.0) * factor
    await conn.execute(
        "UPDATE vendors SET risk_score = GREATEST(0, risk_score - $2), risk_score_updated_at = now() WHERE id = $1 AND risk_score IS NOT NULL",
        vendor_id, delta,
    )


async def admin_close_finding(conn: asyncpg.Connection, finding_id: str, note: str | None = None) -> asyncpg.Record:
    finding = await conn.fetchrow("SELECT * FROM findings WHERE id = $1", finding_id)
    if not finding or finding["status"] == "closed":
        raise InvalidTransition("Finding not found or already closed")
    row = await conn.fetchrow(
        "UPDATE findings SET status = 'closed', closed_at = now(), updated_at = now() WHERE id = $1 RETURNING *", finding_id,
    )
    if note:
        await _add_comment(conn, finding_id, "internal", note)
    await _reduce_risk_on_closure(conn, finding["vendor_id"], finding["severity"], factor=1.0)
    return row


async def admin_reject_finding(conn: asyncpg.Connection, finding_id: str, note: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        "UPDATE findings SET status = 'rejected', rejection_count = rejection_count + 1, updated_at = now() "
        "WHERE id = $1 RETURNING *",
        finding_id,
    )
    if not row:
        raise InvalidTransition("Finding not found")
    await _add_comment(conn, finding_id, "internal", note)
    return row


async def add_comment(
    conn: asyncpg.Connection, finding_id: str, author_type: str, body: str,
    author_vendor_contact_id: str | None = None, author_user_id: str | None = None,
) -> None:
    await _add_comment(conn, finding_id, author_type, body, author_vendor_contact_id, author_user_id)


# --- Exceptions (Phase 3 spec §4 Scenario 3: "vendor claims they can't remediate") --------

async def request_exception(
    conn: asyncpg.Connection, finding_id: str, justification: str, compensating_controls: str | None,
) -> asyncpg.Record:
    expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    exception = await conn.fetchrow(
        """
        INSERT INTO exceptions (finding_id, justification, compensating_controls, expires_at)
        VALUES ($1, $2, $3, $4) RETURNING *
        """,
        finding_id, justification, compensating_controls, expires_at,
    )
    await _add_comment(conn, finding_id, "vendor", f"Exception requested: {justification}")
    return exception


async def approve_exception(conn: asyncpg.Connection, exception_id: str, approved_by_user_id: str | None) -> asyncpg.Record:
    exception = await conn.fetchrow(
        "UPDATE exceptions SET approved_by_id = $2, approved_at = now() WHERE id = $1 RETURNING *",
        exception_id, approved_by_user_id,
    )
    if not exception:
        raise InvalidTransition("Exception not found")
    finding = await conn.fetchrow(
        "UPDATE findings SET status = 'exception_granted', updated_at = now() WHERE id = $1 RETURNING *",
        exception["finding_id"],
    )
    await _add_comment(conn, exception["finding_id"], "internal", "Exception approved — risk formally accepted.")
    await _reduce_risk_on_closure(conn, finding["vendor_id"], finding["severity"], factor=0.5)
    return exception
