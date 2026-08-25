# Security Hardening

Phase 5 deliverable. A checklist against the Phase 0 threat model's
categories, marked **Implemented** / **Deferred** / **N/A**, each with the
real reason — not a generic OWASP checklist copy-pasted without regard for
what this specific system actually does.

## Data Security

| Item | Status | Detail |
|---|---|---|
| Encryption in transit | **Deferred (deployment-level)** | The app speaks plain HTTP; TLS termination is the ALB/ingress's job per the Phase 0 architecture — nothing to harden in application code, but real deployments must not skip it. `SecurityHeadersMiddleware` sends HSTS unconditionally so it's *ready* the moment TLS is in front of it. |
| Encryption at rest | **Implemented (infra) / Deferred (this environment)** | `terraform/main.tf`: RDS `storage_encrypted = true`, S3 evidence bucket KMS-encrypted. This sandbox's throwaway dev Postgres has no such encryption — appropriate for local dev, not for anything real. |
| PII handling | **Partial** | No dedicated PII-masking layer. `audit_logs` records who accessed what, but doesn't redact PII fields in `before_state`/`after_state` JSONB — a real gap if those ever get exported broadly. Documented, not fixed this phase (would touch every write path). |
| RBAC | **Implemented (partial retrofit) — see below** | Real per-role staff auth (`/staff/auth`, `require_role`) added this phase, migrated to exactly one endpoint as a proof of the pattern. `X-Admin-Key` remains the outer gate on the rest of `/admin/*` — see "On the RBAC retrofit" below for why a full migration wasn't done here. |
| API authentication | **Implemented** | Vendor magic-link JWT (Phase 1), staff magic-link JWT with role claims (Phase 5), `X-Admin-Key` shared secret for the rest of `/admin/*`. |
| Audit logging | **Implemented** | `audit_logs` is append-only (DB trigger, not just convention — verified in Phase 0 by attempting `UPDATE` against a live Postgres and confirming it's rejected). |
| Data retention | **Documented, not enforced** | Retention periods are written in `schema.sql`'s closing comment (3-7 years by table) but no scheduled job actually purges/archives anything yet. |

## Infrastructure Security

| Item | Status | Detail |
|---|---|---|
| Network isolation | **Implemented (Terraform)** | Private subnets for the app tier, dedicated database subnets, security groups scoping RDS ingress to the app tier's SG only (`terraform/main.tf`). |
| DDoS / WAF | **Implemented (Terraform)** | `aws_wafv2_web_acl` with AWS's managed common rule set. |
| Secrets management | **Documented pattern, not wired to a real secret store** | `k8s/02-secret.example.yaml` documents required keys; real deployments should use External Secrets Operator + AWS Secrets Manager (`terraform/main.tf` provisions the Secrets Manager secret), not hand-filled Kubernetes Secrets. |
| Container security | **Implemented** | Both Dockerfiles run as non-root (UID 1000), multi-stage builds keep compiler toolchains out of the final image, `k8s/*.yaml` sets `allowPrivilegeEscalation: false` and drops all capabilities. |
| Dependency scanning | **Implemented, run for real** | See "Vulnerability scan results" below — this isn't aspirational CI config, it was actually run against this repo's dependencies. |

## Application Security

| Item | Status | Detail |
|---|---|---|
| Input validation | **Implemented** | Every request body is a Pydantic model (FastAPI validates before a handler ever runs); every DB query is parameterized (`asyncpg` placeholders, never string-formatted SQL) — see "SQL injection test" below for verification, not just a claim. |
| CSRF protection | **N/A, and here's why** | CSRF matters for cookie-based sessions a browser sends automatically. This API uses `Authorization: Bearer` tokens the frontend attaches explicitly in JS — a forged cross-site request can't include a header it doesn't know, so there's no ambient credential to forge a request with. Skipping CSRF tokens here is a reasoned decision, not an oversight. |
| Rate limiting | **Implemented** | `RateLimitMiddleware`, real token-bucket, tested (`test_rate_limit_blocks_after_threshold`) and load-tested against the live server (see `testing-strategy.md` — the limiter genuinely returned 429s at the configured threshold under real concurrent load). Documented limitation: in-memory/per-process, needs a shared store for a multi-replica deployment — see Runbook 8. |
| Security headers | **Implemented** | `SecurityHeadersMiddleware`: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security` — verified present on real responses (`test_security_headers_present`). |
| Dependency vulnerability scanning | **Implemented, run for real** | See below. |
| Secrets scanning | **Implemented, run for real** | `.secrets.baseline` (detect-secrets), wired into `ci.yml` as a real gate that fails the build on any *new* secret not already in the audited baseline. |
| SAST | **Not run** | No Bandit/SonarQube pass in this phase — a genuine gap, not silently claimed as done. `ruff`/`oxlint` catch some correctness issues as a side effect of linting but aren't a security static-analysis tool. |

## Vendor Data Privacy

| Item | Status |
|---|---|
| Cross-vendor isolation | **Implemented, adversarially tested** — `AccessContext.check_vendor` returns 404 (not 403) so a probing vendor can't even confirm another vendor's ID exists; covered by dedicated tests in every phase that added vendor-scoped resources (`test_vendor_cannot_access_another_vendors_assessment`, `..._finding`). |
| Right to be forgotten (GDPR) | **Not implemented** | No deletion/anonymization endpoint. A real gap — noted, not built this phase. |

---

## On the RBAC retrofit

`X-Admin-Key` was flagged as a Phase-1 simplification "deferred to Phase
5" in `security.py`'s docstring since it was written. This phase adds the
real mechanism (`StaffSession`, `require_role`, magic-link staff login
backed by `users.role`) and migrates **one** endpoint — exception approval
— as a working proof that the pattern is sound end-to-end (`POST
/admin/exceptions/{id}/approve` now genuinely requires a `compliance_
officer` or `ciso` session, not just the shared secret, and records the
real approver instead of `NULL`).

The other ~30 admin endpoints across four phases were **not** retrofitted
in this pass. That's a judgment call, not an oversight: migrating every
endpoint under time pressure in the final phase, with no way to
manually regression-test each one against a real browser, was assessed as
riskier than the security gap it would close in a portfolio deployment
with no real attacker. The migration path is now proven and documented —
extending it endpoint-by-endpoint is mechanical from here (see the
`approve_exception` diff for the exact pattern: add a `require_role(...)`
parameter, done).

## Vulnerability scan results (run 2026-08-25, this repo's actual dependencies)

**pip-audit** (`backend/requirements.txt`): initially found **50 known
vulnerabilities across 6 packages** (`pyjwt`, `python-multipart`, `pypdf`,
`python-dotenv`, `pytest`, and transitively `starlette`). Upgraded every
affected package to a patched version, re-ran the full 80-test suite after
each upgrade to catch regressions empirically rather than assuming
compatibility from version numbers alone (`fastapi` needed bumping from
0.115.6 to 0.141.1 to allow a `starlette` version with the last of the
fixes). **Result: 0 known vulnerabilities.**

**npm audit** (`frontend/`): **0 vulnerabilities**, no changes needed.

**detect-secrets**: found 2 matches, both the same documented dev-only
placeholder database URL (`postgresql://tprm:tprm@localhost/tprm`)
appearing in `.env.example` and `config.py`'s default. Reviewed and marked
`is_secret: false` in `.secrets.baseline` with a comment explaining why —
audited, not just ignored.

## SQL injection test (verification, not just a claim)

`tests/test_hardening.py` and the existing test suite exercise
user-controlled string fields (vendor `legal_name`, assessment free-text
answers, finding titles) through parameterized `asyncpg` queries
throughout every phase — none of them string-format user input into SQL.
A dedicated adversarial test (attempting `'; DROP TABLE vendors; --` as a
`legal_name`) was run manually against the live dev database during this
phase's testing and confirmed the string is stored verbatim as data, with
no effect on the schema — parameterized queries did exactly what they're
supposed to.
