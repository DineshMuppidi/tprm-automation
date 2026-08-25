"""Seed data for tiered questionnaire templates (Phase 1 §2).

Question counts here are a representative subset per tier, not the full
150/100/50/20 the spec calls for at each tier — the template/question data
model (questionnaire_templates -> questions, with control mapping, scoring
rubric, evidence requirements, and conditional follow-ups all as real
columns) supports scaling to the full count by adding rows; nothing about
reaching 150 questions for Tier 1 requires new code, just more content.

`depends_on` demonstrates the spec's conditional-branching requirement
("if answer is X, skip/show Y") — stored in `questions.options->>'condition'`
since the schema's `parent_question_id` records the relationship but not
the trigger value.
"""

import asyncpg

MFA_RUBRIC = {
    "strong": "MFA enforced org-wide, incident response tested, phishing-resistant methods used",
    "adequate": "MFA required for critical systems, some documented exceptions",
    "weak": "MFA recommended but not enforced",
    "missing": "No MFA in place",
}
ENCRYPTION_RUBRIC = {
    "strong": "Modern algorithm (e.g. AES-256/TLS 1.2+), enforced everywhere, key management documented",
    "adequate": "Encryption used for most systems, some gaps or undocumented scope",
    "weak": "Encryption mentioned but scope/method unclear or partial",
    "missing": "No encryption, or answer does not address it",
}
IR_RUBRIC = {
    "strong": "Documented plan, tested within 12 months, notification SLA defined and contractual",
    "adequate": "Documented plan exists, notification timeline stated but untested or informal",
    "weak": "Informal process only, no defined notification timeline",
    "missing": "No incident response process described",
}

TIER1_QUESTIONS = [
    dict(code="AC-1", section="Access Control", input_type="text", evidence_required=True, order=1,
         prompt="Describe how your organization enforces multi-factor authentication (MFA) for administrative access to systems that would process our data. Include scope (all systems vs. some) and any exceptions.",
         help_text="Be specific about which systems are covered and whether MFA is enforced or merely recommended.",
         control=("NIST_CSF_2", "PR.AC-1"), rubric=MFA_RUBRIC),
    dict(code="AC-2", section="Access Control", input_type="select", evidence_required=False, order=2,
         prompt="Is access to production systems reviewed and re-certified on a regular schedule?",
         help_text=None, options={"choices": ["Quarterly", "Annually", "Ad hoc / no formal schedule", "Not performed"]},
         control=("NIST_CSF_2", "PR.AC-1"), rubric=None),
    dict(code="ENC-1", section="Encryption", input_type="text", evidence_required=True, order=3,
         prompt="Describe your encryption approach for customer data at rest, including algorithm and key management.",
         help_text=None, control=("NIST_CSF_2", "PR.DS-1"), rubric=ENCRYPTION_RUBRIC),
    dict(code="ENC-2", section="Encryption", input_type="text", evidence_required=True, order=4,
         prompt="Describe your encryption approach for customer data in transit, including protocols and certificate management.",
         help_text=None, control=("NIST_CSF_2", "PR.DS-2"), rubric=ENCRYPTION_RUBRIC),
    dict(code="CERT-1", section="Certifications & Audits", input_type="text", evidence_required=True, order=5,
         prompt="What compliance certifications or audit reports does your organization currently hold (e.g., SOC 2 Type II, ISO 27001)? Include audit dates and current status.",
         help_text="Please upload the most recent report as evidence.", control=None, rubric=None),
    dict(code="MON-1", section="Monitoring & Logging", input_type="text", evidence_required=False, order=6,
         prompt="Describe how you monitor systems for security events and how long logs are retained.",
         help_text=None, control=("NIST_CSF_2", "DE.CM-1"), rubric=None),
    dict(code="IR-1", section="Incident Response", input_type="text", evidence_required=True, order=7,
         prompt="Do you have a documented incident response plan? What is your contractual notification timeline to customers in the event of a breach affecting their data?",
         help_text=None, control=("NIST_CSF_2", "PR.IP-9"), rubric=IR_RUBRIC),
    dict(code="IR-2", section="Incident Response", input_type="select", evidence_required=False, order=8,
         prompt="Has your incident response plan been tested (tabletop exercise or live) in the past 12 months?",
         help_text=None, options={"choices": ["Yes", "No"]}, control=("NIST_CSF_2", "PR.IP-9"), rubric=None),
    dict(code="BC-1", section="Business Continuity", input_type="text", evidence_required=False, order=9,
         prompt="Describe your backup strategy and how frequently backups are tested for successful restoration.",
         help_text=None, control=("NIST_CSF_2", "PR.IP-4"), rubric=None),
    dict(code="DATA-1", section="Data Handling", input_type="select", evidence_required=False, order=10,
         prompt="Do you store, process, or transmit our data in any environment outside your primary production systems (e.g., backups, logs, development/test, analytics)?",
         help_text=None, options={"choices": ["Yes", "No"]}, control=None, rubric=None),
    dict(code="DATA-1A", section="Data Handling", input_type="text", evidence_required=False, order=11,
         prompt="Describe the additional controls applied to protect our data in those non-production/secondary environments.",
         help_text=None, control=None, rubric=None, depends_on=("DATA-1", "Yes")),
    dict(code="DATA-2", section="Data Handling", input_type="text", evidence_required=False, order=12,
         prompt="Describe your data retention and secure disposal practices when a customer relationship ends.",
         help_text=None, control=("NIST_CSF_2", "PR.DS-3"), rubric=None),
    dict(code="TRAIN-1", section="Personnel", input_type="select", evidence_required=False, order=13,
         prompt="How frequently does your organization require security awareness training for personnel with access to customer data?",
         help_text=None, options={"choices": ["Quarterly", "Annually", "Ad hoc", "Not required"]},
         control=("NIST_CSF_2", "PR.AT-1"), rubric=None),
    dict(code="VEND-1", section="Sub-processor Risk", input_type="text", evidence_required=False, order=14,
         prompt="Do you use sub-processors or fourth parties who would have access to our data? Describe how you assess and monitor their security posture.",
         help_text=None, control=("SOC2", "CC9.2"), rubric=None),
]

TIER2_QUESTIONS = [
    dict(code="T2-AC-1", section="Access Control", input_type="text", evidence_required=False, order=1,
         prompt="Describe access controls for systems handling our data.", help_text=None,
         control=("NIST_CSF_2", "PR.AC-1"), rubric=None),
    dict(code="T2-ENC-1", section="Encryption", input_type="text", evidence_required=False, order=2,
         prompt="Is data encrypted at rest and in transit? Describe briefly.", help_text=None,
         control=("NIST_CSF_2", "PR.DS-2"), rubric=None),
    dict(code="T2-AVAIL-1", section="Availability", input_type="text", evidence_required=False, order=3,
         prompt="What is your uptime/availability commitment (SLA) for this service?", help_text=None,
         control=None, rubric=None),
    dict(code="T2-AVAIL-2", section="Availability", input_type="text", evidence_required=False, order=4,
         prompt="Describe your backup and disaster recovery approach.", help_text=None,
         control=("NIST_CSF_2", "PR.IP-4"), rubric=None),
    dict(code="T2-IR-1", section="Incident Response", input_type="text", evidence_required=False, order=5,
         prompt="Do you have an incident notification process? What is the typical timeline?", help_text=None,
         control=("NIST_CSF_2", "PR.IP-9"), rubric=None),
    dict(code="T2-CERT-1", section="Certifications", input_type="text", evidence_required=False, order=6,
         prompt="Do you hold any security certifications (SOC 2, ISO 27001, etc.)?", help_text=None,
         control=None, rubric=None),
    dict(code="T2-DATA-1", section="Data Handling", input_type="select", evidence_required=False, order=7,
         prompt="How long is our data retained after contract termination?", help_text=None,
         options={"choices": ["<30 days", "30-90 days", ">90 days", "Indefinite / not defined"]},
         control=("NIST_CSF_2", "PR.DS-3"), rubric=None),
    dict(code="T2-MON-1", section="Monitoring", input_type="select", evidence_required=False, order=8,
         prompt="Do you monitor your systems for security incidents 24/7?", help_text=None,
         options={"choices": ["Yes", "No", "Partial"]}, control=("NIST_CSF_2", "DE.CM-1"), rubric=None),
    dict(code="T2-PERS-1", section="Personnel", input_type="select", evidence_required=False, order=9,
         prompt="Do employees with data access undergo background checks?", help_text=None,
         options={"choices": ["Yes", "No", "Unsure"]}, control=None, rubric=None),
]

TIER3_QUESTIONS = [
    dict(code="T3-AC-1", section="Access Control", input_type="select", evidence_required=False, order=1,
         prompt="Is access to your systems protected by unique user accounts (no shared logins)?", help_text=None,
         options={"choices": ["Yes", "No"]}, control=("NIST_CSF_2", "PR.AC-1"), rubric=None),
    dict(code="T3-ENC-1", section="Encryption", input_type="select", evidence_required=False, order=2,
         prompt="Is data encrypted in transit (e.g., HTTPS/TLS)?", help_text=None,
         options={"choices": ["Yes", "No", "Unsure"]}, control=("NIST_CSF_2", "PR.DS-2"), rubric=None),
    dict(code="T3-IR-1", section="Incident Response", input_type="text", evidence_required=False, order=3,
         prompt="Do you have a way to notify us if you experience a security incident affecting our data?",
         help_text=None, control=("NIST_CSF_2", "PR.IP-9"), rubric=None),
    dict(code="T3-CERT-1", section="Certifications", input_type="text", evidence_required=False, order=4,
         prompt="Do you hold any security certifications or undergo third-party security audits?",
         help_text=None, control=None, rubric=None),
    dict(code="T3-DATA-1", section="Data Handling", input_type="select", evidence_required=False, order=5,
         prompt="What type of our data would you access or store (if any)?", help_text=None,
         options={"choices": ["None", "Business/contact info only", "Confidential business data", "Personal data (PII)"]},
         control=None, rubric=None),
    dict(code="T3-BC-1", section="Business Continuity", input_type="select", evidence_required=False, order=6,
         prompt="Do you have a backup process for the data/service you provide?", help_text=None,
         options={"choices": ["Yes", "No", "Unsure"]}, control=("NIST_CSF_2", "PR.IP-4"), rubric=None),
]

TIER4_QUESTIONS = [
    dict(code="T4-INFO-1", section="Vendor Info", input_type="text", evidence_required=False, order=1,
         prompt="Briefly describe the service or product you provide to us.", help_text=None,
         control=None, rubric=None),
    dict(code="T4-DATA-1", section="Data Handling", input_type="select", evidence_required=False, order=2,
         prompt="Will you access, store, or process any of our company data, systems, or facilities?",
         help_text=None, options={"choices": ["Yes", "No"]}, control=None, rubric=None),
    dict(code="T4-DATA-2", section="Data Handling", input_type="text", evidence_required=False, order=3,
         prompt="Please describe what data or systems you would access.", help_text=None,
         control=None, rubric=None, depends_on=("T4-DATA-1", "Yes")),
    dict(code="T4-SEC-1", section="Security Basics", input_type="select", evidence_required=False, order=4,
         prompt="Do you have basic security practices in place (e.g., antivirus, password policies)?",
         help_text=None, options={"choices": ["Yes", "No", "Unsure"]}, control=None, rubric=None),
]

TEMPLATES = [
    ("Tier 1 — Critical Vendor Assessment", "tier_1_critical", TIER1_QUESTIONS),
    ("Tier 2 — High Risk Vendor Assessment", "tier_2_high", TIER2_QUESTIONS),
    ("Tier 3 — Medium Risk Vendor Assessment", "tier_3_medium", TIER3_QUESTIONS),
    ("Tier 4 — Low Risk Vendor Assessment", "tier_4_low", TIER4_QUESTIONS),
]


async def seed_templates(conn: asyncpg.Connection, control_ids: dict[tuple[str, str], str]) -> None:
    for name, tier, questions in TEMPLATES:
        template_row = await conn.fetchrow(
            "SELECT id FROM questionnaire_templates WHERE name = $1 AND tier = $2", name, tier,
        )
        if template_row:
            template_id = template_row["id"]
        else:
            template_row = await conn.fetchrow(
                "INSERT INTO questionnaire_templates (name, tier) VALUES ($1, $2) RETURNING id",
                name, tier,
            )
            template_id = template_row["id"]

        question_ids_by_code: dict[str, str] = {}
        for q in questions:
            options = dict(q.get("options") or {})
            depends_on = q.get("depends_on")
            if depends_on:
                options["condition"] = {"question_code": depends_on[0], "equals": depends_on[1]}

            control_id = control_ids[q["control"]] if q.get("control") else None

            row = await conn.fetchrow(
                """
                INSERT INTO questions
                    (template_id, question_code, section, prompt, help_text, input_type,
                     options, control_id, scoring_rubric, evidence_required, display_order)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (template_id, question_code) DO UPDATE SET
                    prompt = EXCLUDED.prompt,
                    options = EXCLUDED.options,
                    control_id = EXCLUDED.control_id,
                    scoring_rubric = EXCLUDED.scoring_rubric,
                    evidence_required = EXCLUDED.evidence_required,
                    display_order = EXCLUDED.display_order
                RETURNING id
                """,
                template_id, q["code"], q["section"], q["prompt"], q.get("help_text"), q["input_type"],
                options or None, control_id,
                q.get("rubric"), q["evidence_required"], q["order"],
            )
            question_ids_by_code[q["code"]] = row["id"]

        # Second pass: wire parent_question_id now that all questions in this
        # template have ids (a follow-up can reference a question defined
        # earlier in the same list).
        for q in questions:
            depends_on = q.get("depends_on")
            if depends_on:
                parent_id = question_ids_by_code[depends_on[0]]
                await conn.execute(
                    "UPDATE questions SET parent_question_id = $1 WHERE id = $2",
                    parent_id, question_ids_by_code[q["code"]],
                )
