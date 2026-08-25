# Training: IT/Security Team (2 hours)

## Session outline

**1. System architecture overview (30 min)**
- Walk `docs/architecture/architecture.md`'s diagram: edge → app tier →
  async/scheduled tier → data tier.
- Where each phase's work lives: assessment engine (Phase 1), monitoring
  (Phase 2), remediation (Phase 3), contracts/frameworks/playbooks
  (Phase 4), this hardening pass (Phase 5).
- The mock/live provider pattern used everywhere (LLM, monitoring
  sources) — why it exists (offline dev, no paid keys required) and how
  to flip a source to live in a real deployment.

**2. How monitoring detects issues (30 min)**
- Four source categories, each its own Airflow DAG in a real deployment
  (`backend/airflow_dags/README.md` — not run in the dev sandbox this
  was built in, written to be deployed for real).
- Live demo: `POST /admin/monitoring/run-checks` against the seeded demo
  vendor, watch alerts/findings/playbook executions appear.
- Alert dedup/suppression — why re-running checks doesn't spam duplicate
  alerts (`docs/monitoring/alert-routing.md`).

**3. Incident response procedures (30 min)**
- The ransomware scenario walkthrough end to end
  (`docs/architecture/scenario-vendor-ransomware.md` and
  `docs/monitoring/incident-response-playbook-vendor-breach.md`) — what's
  automated (impact assessment, stakeholder notification, incident
  finding) vs. what's still a human call (confirming actual scope with
  the vendor, drafting regulator notifications).
- Where playbook executions are logged and how to audit what an
  automated response actually did (`/admin/board`'s Playbook Executions
  tab, backed by the real `playbook_executions` table).

**4. Troubleshooting common issues (30 min)**
- Walk `docs/operations/runbooks.md` — pick 3-4 most relevant to this
  org's actual deployment (DB down, monitoring API down, rate limiting,
  LLM provider degraded) and demo the diagnostic steps live.
- `/health/ready` vs `/health/live` vs `/metrics` — what each actually
  checks, and how to read Prometheus output by hand if no dashboard is
  wired up yet.

**5. Security posture, honestly (20 min)**
- Walk `docs/operations/security-hardening.md`'s status table — what's
  implemented, what's deferred, and why (this is deliberately not a
  "we're fully secure" pitch; know the real gaps, especially the RBAC
  retrofit's partial coverage and the in-memory rate limiter's
  multi-replica limitation).

**6. Hands-on lab (10 min)**
- Trigger a rate-limit 429 on purpose (`scripts/load_test.py` against a
  non-exempt endpoint) and find it in `/metrics`.
