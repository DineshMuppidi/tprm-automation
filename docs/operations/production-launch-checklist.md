# Production Launch Checklist

Phase 5 deliverable — adapted from the spec's own launch-day scenario
(§9), rewritten against what this specific build actually has ready vs.
what a real launch would still need to do first.

## Pre-launch (1 week before)

- [ ] `terraform apply` run against a real AWS account, plan reviewed by
      someone other than whoever wrote it — **not done**; this repo's
      Terraform has never touched real infrastructure.
- [ ] CI green on the actual GitHub Actions runner (not just verified
      locally) — **not done**; no git remote is configured on this repo.
- [ ] `AUTH_SECRET`, `ADMIN_API_KEY`, and every provider API key rotated
      to real, non-default values (never the `.env.example` placeholders).
- [ ] `pip-audit` / `npm audit` clean — **done**, see
      `docs/operations/security-hardening.md` (0 vulnerabilities as of
      this phase, re-run before an actual launch since new CVEs publish
      continuously).
- [ ] Full test suite green — **done locally** (81/81); re-run in CI on
      the real runner before launch, don't trust a stale local run.
- [ ] Backup/restore cycle tested against the *actual* production-shaped
      database, not just the dev one — **done against dev only** (see
      `disaster-recovery.md`); re-verify against staging with production
      -scale data before go-live.
- [ ] Load test run against a provisioned (not local) environment with
      realistic network latency — **done locally only** (see
      `testing-strategy.md`); the numbers there are a smoke-level
      baseline, not a capacity plan.
- [ ] Runbooks reviewed by whoever's actually on call — not just written.
- [ ] Staff accounts provisioned for real users (not the seeded demo
      `ciso@example.com`/etc.) via `app/seed/seed_users.py`'s pattern or a
      real admin UI (doesn't exist yet — see `admin-guide.md`).
- [ ] Training sessions delivered (`docs/training/`) to compliance,
      procurement, IT/security, and leadership.
- [ ] Status-page / incident-communication channel set up.

## Launch day

- [ ] Deploy via the CD pipeline's staging → smoke test → production
      -approval → blue-green sequence (`.github/workflows/cd.yml`) — not
      a manual `kubectl apply` under time pressure.
- [ ] `/health/ready` green on every replica before flipping traffic.
- [ ] Confirm `/metrics` is actually being scraped by whatever's running
      Prometheus/CloudWatch — a dashboard with no data flowing in is
      worse than no dashboard, because it looks like everything's fine.
- [ ] First real vendor onboarded end-to-end (assign → assessment →
      submit) as a live smoke test, not just synthetic traffic.
- [ ] On-call team watching `/admin/monitoring` and `/admin/board` for
      the first few hours.

## Week 1

- [ ] Daily check: any findings/alerts that look like false positives at
      scale (the mock-provider determinism that worked for a single demo
      vendor needs revisiting once `*_PROVIDER=live` is flipped for real
      external data).
- [ ] Confirm Airflow DAGs (once actually deployed — see
      `backend/airflow_dags/README.md`) are running on schedule, not just
      present in the `dags_folder`.
- [ ] Rate-limit tuning: real usage patterns vs. the default 120/min (see
      Runbook 8) — adjust `RATE_LIMIT_REQUESTS_PER_MINUTE` based on actual
      traffic, not the guess this was shipped with.

## Month 1

- [ ] First monthly backup-restore drill against production-scale data
      (per the spec's own "test restores monthly" — a one-time test
      during development doesn't satisfy an ongoing operational practice).
- [ ] Review `security-hardening.md`'s deferred items — is the RBAC
      retrofit's scope (one endpoint) still acceptable at this point, or
      has real usage revealed which other endpoints most need it?
- [ ] Coverage/test-suite health check — has coverage moved from the 77%
      baseline, in which direction?
