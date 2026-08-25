"""Shared query/aggregation logic behind the assessment endpoints — kept out
of the router so the router stays a thin HTTP shim over these functions.
"""

from uuid import UUID

import asyncpg

from app.services.risk_scoring import ScoredResponse, compute_risk_breakdown

QUESTIONS_SQL = """
    SELECT q.id, q.question_code, q.section, q.prompt, q.help_text, q.input_type,
           q.options, q.evidence_required, q.display_order, q.control_id, q.scoring_rubric,
           c.control_ref, c.title AS control_title, c.framework_id,
           f.code AS framework_code
    FROM questions q
    LEFT JOIN controls c ON c.id = q.control_id
    LEFT JOIN frameworks f ON f.id = c.framework_id
    WHERE q.template_id = $1
    ORDER BY q.display_order
"""


async def fetch_template_questions(conn: asyncpg.Connection, template_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(QUESTIONS_SQL, template_id)


async def fetch_responses_by_question(conn: asyncpg.Connection, assessment_id: UUID) -> dict[str, asyncpg.Record]:
    rows = await conn.fetch(
        "SELECT * FROM assessment_responses WHERE assessment_id = $1", assessment_id,
    )
    return {str(r["question_id"]): r for r in rows}


async def fetch_evidence(conn: asyncpg.Connection, assessment_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT * FROM assessment_evidence WHERE assessment_id = $1 ORDER BY uploaded_at", assessment_id,
    )


def is_visible(question: asyncpg.Record, answers_by_code: dict[str, str | None]) -> bool:
    options = question["options"] or {}
    condition = options.get("condition")
    if not condition:
        return True
    dep_answer = answers_by_code.get(condition["question_code"])
    return (dep_answer or "").strip().lower() == str(condition["equals"]).strip().lower()


def _answers_by_code(
    questions: list[asyncpg.Record], responses_by_qid: dict[str, asyncpg.Record],
) -> dict[str, str | None]:
    result = {}
    for q in questions:
        resp = responses_by_qid.get(str(q["id"]))
        result[q["question_code"]] = resp["raw_answer"] if resp else None
    return result


def visible_questions(
    questions: list[asyncpg.Record], responses_by_qid: dict[str, asyncpg.Record],
) -> list[asyncpg.Record]:
    by_code = _answers_by_code(questions, responses_by_qid)
    return [q for q in questions if is_visible(q, by_code)]


def compute_progress_pct(
    questions: list[asyncpg.Record], responses_by_qid: dict[str, asyncpg.Record],
) -> float:
    visible = visible_questions(questions, responses_by_qid)
    if not visible:
        return 0.0
    answered = 0
    for q in visible:
        resp = responses_by_qid.get(str(q["id"]))
        if resp and (resp["raw_answer"] or "").strip():
            answered += 1
    return round(answered / len(visible) * 100, 1)


def missing_required_codes(
    questions: list[asyncpg.Record], responses_by_qid: dict[str, asyncpg.Record],
) -> list[str]:
    """Every *visible* question must have a non-empty answer before submit."""
    missing = []
    for q in visible_questions(questions, responses_by_qid):
        resp = responses_by_qid.get(str(q["id"]))
        if not resp or not (resp["raw_answer"] or "").strip():
            missing.append(q["question_code"])
    return missing


def build_question_out(q: asyncpg.Record) -> dict:
    return {
        "id": q["id"],
        "question_code": q["question_code"],
        "section": q["section"],
        "prompt": q["prompt"],
        "help_text": q["help_text"],
        "input_type": q["input_type"],
        "options": q["options"],
        "evidence_required": q["evidence_required"],
        "display_order": q["display_order"],
    }


def build_response_out(question_id: UUID, resp: asyncpg.Record | None) -> dict:
    if resp is None:
        return {
            "question_id": question_id,
            "raw_answer": None,
            "analysis": {
                "classification": None, "confidence_score": None, "extracted_claims": None,
                "evidence_status": "unverified", "follow_up_needed": False,
                "follow_up_question": None, "analyzed_at": None,
            },
        }
    return {
        "question_id": question_id,
        "raw_answer": resp["raw_answer"],
        "analysis": {
            "classification": resp["classification"],
            "confidence_score": float(resp["confidence_score"]) if resp["confidence_score"] is not None else None,
            "extracted_claims": resp["extracted_claims"],
            "evidence_status": resp["evidence_status"],
            "follow_up_needed": resp["follow_up_needed"],
            "follow_up_question": resp["follow_up_question"],
            "analyzed_at": resp["analyzed_at"],
        },
    }


def build_risk_breakdown(
    questions: list[asyncpg.Record], responses_by_qid: dict[str, asyncpg.Record],
) -> dict:
    scored = []
    for q in questions:
        resp = responses_by_qid.get(str(q["id"]))
        scored.append(ScoredResponse(
            question_id=str(q["id"]),
            classification=resp["classification"] if resp else None,
            evidence_required=q["evidence_required"],
            control_id=str(q["control_id"]) if q["control_id"] else None,
            control_ref=q["control_ref"],
            control_title=q["control_title"],
            framework_id=str(q["framework_id"]) if q["framework_id"] else None,
            framework_code=q["framework_code"],
        ))
    return compute_risk_breakdown(scored)
