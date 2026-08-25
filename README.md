# TPRM Automation Platform

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![PostgreSQL](https://img.shields.io/badge/db-PostgreSQL%2015%2B-336791)
![Status](https://img.shields.io/badge/status-Phase%204%20%E2%80%94%20advanced%20features-blue)
![No Paid Services Required](https://img.shields.io/badge/monitoring%20APIs-mockable%2C%20no%20paid%20keys%20required-informational)

Portfolio project: a production-shaped Third-Party Risk Management platform
— vendor questionnaires with LLM-powered scoring, continuous monitoring for
breaches/cert expiry/financial distress, an accountable remediation
workflow, and contract/control-framework mapping — aimed at the actual
1,500-hour/year manual workload a Fortune 500 GRC team carries for vendor
risk, not a toy CRUD demo.

Built phase by phase; each phase is reviewed before the next starts. See
[Roadmap](#roadmap) for status.

```
Vendor intake & assessment  ->  Continuous monitoring  ->  Remediation workflow
        (Phase 1)                   (Phase 2)                  (Phase 3)
                                        |
                    Contracts / control mapping / playbooks (Phase 4)
                                        |
                        Production hardening & ops (Phase 5)
```

## Why this exists

Vendor risk management at scale is a spreadsheet-and-email problem dressed
up as a security program: hundreds of vendors, annual questionnaires nobody
enjoys reading, certifications that quietly expire, and findings that get
"remediated" with a promise instead of evidence. This platform automates
the parts that are mechanical (scoring, tracking, escalating, cross-
referencing a contract against an assessment) so the humans spend their
time on the parts that actually need judgment (is this vendor's excuse for
missing MFA acceptable, is this evidence real).

## Architecture

Full design — system diagram, data flow, scalability/failover posture,
failure points — lives in [`docs/architecture/architecture.md`](docs/architecture/architecture.md).
Supporting docs from the same design pass:

- [`data model`](backend/db/schema/schema.sql) — full PostgreSQL schema (25 tables), executable; validated against a live Postgres 18 instance
- [`integration points`](docs/architecture/integrations.md) — every external API, auth, rate limits, fallback behavior, cost, data sensitivity
- [`threat model`](docs/architecture/threat-model.md) — RBAC, encryption, audit-log immutability, vendor data isolation, third-party-compromise blast radius
- [`tech stack rationale`](docs/architecture/tech-stack.md) — why FastAPI/Postgres/Airflow/Claude/React, and what was rejected
- [`scenario walkthrough`](docs/architecture/scenario-vendor-ransomware.md) — a healthcare vendor ransomware incident traced through every layer, minute by minute

**Design principle carried through every phase:** monitoring sources can
*create alerts*; nothing outside a human-reviewed finding/playbook pipeline
can change a vendor's risk score, status, or contract state. See the threat
model for why that's load-bearing, not incidental.

## What's built (Phase 1)

- **Vendor portal** (React + Tailwind): passwordless magic-link login,
  tiered questionnaire (Tier 1–4) with section navigation, autosaved
  answers, drag-and-drop evidence upload, conditional follow-up questions,
  and a results page with a risk gauge and a downloadable PDF report.
- **LLM answer analysis**: classifies each response (Strong/Adequate/Weak/
  Missing/Contradictory), extracts key claims, and flags follow-ups —
  `mock` by default (deterministic, offline, free) or `live` against the
  real Claude API. The mock provider implements the exact SOC 2 Type I/II
  contradiction scenario from the project brief as a real, tested code
  path, not just a paragraph in a doc.
- **Automated risk scoring**: per-control and per-framework aggregation,
  evidence-weighted, rolling up to a vendor risk score.
- **Admin screen** (`/admin`): create a vendor, assign a questionnaire
  tier, see all assessments in flight.
- Enforces the Phase 0 threat model's vendor-isolation guarantee at the API
  layer (cross-vendor access → 404) — covered by an integration test.

Question counts are a representative subset per tier (the brief calls for
150/100/50/20) — the template/question data model supports scaling to the
full count by adding rows, not by changing code; see
[`seed_templates.py`](backend/app/seed/seed_templates.py).

## What's built (Phase 2)

- **Continuous monitoring** across four source categories — certification
  registries, breach/CVE feeds, news/reputation, financial distress — each
  behind a `mock`/`live` provider interface (see
  [`adding-a-data-source.md`](docs/monitoring/adding-a-data-source.md)).
  Two live providers are genuinely network-tested against real, free,
  keyless APIs (NVD for CVEs, SEC EDGAR full-text search for financial
  distress); the rest are correctly implemented against their documented
  request/response shapes but need a paid/registered key this build
  doesn't have — see `live_providers.py`'s docstring for exactly which.
- **Alert engine**: deduplication (one open alert per vendor+type),
  suppression (with a 90-day expiry and an audit trail), evidence-weighted
  risk-score deltas, and role-based routing (critical → CISO + Compliance
  + Category Manager + Legal; medium → Compliance only) — see
  [`alert-routing.md`](docs/monitoring/alert-routing.md) for the full
  pipeline diagram and real payload examples.
- **Incident impact assessment**: a critical breach alert automatically
  queries which business units/data types are affected and opens a
  critical `findings` row with that context — see
  [`incident-response-playbook-vendor-breach.md`](docs/monitoring/incident-response-playbook-vendor-breach.md)
  for exactly which steps are automated vs. still manual.
- **Escalation**: unacknowledged critical/high alerts auto-escalate past
  their SLA (60 / 240 minutes) and notify the CISO directly.
- **Monitoring dashboard** (`/admin/monitoring`): live alert feed with
  acknowledge/resolve/suppress actions, a vendor risk scoreboard, and a
  data-source health panel — plus a "Run checks now" button, since Airflow
  itself isn't running in this environment (see below).
- One demo vendor (`primary_domain` matching `acmehr-demo.example.com`,
  which is exactly what `seed_demo_data.py` creates) deterministically
  reproduces the Phase 0 ransomware scenario across all four sources when
  you run the checks — same story, now actually executable.

**On Airflow:** the four scheduled DAGs the spec calls for
(`daily_certification_check`, `hourly_breach_check`,
`daily_news_monitoring`, `weekly_financial_check`) plus an
`escalation_check` sweep are written as real Airflow 3.x DAG definitions
in [`backend/airflow_dags/`](backend/airflow_dags/) — but Airflow itself
was not installed or run in this sandbox (no Docker, no root, and Airflow
brings its own metadata DB + scheduler + API server to stand up). Every
DAG task is a thin wrapper calling straight into
`monitoring_service.py`, which *is* what's tested (unit + live-Postgres
integration) — see that directory's `README.md` for the honest version of
this tradeoff and how to actually deploy them.

## What's built (Phase 3)

- **Finding generation, two triggers**: a completed assessment's weak/
  missing/contradictory responses become findings automatically (severity
  and due-date per the spec's own table — critical: 30 days, high: 60,
  medium: 90, low: 120); a critical/high monitoring alert opens one too
  (breach alerts get the richer Phase 2 impact-assessment treatment, cert/
  CVE/financial ones get a direct finding). See
  [`finding_generator.py`](backend/app/services/remediation/finding_generator.py).
- **Remediation state machine**: `new → assigned → in_progress → submitted
  → validating → closed`, with `rejected` as a real, visible "send it back
  for revision" state (not a dead end) reachable from either a
  non-credible plan or insufficient evidence — see
  [`state-machine.md`](docs/remediation/state-machine.md) for the full
  diagram and the reasoning behind that design choice.
- **LLM-powered plan and evidence review**: does the vendor's remediation
  plan name concrete actions and a timeline, or is it vague hand-waving?
  Does the uploaded evidence actually prove the fix, or (the spec's own
  example) is it a screenshot of one account claiming org-wide MFA? See
  [`evidence-validation-guide.md`](docs/remediation/evidence-validation-guide.md).
- **Escalation & accountability**: unacknowledged findings get a daily
  reminder; overdue findings notify category management; findings overdue
  14+ days escalate to Legal (once, tracked via the audit trail so it
  doesn't re-fire daily); repeated rejected submissions flag for
  compliance review.
- **Exceptions**: a vendor who can't remediate requests one with a
  justification and compensating controls; compliance approves it, which
  formally accepts the risk (a *partial* risk-score reduction, not a full
  one — the gap is still there, just knowingly tolerated).
- **Vendor self-service** (`/findings`): view assigned findings, submit a
  plan, upload evidence, message the compliance team, request an
  exception — all with inline feedback from the LLM review, not a black
  box that just says "rejected."
- **Compliance dashboard** (`/admin/findings`): all findings with
  filters, vendor performance (closure rate, overdue count), pending
  exceptions, and KPI cards (MTTR by severity, rework rate, evidence
  coverage) — see
  [`remediation-playbook.md`](docs/remediation/remediation-playbook.md)
  for the spec's own 90-day scenario walked through against these exact
  endpoints.
- A `daily_finding_escalation_check` Airflow DAG (same "not executed
  here, written correctly, service layer is what's tested" honesty as
  Phase 2's monitoring DAGs).

One gap, documented rather than glossed over: "risk improvement" in the
Phase 3 spec means a before/after trend, and this build only reports the
*current* risk distribution — there's no `risk_score_history` snapshot
mechanism yet. See `reporting.py`'s module docstring.

## What's built (Phase 4)

- **Contract parsing** (`/admin/contracts`): upload a contract (PDF or
  `.txt`), extract SLA/uptime, breach-notification SLA, named security
  requirements, audit rights, liability, indemnification, and termination/
  renewal terms — same mock/live provider split as every other LLM-backed
  feature. The mock provider uses targeted regexes against real contract
  language, not toy strings — see
  [`contract-compliance.md`](docs/advanced/contract-compliance.md), which
  also documents a real bug (numbered section headings matching before the
  actual clause) found and fixed while smoke-testing this against an
  actual sample contract.
- **Contract obligation tracking & compliance checking**: each extracted
  requirement becomes a trackable `contract_obligations` row; checking
  compliance reuses Phase 2's alert engine outright (`contract_violation`
  has been sitting unused in the schema's `alert_type` enum since Phase 0)
  rather than building a parallel notification path.
- **Cross-framework control mapping** (`/admin/board` → Vendor Coverage
  tab): "vendor covers 85% of NIST CSF, 78% of SOC 2" made real — a
  vendor's assessment answers are credited across frameworks by walking
  the `control_mappings` graph seeded in Phase 0, so one NIST-framed
  questionnaire implies SOC 2/ISO 27001/HIPAA coverage too. Includes the
  spec's own HIPAA gap-analysis scenario ("SOC 2 certified ≠ HIPAA
  compliant — here's exactly what's missing") and a control-gap
  scorecard across the whole vendor base. See
  [`control-mapping-guide.md`](docs/advanced/control-mapping-guide.md).
- **Generalized playbook engine**: `playbook_definitions` rows (5 seeded)
  each name a trigger and an ordered step sequence, executed and logged to
  `playbook_executions` by one small interpreter — deliberately additive
  to Phases 2/3's already-tested hardcoded logic, covering only the steps
  nothing else handles yet (e.g. scheduling the 30-day post-incident
  review after a breach, which nothing previously did). See
  [`playbook-engine.md`](docs/advanced/playbook-engine.md) for exactly
  what's new per playbook vs. already covered, and how to add a sixth.
- **Board reporting dashboard** (`/admin/board`): vendor risk distribution,
  remediation KPIs (Phase 3), top control gaps (Phase 4), upcoming
  contract renewals, and a live playbook-execution log — one consolidated
  view spanning three phases, matching the spec's own healthcare-org
  quarterly board scenario.

## Running it

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 15+.

**Backend**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # defaults work as-is for local dev
createdb tprm                        # or point DATABASE_URL at an existing one
python db/init_db.py                 # applies schema.sql + seeds frameworks/templates
python db/seed_demo_data.py          # creates a demo vendor + prints a login URL
uvicorn app.main:app --reload        # http://localhost:8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

Open the login URL `seed_demo_data.py` printed to walk through the
questionnaire as the demo vendor, or open `/admin` (key from
`ADMIN_API_KEY` in `.env`, default `dev-admin-key`) to assign a fresh one.
Completing that assessment auto-generates findings you can then work
through at `/findings` as the vendor. Open `/admin/monitoring` and click
**Run checks now** to see the demo vendor's alerts, risk score, and
auto-created incident finding appear live — that button runs exactly what
the Airflow DAGs would run on a schedule, and also fires the matching
playbooks. `/admin/findings` is the compliance-side view: all findings,
vendor performance, pending exceptions, and KPIs. `/admin/contracts` lets
you upload a contract for that vendor and check it for compliance;
`/admin/board` is the consolidated board-reporting view (KPIs, control
gaps, contract renewals, playbook execution log, and per-vendor framework
coverage).

External monitoring integrations (HIBP, NewsAPI, D&B, and the cert
registries) default to `mock` providers so the platform runs fully offline
with zero paid API keys — see
[`integrations.md`](docs/architecture/integrations.md) for how to swap in
real ones. `LLM_PROVIDER` and `EMAIL_PROVIDER` follow the same pattern
(see `backend/.env.example`).

**Tests**
```bash
cd backend && source venv/bin/activate && pytest   # 71 tests: scoring, LLM analyzer, monitoring/alerts, remediation workflow, contracts, framework mapping, playbooks, full API flow
```
Two of those tests (`test_live_providers_network.py`) call the real NVD
and SEC EDGAR APIs and skip themselves automatically if the network is
unreachable.

## Roadmap

- [x] **Phase 0 — Foundation & Architecture**: system design, data model,
      integration points, threat model, scenario walkthrough, tech stack
- [x] **Phase 1 — Vendor Assessment Engine**: questionnaire portal, LLM
      answer analysis, automated risk scoring, PDF assessment reports
- [x] **Phase 2 — Continuous Monitoring & Alerts**: cert/breach/CVE/news/
      financial-distress monitoring via Airflow, alert routing & escalation,
      incident impact assessment
- [x] **Phase 3 — Remediation Workflow**: finding-to-closure state machine,
      evidence validation engine, escalation & exception handling, KPI
      reporting
- [x] **Phase 4 — Advanced Features**: contract parsing & compliance
      mapping, cross-framework control mapping (NIST CSF ↔ SOC 2 ↔ ISO
      27001 ↔ HIPAA), incident-response playbook engine
- [ ] **Phase 5 — Production Hardening**: CI/CD, security hardening, test
      suites, operational runbooks, disaster recovery, documentation &
      training materials

Each phase's detailed requirements are tracked against the original spec
in `~/Desktop/TPRM_Automation_Enterprise_Prompt.txt`.
