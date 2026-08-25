# Testing Strategy

Phase 5 deliverable. What's actually tested in this codebase, with real
numbers from real runs — not the spec's aspirational targets restated as
if they were achieved.

## Test suite

**81 tests, all passing** (`cd backend && pytest`), spanning:

- **Unit tests**: risk-scoring math, LLM analyzer heuristics (mock
  provider), evidence/plan-review heuristics, news classification,
  contract-term extraction regexes, control-mapping traversal logic.
- **Integration tests**: every workflow state machine exercised against a
  **live PostgreSQL 18 instance**, not mocks — assessment submission →
  finding generation, the full remediation state machine including the
  reject/resubmit loop, the monitoring alert → playbook trigger chain,
  contract compliance checking, framework coverage/gap analysis.
- **API-level tests**: auth flows (vendor and staff magic-link), RBAC
  enforcement (`test_exception_approval_requires_staff_role_not_just_
  admin_key` — the actual 401→403→200 progression, not just "gate
  exists"), cross-vendor isolation (404, not 403, on every vendor-scoped
  resource type added across five phases).
- **Real-network tests**: `test_live_providers_network.py` calls the
  actual NVD and SEC EDGAR APIs (free, keyless) and skips itself
  automatically if the network is unreachable, rather than mocking what
  claims to be a "live" integration test.

## Coverage — real number, not the spec's 85% target restated

```
pytest --cov=app --cov-report=term-missing
```
**77% overall** (2,573 statements, 596 missed). Breakdown worth knowing,
not just the headline number:

- **Service/business logic is well covered**: `risk_scoring.py` 100%,
  `assessment_service.py` 98%, `finding_generator.py` 95%,
  `contract_compliance.py` 95%, `coverage.py` (framework mapping) 99%.
- **Seed scripts show 0%** — `seed_frameworks.py`, `seed_templates.py`,
  etc. are never imported by pytest, but they *are* exercised for real:
  every phase's manual smoke-testing ran `db/init_db.py` against a live
  Postgres instance and verified the seeded data (frameworks, templates,
  playbooks) came out correct. 0% *unit*-test coverage on idempotent
  data-loading scripts that are otherwise verified isn't the same gap as
  0% coverage on untested business logic — lumping them into one number
  without this context would be misleading in the other direction.
- **Router (HTTP-layer) coverage is thinner than service-layer coverage**
  in a few places (`admin.py` 42%, `monitoring.py` 43%) — the underlying
  service functions those routers call are well-tested directly; the
  routers themselves were more often verified by hand via live `curl`
  smoke tests during development (documented in each phase's commit
  message) than by dedicated HTTP-level pytest cases. A real next step,
  not claimed as already done.
- **`storage.py` (25%)**: the local-filesystem evidence storage path is
  exercised indirectly through evidence-upload tests but has no dedicated
  unit tests of its own (`infer_document_type`'s edge cases, in
  particular).

Full breakdown reproducible with the command above.

## Load testing — real numbers, not synthetic

`backend/scripts/load_test.py`, run against the actual local backend
(uvicorn, real Postgres, real middleware stack including the new rate
limiter):

| Endpoint | Concurrency | Requests | p50 | p95 | p99 | Result |
|---|---|---|---|---|---|---|
| `/health/ready` (DB round-trip, rate-limit exempt) | 50 | 500 | 29.6ms | 71.2ms | 83.0ms | 500/500 succeeded, 1,342 req/s |
| `/admin/vendors` (DB query, rate-limited) | 20 | 200 | 23.6ms | 86.9ms | 152.0ms | Exactly 120 succeeded, 80 correctly rejected with 429 — the rate limiter enforcing its configured 120/min limit under real concurrent load, not just in a unit test |

Caveat: this is a single-instance local run against a throwaway dev
Postgres, not a provisioned RDS instance under realistic network latency —
useful as a smoke-level performance baseline and a genuine demonstration
that the rate limiter works under load, not as a production capacity plan.

## Security testing

- **SQL injection**: attempted directly against the live API
  (`POST /admin/vendors` with a `legal_name` of `Evil Corp'; DROP TABLE
  vendors; --`) — stored verbatim as data, `vendors` table unaffected.
  See `security-hardening.md` for the full transcript.
- **Cross-vendor access**: adversarial tests across every vendor-scoped
  resource type (assessments, findings) confirm 404 responses, not just
  403 — see `security-hardening.md`'s vendor-privacy section.
- **RBAC bypass attempts**: `test_exception_approval_requires_staff_role_
  not_just_admin_key` verifies admin-key-alone is rejected (401), a
  wrong-role staff session is rejected (403), and only the correct role
  succeeds (200) — the full negative-then-positive path, not just "it
  works when given the right credentials."
- **Dependency vulnerabilities**: pip-audit and npm audit, both run for
  real — see `security-hardening.md`.
- **Penetration testing / OWASP Top 10 scan**: not performed. Genuinely
  out of scope for a solo portfolio build in this timeframe — noted as a
  gap a real production launch would need, not silently skipped without
  mention.

## Compliance testing

- **PII/audit trail**: `audit_logs` immutability verified against a live
  Postgres instance (attempted `UPDATE`, confirmed rejected by the DB
  trigger) — done in Phase 0, still true today (nothing since has altered
  that table's grants or trigger).
- **Access control**: covered above (cross-vendor isolation, RBAC).
- **Retention**: documented in `schema.sql`'s closing comment, **not
  enforced by any running job** — see `security-hardening.md`'s data
  security table for the honest status.
- **GDPR right-to-be-forgotten**: not implemented — see
  `security-hardening.md`.

## CI pipeline (what actually runs on every push)

`.github/workflows/ci.yml` runs, in order: pip-audit → detect-secrets
(against the audited baseline, failing only on *new* findings) → schema
apply + seed → `pytest --cov` → Docker build-check (backend and
frontend, `push: false`) → (frontend job) `oxlint` → `tsc --noEmit` →
`npm audit` → `npm run build` → Docker build-check. Not run by an actual
GitHub Actions runner in this session (no git remote configured on this
repo), but every command in it is the exact command verified locally
throughout Phases 0-5.
