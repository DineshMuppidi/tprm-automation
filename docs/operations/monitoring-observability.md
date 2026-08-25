# Monitoring & Observability

Phase 5 deliverable. What `/metrics` actually exposes (Prometheus format,
`app/observability.py`) and what a real dashboard/alerting setup should
watch — not a generic "monitor CPU and memory" list.

## What's real today

`GET /metrics` (unauthenticated on purpose — same convention as `/health*`,
scrapers shouldn't need a credential to reach it, and it exposes no
sensitive data):

```
tprm_http_requests_total{method, path, status}       # Counter
tprm_http_request_duration_seconds{method, path}      # Histogram
tprm_db_pool_size                                      # Gauge
tprm_db_pool_idle                                      # Gauge
```

Verified live: `curl /metrics` after a few requests shows real,
non-placeholder values — see `test_metrics_endpoint_returns_prometheus_format`.

Known limitation, documented in `observability.py`'s middleware docstring:
`path` labels use the literal request path, not the route template — a
request to `/findings/{some-uuid}` produces a distinct metric series per
finding ID rather than one `/findings/{id}` series. Fine at this
project's traffic volume; a real production deployment should switch to
`request.scope["route"].path_format` to avoid unbounded label cardinality.

## What a real dashboard should show (Phase 5 spec §5)

### Application health
- **API p50/p95/p99 latency** — from `tprm_http_request_duration_seconds`.
  Alert threshold: p95 > 5s (spec's own target).
- **Error rate** — `rate(tprm_http_requests_total{status=~"5.."}[5m]) /
  rate(tprm_http_requests_total[5m])`. Alert: > 1%.
- **`/health/ready` failures** — should be zero; any failure means the DB
  connectivity check is failing (Runbook 1).
- **DB pool saturation** — `tprm_db_pool_idle == 0` sustained for more
  than a minute or two is the leading indicator for Runbook 4
  (performance degradation) before latency even visibly degrades.

### Business metrics
*(Not yet exported as Prometheus metrics — these live in the app's own
reporting endpoints today, not a metrics scrape. Listed here as what a
`business_metrics_exporter` would need to expose if this became a
standalone concern.)*
- Assessments completed / findings closed per week — `GET
  /admin/reporting/kpis`'s `remediation_velocity`.
- Alert volume by type/severity — `GET /admin/monitoring/status`'s `stats`.
- Vendor portal logins — not currently tracked as a distinct metric (the
  magic-link verify endpoint doesn't emit one); a real gap.

### Security metrics
- **429 rate** (`tprm_http_requests_total{status="429"}`) — a sustained
  spike from one client key is either abuse or Runbook 8's "legitimate
  traffic hit the limit" scenario; distinguishing them needs looking at
  *which* client key, not just the count.
- **Failed staff/vendor auth attempts** — not currently counted as a
  distinct metric; `require_staff_session`/`require_vendor_session`
  raising 401 shows up in the generic `tprm_http_requests_total{status=
  "401"}` bucket today, not broken out separately. A real SOC would want
  this split out and correlated by source IP.
- **RBAC denials** — `tprm_http_requests_total{status="403"}` on
  `/admin/exceptions/*/approve` specifically, once the RBAC retrofit
  (`security-hardening.md`) extends past that one endpoint.

### Infrastructure metrics
Standard CloudWatch/node-exporter territory (CPU, memory, disk, network) —
not application-specific, not detailed here; `terraform/main.tf`'s
`aws_cloudwatch_log_group` is where backend logs land for a real
deployment, and CloudWatch Container Insights (or the equivalent for
whatever's running the containers) covers infra-level metrics without the
app needing to export them itself.

## Alerting thresholds (starting point, not tuned against real traffic)

| Metric | Warning | Critical |
|---|---|---|
| API p95 latency | > 2s | > 5s |
| Error rate (5xx) | > 0.5% | > 1% |
| `/health/ready` failures | any, for > 1 min | any, for > 5 min |
| DB pool idle | 0 for > 2 min | 0 for > 10 min |
| 429 rate | > 5% of requests | > 20% of requests |

These are reasonable starting points, explicitly not validated against
real production traffic patterns (there is none) — the honest position is
"tune these after the first month of real usage," not "these are correct."
