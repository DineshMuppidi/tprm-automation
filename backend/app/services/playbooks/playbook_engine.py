"""Generalized playbook engine (Phase 4 spec §3). `playbook_definitions`
rows (seeded — see app/seed/seed_playbooks.py) name a `trigger_event` and
an ordered list of `steps`; `trigger_playbook` looks up the active
definition for an event and executes each step, logging to
`playbook_executions`.

Deliberately additive to Phases 2/3, not a replacement for them: the
breach-response impact assessment (Phase 2's `impact_assessor`) and the
14-day Legal escalation (Phase 3's `escalation_engine`) already work and
are tested. Rather than re-deriving that already-correct behavior through
a template interpreter — designing a general abstraction from a sample
size of one is how you get the wrong abstraction — each seeded playbook
here covers specifically the steps the spec describes that ISN'T already
handled elsewhere. See seed_playbooks.py for exactly what's new per
playbook vs. what already happens through existing Phase 2/3 code paths.
"""

import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from app.services.email_service import Email, get_email_provider

logger = logging.getLogger("tprm.playbooks")

# step "type" -> (subject_template, body_template) for notify_vendor steps
VENDOR_EMAIL_TEMPLATES = {
    "cert_renewal_request": (
        "Certification Renewal Requested — {vendor_name}",
        "Hello,\n\nOur records show your certification is expiring soon. Please provide an "
        "updated audit report as soon as it's available so we can keep your account in good "
        "standing.\n\n— TPRM Automation Platform",
    ),
    "final_notice": (
        "FINAL NOTICE — Remediation Required",
        "Hello,\n\nThe finding referenced below is significantly overdue. Please respond within "
        "5 business days with an updated remediation plan, or we will begin evaluating contract "
        "enforcement options.\n\nFinding: {finding_title}\n\n— TPRM Automation Platform",
    ),
}

# step "message_template" -> body template for notify_role steps
ROLE_MESSAGE_TEMPLATES = {
    "critical_assessment_alert": (
        "Vendor {vendor_name} scored a critical risk ({risk_score:.0f}/100) on their latest "
        "assessment. Immediate review requested — is this vendor business-critical, and can it "
        "be replaced if remediation stalls?"
    ),
    "financial_distress_alert": (
        "Vendor {vendor_name} shows signs of financial distress. Consider whether business "
        "continuity / backup-vendor planning is warranted."
    ),
    "deadline_missed_final_notice": (
        "Finding for {vendor_name} is severely overdue ({finding_title}). Contract enforcement "
        "action may be warranted — a final notice has been sent to the vendor."
    ),
}


async def _execute_step(conn: asyncpg.Connection, step: dict, context: dict) -> dict:
    step_type = step["type"]

    if step_type == "notify_vendor":
        contact = await conn.fetchrow(
            "SELECT email FROM vendor_contacts WHERE vendor_id = $1 AND is_primary LIMIT 1", context["vendor_id"],
        )
        if not contact:
            return {"type": step_type, "skipped": "no primary vendor contact"}
        subject_tpl, body_tpl = VENDOR_EMAIL_TEMPLATES[step["template"]]
        get_email_provider().send(Email(to=contact["email"], subject=subject_tpl.format(**context), body=body_tpl.format(**context)))
        return {"type": step_type, "sent_to": contact["email"]}

    if step_type == "notify_role":
        rows = await conn.fetch("SELECT email FROM users WHERE role = $1 AND is_active", step["role"])
        message = ROLE_MESSAGE_TEMPLATES[step["message_template"]].format(**context)
        for r in rows:
            get_email_provider().send(Email(to=r["email"], subject=f"[Playbook] {context.get('vendor_name', '')}", body=message))
        return {"type": step_type, "notified": [r["email"] for r in rows]}

    if step_type == "schedule_review":
        review_at = datetime.now(timezone.utc) + timedelta(days=step["days_from_now"])
        await conn.execute(
            "INSERT INTO audit_logs (action, entity_type, entity_id, after_state) VALUES ('playbook.review_scheduled', 'vendor', $1, $2)",
            context["vendor_id"], {"review_at": review_at.isoformat(), "note": step["note"]},
        )
        return {"type": step_type, "review_at": review_at.isoformat(), "note": step["note"]}

    return {"type": step_type, "error": f"unknown step type '{step_type}'"}


async def trigger_playbook(
    conn: asyncpg.Connection, trigger_event: str, vendor_id: str, context: dict,
    alert_id: str | None = None, finding_id: str | None = None,
) -> asyncpg.Record | None:
    """Best-effort: a playbook failing should never take down the code path
    that triggered it (an alert firing, an assessment submitting) — errors
    are logged and the execution is marked failed, not re-raised."""
    definition = await conn.fetchrow(
        "SELECT * FROM playbook_definitions WHERE trigger_event = $1 AND is_active LIMIT 1", trigger_event,
    )
    if not definition:
        return None

    execution = await conn.fetchrow(
        """
        INSERT INTO playbook_executions (playbook_id, vendor_id, triggered_by_alert_id, triggered_by_finding_id, status)
        VALUES ($1, $2, $3, $4, 'running') RETURNING *
        """,
        definition["id"], vendor_id, alert_id, finding_id,
    )

    step_log = []
    full_context = {"vendor_id": vendor_id, **context}
    status = "completed"
    try:
        for step in definition["steps"]:
            result = await _execute_step(conn, step, full_context)
            step_log.append({**result, "at": datetime.now(timezone.utc).isoformat()})
    except Exception as e:  # noqa: BLE001 — recorded, not propagated (see docstring)
        logger.exception("Playbook '%s' step failed for vendor %s", trigger_event, vendor_id)
        step_log.append({"error": str(e), "at": datetime.now(timezone.utc).isoformat()})
        status = "failed"

    await conn.execute(
        "UPDATE playbook_executions SET status = $2, step_log = $3, completed_at = now() WHERE id = $1",
        execution["id"], status, step_log,
    )
    return await conn.fetchrow("SELECT * FROM playbook_executions WHERE id = $1", execution["id"])
