# Remediation Playbook: 90-Day Vendor Remediation Campaign

Phase 3 deliverable — the spec's own scenario (§7: a financial services
company with 200 findings across vendors after a SOX assessment, tracked
over 90 days), walked through against what's actually built, not a
hypothetical.

## Day 1 — Findings generated

`POST /assessments/{id}/submit` (Phase 1) completing an assessment
triggers `finding_generator.generate_findings_from_assessment` (Phase 3
§1 Trigger 1): every weak/missing/contradictory response becomes a
`new` finding with severity/due-date already set per the spec's table
(critical: 30 days, high: 60, medium: 90, low: 120). At scale — 200
findings across many vendors from many assessments — this is the same
function running once per assessment submission, not a batch job; each
vendor's findings appear as soon as their assessment is done.

## Day 4 — Unacknowledged findings

`daily_finding_escalation_check` (or the manual `POST /admin/findings/
run-escalation-check` trigger) calls `check_unacknowledged_findings`:
any `new` finding older than 3 days emails the vendor a reminder and
notifies the category manager. This keeps firing daily for as long as a
finding sits unacknowledged — a live nag, not a one-shot reminder.

## Day 10–20 — Plans and evidence

As vendors acknowledge and submit plans, `PUT /findings/{id}/plan` runs
`review_plan` — a vague plan bounces back to `rejected` with a specific
follow-up question (not just "try again"); a credible one moves to
`in_progress`. Evidence submission (`POST /findings/{id}/submit`) runs
`validate_evidence` synchronously: approved evidence closes the finding
and reduces the vendor's risk score immediately; insufficient evidence
bounces back to `rejected` with a specific ask, same as the spec's own
"your screenshot shows 1 account, can you confirm scope" example.

## Day 35 — Missed deadlines

`check_overdue_findings` transitions any finding past `due_at` (and not
yet closed/exempted) to `overdue`, notifying category manager and
compliance officer. `GET /admin/monitoring/scoreboard`-style visibility
(here, `GET /admin/findings?status=overdue`) shows exactly which vendors
are behind — this is what the Vendor Performance tab on `/admin/findings`
renders directly from `reporting.vendor_performance`.

## Day 49 — Legal escalation

`check_severely_overdue_findings`: any finding overdue by 14+ days
escalates to Legal, once (tracked via an `audit_logs` marker so it doesn't
re-fire every day — see `escalation_engine.py`'s docstring).

## Day 60 — Exceptions

A vendor who genuinely can't remediate (legacy system constraints, the
spec's own example) calls `POST /findings/{id}/request-exception` with a
justification and compensating controls — this creates an `exceptions`
row via `ticket_engine.request_exception`. Compliance reviews pending
requests on the Exceptions tab of `/admin/findings` and approves via
`POST /admin/exceptions/{id}/approve`, which sets the finding to
`exception_granted` and applies a *partial* risk-score reduction (the
risk is accepted, not eliminated — see `state-machine.md`).

## Day 90 — Reporting

`GET /admin/reporting/kpis` (rendered as the KPI cards atop
`/admin/findings`) answers the spec's own closing questions directly:
- **Closure rate** — `remediation_velocity.by_status` + `closed_last_30_days`
- **MTTR by severity** — `remediation_velocity.mttr_by_severity`
- **Vendor performance / who's behind** — `vendor_performance`, sorted
  by overdue count
- **Rework rate** (did vendors get it right the first time?) —
  `quality.rework_rate_pct`, computed from `rejection_count > 0` on
  closed findings
- **Exception rate** — `quality.exception_rate_pct`
- **Regulatory readiness** — `risk_and_regulatory.evidence_coverage_pct`
  (% of closed findings that actually have evidence on file — the thing
  an external auditor asks for)

The one number the spec's scenario reports that this build genuinely
can't (documented, not faked): risk score *improvement* as a before/after
trend. `risk_and_regulatory` reports the current distribution only — see
`reporting.py`'s module docstring for exactly what a `risk_score_history`
table would need to add.
