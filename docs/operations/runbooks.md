# Operational Runbooks

Phase 5 deliverable. Ten scenarios, each tied to this system's actual
code/config — not generic "restart the server" filler. Every alert/symptom
line names the real signal (a log message, a metric, an endpoint) that
would actually fire.

---

## Runbook 1 — Database Unreachable

**Alert:** `/health/ready` returns 503 (`app/main.py`'s real `SELECT 1`
check, not a static 200). `tprm_db_pool_size` / `tprm_db_pool_idle` on
`/metrics` stop updating.

**Steps:**
1. Check RDS status in the AWS console / `aws rds describe-db-instances`.
2. If the instance is up but connections are refused: check
   `aws_security_group.rds` (terraform/main.tf) actually allows the app
   tier's security group — a security-group drift is the most common
   cause of "DB is up, app can't reach it."
3. If disk is full: `contract_obligations`/`monitoring_alerts`/`audit_logs`
   grow unboundedly without the retention job described in
   `docs/architecture/schema.sql`'s closing comment — check row counts
   there first before assuming it's evidence-file bloat (evidence lives in
   S3/local `storage/`, not the DB).
4. Restore from the latest automated RDS snapshot if data is corrupted —
   see `disaster-recovery.md` for the tested restore procedure.
5. Update the status page; the frontend's own error states (`ApiError` in
   `frontend/src/lib/api.ts`) surface a generic failure, not a helpful one
   — a status page is the only way affected users find out what's wrong.
6. Post-incident: was this caught by `/health/ready` before or after user
   reports? If after, the readiness probe's `initialDelaySeconds`/
   `periodSeconds` in `k8s/10-backend.yaml` may need tightening.

**Target RTO:** <15 minutes (matches `disaster-recovery.md`).

---

## Runbook 2 — High Alert Volume (Alert Fatigue)

**Alert:** `alerts_this_week` on `GET /admin/monitoring/status` spikes
well above its usual range, or the `/admin/monitoring` Alert Feed fills
with the same vendor repeatedly.

**Steps:**
1. Filter the Alert Feed by vendor (`GET /admin/monitoring/alerts?vendor_id=...`)
   — is this one vendor having a real, major incident, or a source
   misbehaving?
2. Check `alert_engine.py`'s dedup logic actually held — one open alert
   per (vendor, alert_type) should mean volume comes from *distinct*
   vendors/types, not the same one repeating. If the same vendor+type
   shows multiple `new` alerts, dedup itself may be broken — that's a
   code bug, not normal volume, and should be escalated as one.
3. If it's a real widespread event (e.g. a supply-chain CVE affecting many
   vendors' shared dependency): this is what the system is *for* — let it
   run, but consider a temporary suppression rule
   (`POST /admin/monitoring/alerts/{id}/suppress`) for confirmed
   duplicates/false positives, which expires in 90 days per
   `alert_suppression_default_days`.
4. If a source is clearly misbehaving (e.g. the mock provider's
   `_stable_fraction` logic — see `mock_providers.py` — somehow
   regressed to non-deterministic output): disable that source via
   `CERT_REGISTRY_PROVIDER`/`BREACH_PROVIDER`/etc. env vars, redeploy.

---

## Runbook 3 — Monitoring API Down (External Dependency Failure)

**Alert:** `last_error` populated on a row in `GET /admin/monitoring/status`'s
`sources` list (real, from `monitoring_service._touch_source`, not
synthetic).

**Steps:**
1. Identify which source (`cert_registry`, `breach_vuln`, `news`,
   `financial`) via the `sources[].code` field.
2. Check the named external API's own status page (NVD, HIBP, NewsAPI,
   etc. — see `docs/architecture/integrations.md` for which is live vs.
   mock in this deployment).
3. Verify the API key hasn't expired (`HIBP_API_KEY`/`NVD_API_KEY`/
   `NEWSAPI_API_KEY` in `.env` / the k8s Secret).
4. The other three sources are unaffected — each has its own DAG/task and
   its own `monitoring_sources` row (Phase 2 design: one source failing
   never blocks the others).
5. If the outage is prolonged, temporarily set that source's provider env
   var back to `mock` rather than leaving critical-vendor monitoring blind
   — a stale mock signal is a known, documented state; a silently-failing
   live check is not.
6. No data is lost — the DAG retries per its `default_args` (see
   `backend/airflow_dags/README.md`'s schedule table) and picks up on the
   next scheduled run.

---

## Runbook 4 — Performance Degradation (Slow Queries)

**Alert:** `tprm_http_request_duration_seconds` p95/p99 on `/metrics`
climbs; `scripts/load_test.py` against a representative endpoint shows
regression vs. the baseline numbers in `testing-strategy.md`.

**Steps:**
1. Check `EXPLAIN ANALYZE` on the slow query — the schema's indexes
   (`idx_findings_vendor_status`, `idx_alerts_detected`, etc. — see
   `backend/db/schema/schema.sql`) cover the query patterns the API
   actually uses (vendor-scoped lookups, status filters, date-sorted
   feeds); a slow query outside those patterns likely needs a new index,
   not just more CPU.
2. Check `tprm_db_pool_size`/`tprm_db_pool_idle` on `/metrics` — pool
   exhaustion (idle near 0 under load) means either genuinely more
   traffic than provisioned for, or a connection leak (a handler acquiring
   a connection without releasing it — review recent changes to any
   `async with pool.acquire()` block).
3. Re-run `scripts/load_test.py` against the suspect endpoint to get a
   current, real number rather than guessing.
4. Scale: `k8s/10-backend.yaml`'s HPA already scales on CPU 70% — if CPU
   isn't the bottleneck (i.e. it's DB-bound), scaling backend replicas
   won't help; scale/tune `terraform/main.tf`'s `db_instance_class`
   instead.

---

## Runbook 5 — Vendor Portal Access Issue

**Alert/ticket:** "Vendor X can't log in."

**Steps:**
1. Confirm the vendor is using the *email on file* —
   `vendor_contacts.email` (case-insensitive, `citext`) is the only
   lookup key; a typo'd email gets the enumeration-safe "if that email is
   registered..." response with no further signal.
2. Check the magic link hasn't expired — 15 minutes
   (`magic_link_ttl_minutes`), by design short-lived. A vendor reporting
   "the link doesn't work" an hour after requesting it is expected
   behavior, not a bug; have them request a new one.
3. Check spam/junk — `EMAIL_PROVIDER=console` in a misconfigured
   environment means the email was never actually sent, only logged
   server-side; confirm the deployment's `EMAIL_PROVIDER` is actually
   `smtp` in anything beyond local dev.
4. If multiple vendors report the same issue simultaneously: it's the
   platform, not them — check `EMAIL_PROVIDER`/SMTP credentials, and
   `AUTH_SECRET` hasn't rotated out from under active sessions (rotating
   it invalidates every outstanding session token immediately).

---

## Runbook 6 — LLM Provider Degraded or Unavailable

*(Platform-specific — not one of the spec's five examples, added because
every scoring/review feature in this platform depends on it.)*

**Alert:** Assessment submission / plan review / evidence validation
requests start failing or timing out; Anthropic's own status page shows
an incident.

**Steps:**
1. Every LLM-backed feature (Phase 1 answer analysis, Phase 3 plan/
   evidence review, Phase 4 contract parsing) already defaults to `mock`
   — if `LLM_PROVIDER=live` and Claude is degraded, flip it to `mock` via
   env var and redeploy. The platform keeps functioning with deterministic
   heuristic scoring instead of live LLM calls — this is exactly why the
   mock/live split exists, not just for offline development.
2. Assessments/findings submitted during the outage with `mock` active are
   still scored and usable; nothing is lost, the classification quality is
   just the heuristic's rather than Claude's for that window.
3. Once Claude recovers, flip back to `live`. No backfill/reprocessing is
   built — a documented gap, not silently assumed away (re-scoring
   historical responses would need a dedicated batch job that doesn't
   exist yet).

---

## Runbook 7 — Airflow DAG Failing

*(Platform-specific. Applies once Airflow is actually deployed — see
`backend/airflow_dags/README.md` for this build's "written, not run"
status.)*

**Steps:**
1. Every DAG task is a one-line wrapper around a plain async function in
   `app/services/monitoring/monitoring_service.py` or
   `app/services/remediation/escalation_engine.py` — reproduce the
   failure directly: `python -c "from app...monitoring_service import
   run_certification_check; ..."` rather than debugging through Airflow's
   UI first. If it fails the same way outside Airflow, it's an
   application bug; if it only fails inside Airflow, it's an
   orchestration/environment issue (missing `DATABASE_URL`, `backend/` not
   on `PYTHONPATH` — see that README's "Deploying for real" section).
2. Check the DAG's configured retry policy actually matches
   `backend/airflow_dags/README.md`'s schedule table — `hourly_breach_check`
   should retry aggressively (5x, 1 min backoff), the others more
   conservatively.
3. A stuck/failing DAG doesn't lose data — `monitoring_sources.last_error`
   surfaces the failure on `/admin/monitoring/status` (Runbook 3) even
   without touching Airflow's own UI.

---

## Runbook 8 — Rate Limit Blocking Legitimate Traffic

*(Platform-specific — Phase 5's rate limiter is new; a real failure mode
worth having a runbook for from day one.)*

**Alert:** Users report intermittent 429s; `/metrics`
`tprm_http_requests_total{status="429"}` is nonzero for real user traffic,
not a load test.

**Steps:**
1. Check `RATE_LIMIT_REQUESTS_PER_MINUTE` (default 120) against actual
   legitimate traffic patterns — a compliance officer's dashboard
   auto-refreshing multiple panels every few seconds can plausibly hit
   this on a busy `/admin/findings` session.
2. Remember the documented limitation in `app/middleware.py`: the limiter
   is in-memory, per-process. On a multi-replica deployment (`k8s/10-
   backend.yaml`'s `replicas: 2`+), the *effective* limit per client is
   actually `RATE_LIMIT_REQUESTS_PER_MINUTE × replica_count` if requests
   land on different pods, or as low as the configured value if they all
   land on one — inconsistent enough to be confusing when debugging.
   Moving to a shared Redis-backed limiter (already in the Phase 0
   architecture for queueing) is the real fix; noted, not yet built.
3. Short-term mitigation: raise `RATE_LIMIT_REQUESTS_PER_MINUTE` via the
   ConfigMap and redeploy — no code change needed.

---

## Runbook 9 — Evidence Storage Full or Unavailable

**Alert:** Evidence upload endpoints (`POST /assessments/{id}/responses/
{qid}/evidence`, `POST /findings/{id}/evidence`, contract upload) start
returning 500s.

**Steps:**
1. Local/single-VM deployment: check disk space where `STORAGE_ROOT`
   points (`storage.py`) — evidence files accumulate with no cleanup job.
2. S3-backed deployment (once `storage.py` is extended per its own
   `Path`-based interface — see that module's docstring): check the
   bucket's access policy and `aws_s3_bucket_public_access_block`
   (terraform/main.tf) haven't drifted to block the app's own writes.
3. This never corrupts existing data — a failed upload just means that
   one evidence file didn't save; the finding/assessment/contract row
   itself is unaffected and the vendor can retry.

---

## Runbook 10 — Suspicious Cross-Vendor Access Attempt

*(Security runbook — not one of the spec's five infra examples, but the
Phase 0 threat model calls vendor isolation the platform's single most
consequential access-control property, so it gets its own runbook.)*

**Alert:** A spike in 404s from `AccessContext.check_vendor` (a vendor
session probing IDs that resolve to *other* vendors' data — logged the
same as "not found," by design, so an attacker learns nothing from the
response, but the *rate* of 404s from one session is still a signal worth
watching for centrally).

**Steps:**
1. Correlate by `vendor_contact_id` (JWT `sub` claim) across requests —
   is one session hitting many different resource IDs in sequence
   (enumeration) vs. one-off typos/stale bookmarks (normal)?
2. If enumeration is confirmed: the session's JWT can't be revoked
   individually (stateless tokens, by design — see `security.py`) short of
   rotating `AUTH_SECRET`, which invalidates *every* active session,
   vendor and staff. Document this tradeoff before invoking it: it's the
   real fix, but it logs everyone out.
3. This is exactly the scenario `test_vendor_cannot_access_another_vendors_
   assessment`/`_finding` exist to prevent at the code level — if this
   runbook is ever needed for a *successful* cross-vendor read (not just
   attempted), that's a regression in `AccessContext.check_vendor` and
   should be treated as a P0 security incident, not a routine ticket.
