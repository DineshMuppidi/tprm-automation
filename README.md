# TPRM Automation Platform

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![PostgreSQL](https://img.shields.io/badge/db-PostgreSQL%2015%2B-336791)
![Status](https://img.shields.io/badge/status-Phase%201%20%E2%80%94%20assessment%20engine-blue)
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

External monitoring integrations for later phases (HIBP, Shodan, NewsAPI,
D&B, ...) default to `mock` providers so the platform runs fully offline
with zero paid API keys — see
[`integrations.md`](docs/architecture/integrations.md) for how to swap in
real ones. `LLM_PROVIDER` and `EMAIL_PROVIDER` follow the same pattern
today (see `backend/.env.example`).

**Tests**
```bash
cd backend && source venv/bin/activate && pytest   # 14 tests: scoring, LLM analyzer, full API flow
```

## Roadmap

- [x] **Phase 0 — Foundation & Architecture**: system design, data model,
      integration points, threat model, scenario walkthrough, tech stack
- [x] **Phase 1 — Vendor Assessment Engine**: questionnaire portal, LLM
      answer analysis, automated risk scoring, PDF assessment reports
- [ ] **Phase 2 — Continuous Monitoring & Alerts**: cert/breach/CVE/news/
      financial-distress monitoring via Airflow, alert routing & escalation,
      incident impact assessment
- [ ] **Phase 3 — Remediation Workflow**: finding-to-closure state machine,
      evidence validation engine, escalation & exception handling, KPI
      reporting
- [ ] **Phase 4 — Advanced Features**: contract parsing & compliance
      mapping, cross-framework control mapping (NIST CSF ↔ SOC 2 ↔ ISO
      27001 ↔ HIPAA), incident-response playbook engine
- [ ] **Phase 5 — Production Hardening**: CI/CD, security hardening, test
      suites, operational runbooks, disaster recovery, documentation &
      training materials

Each phase's detailed requirements are tracked against the original spec
in `~/Desktop/TPRM_Automation_Enterprise_Prompt.txt`.
