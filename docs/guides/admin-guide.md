# Admin Guide

System administration — deployment configuration, user/vendor management,
and settings not covered by the compliance-officer day-to-day workflow.

## Environment configuration

Every setting lives in `backend/.env` (copy from `.env.example`) and maps
1:1 to `app/config.py`'s `Settings` fields. The ones worth knowing:

- **`LLM_PROVIDER`** (`mock`|`live`): controls every LLM-backed feature at
  once (assessment scoring, plan/evidence review, contract parsing) — one
  switch, not one per feature. `live` needs `ANTHROPIC_API_KEY` set.
- **`{CERT_REGISTRY,BREACH,NEWS,FINANCIAL}_PROVIDER`**: same mock/live
  pattern for monitoring sources — see `docs/architecture/integrations.md`
  for which live providers are actually network-tested vs. correctly
  written but untested for lack of a key.
- **`ADMIN_API_KEY`**: the shared secret gating most of `/admin/*`.
  Rotate it by changing this value and redeploying — there's no
  revocation list to manage, it's just string comparison.
- **`AUTH_SECRET`**: signs every JWT (vendor sessions, staff sessions,
  magic links). **Must be at least 32 bytes** — PyJWT will warn (not
  error) below that; `openssl rand -hex 32` generates a good one.
  Rotating it invalidates every active session immediately, vendor and
  staff both — see Runbook 10 in `docs/operations/runbooks.md`.
- **`RATE_LIMIT_REQUESTS_PER_MINUTE`**: default 120. See Runbook 8 before
  changing it under pressure — the limiter is per-process, so the
  effective limit scales with replica count on a multi-instance
  deployment.

## Creating and managing internal staff accounts

Staff accounts are rows in the `users` table (`email`, `full_name`,
`role`, `is_active`) — seeded via `app/seed/seed_users.py` for the demo
roles (`ciso`, `compliance_officer`, `category_manager`, `legal`). There's
no admin UI for this yet (a real gap — see `security-hardening.md`'s RBAC
section); add/deactivate accounts directly via SQL or extend
`seed_users.py`'s pattern until an admin endpoint exists.

Staff sign in the same magic-link way vendors do, at `/staff/auth/request-link`
→ `/staff/auth/verify` — the session JWT carries their `role`, which is
what `require_role(...)`-gated endpoints check.

## Vendor lifecycle

Vendors move through `status`: `prospective` → `onboarding` → `active` →
(`under_review` / `remediation_required` as needed) → `suspended` /
`offboarding` → `terminated`. Most of the platform's queries already
exclude `terminated` vendors from active views (monitoring checks, board
reporting) — terminating a vendor is the right way to stop it from
generating new alerts/findings without deleting its history.

## Data retention

Documented in `backend/db/schema/schema.sql`'s closing comment (3-7 years
by table, matching common compliance-record retention norms) but **not
currently enforced by any running job** — this is a known gap, not
silently handled. A real deployment needs a scheduled archival job before
relying on this for actual regulatory retention compliance.

## Deploying

See the root `README.md`'s "Running it" section for local dev.
For anything beyond local dev:
- `docker-compose.yml` — single-VM deployment.
- `k8s/` — Kubernetes, with its own README on what's templated vs. not.
- `terraform/` — supporting AWS infrastructure (RDS, S3, WAF, Secrets
  Manager), also with its own README on scope.

None of the container/cluster/cloud infrastructure was actually run in
this project's development environment (no Docker/kubectl/terraform
available) — every file was written to be correct against the tool
versions it targets, not executed. Treat first use in a real environment
as a first real test, same as you would for any infra you didn't author
yourself.
