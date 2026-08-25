"""Five playbook definitions (Phase 4 spec §3). Each covers specifically
the steps NOT already handled by existing Phase 2/3 code, to avoid
duplicating already-tested behavior through a template interpreter:

  * vendor_breach_response — Phase 2's alert_engine + impact_assessor
    already notify stakeholders and open a critical finding when a breach
    alert fires. This playbook adds the one step nothing else does yet:
    scheduling the 30-day post-incident review (spec's playbook 1, step 10).
  * cert_critical_expiring — Phase 2/3 already alert and open a finding.
    This adds the vendor-facing renewal request email and an internal
    14-day follow-up reminder (spec's playbook 2, steps 1-3).
  * vendor_fails_critical_assessment — genuinely new: nothing currently
    triggers on a vendor's assessment risk score itself crossing critical.
  * vendor_financial_distress — Phase 2 already alerts/opens a finding.
    This adds the category-manager-specific business-continuity nudge.
  * remediation_deadline_missed — Phase 3's escalation_engine already
    notifies Legal at 14+ days overdue. This adds the vendor-facing final
    notice email that nothing currently sends.
"""

import asyncpg

PLAYBOOKS = [
    (
        "vendor_breach_response", "Vendor Breach Response", "alert.breach.critical",
        [{"type": "schedule_review", "days_from_now": 30, "note": "Post-incident review: was the vendor's remediation credible?"}],
    ),
    (
        "cert_critical_expiring", "Critical Certification Expiring", "alert.cert_expiry.critical",
        [
            {"type": "notify_vendor", "template": "cert_renewal_request"},
            {"type": "schedule_review", "days_from_now": 14, "note": "Check whether vendor has provided an updated audit/certification"},
        ],
    ),
    (
        "vendor_fails_critical_assessment", "Vendor Fails Critical Assessment", "assessment.completed.risk_critical",
        [
            {"type": "notify_role", "role": "ciso", "message_template": "critical_assessment_alert"},
            {"type": "notify_role", "role": "compliance_officer", "message_template": "critical_assessment_alert"},
            {"type": "schedule_review", "days_from_now": 7, "note": "Business continuity assessment: is this vendor critical, and replaceable?"},
        ],
    ),
    (
        "vendor_financial_distress", "Vendor Financial Distress", "alert.financial_distress.high",
        [
            {"type": "notify_role", "role": "category_manager", "message_template": "financial_distress_alert"},
            {"type": "schedule_review", "days_from_now": 14, "note": "Business continuity / backup-vendor planning"},
        ],
    ),
    (
        "remediation_deadline_missed", "Remediation Deadline Missed", "finding.legal_escalated",
        [
            {"type": "notify_role", "role": "legal", "message_template": "deadline_missed_final_notice"},
            {"type": "notify_vendor", "template": "final_notice"},
        ],
    ),
]


async def seed_playbooks(conn: asyncpg.Connection) -> None:
    for code, name, trigger_event, steps in PLAYBOOKS:
        await conn.execute(
            """
            INSERT INTO playbook_definitions (code, name, trigger_event, steps)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, trigger_event = EXCLUDED.trigger_event, steps = EXCLUDED.steps
            """,
            code, name, trigger_event, steps,
        )
