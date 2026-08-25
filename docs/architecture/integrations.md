# Integration Points

Phase 0 deliverable. Every external dependency the platform calls, what it's
for, how we authenticate, what happens when it's unavailable, and whether it
touches sensitive vendor data.

**Default posture for this build:** none of these require paid keys to run
the platform end-to-end. Each integration is implemented behind a
`MonitoringProvider` interface (Phase 2) with a `mock` adapter that returns
realistic canned data, and a `live` adapter that makes the real call. Swap
via `.env` (`HIBP_PROVIDER=mock|live`, etc.) per source. This keeps the repo
runnable by anyone cloning it, and keeps CI free.

| Source | Purpose | Auth | Rate limit | Fallback if unavailable | Cost | Touches sensitive vendor data? |
|---|---|---|---|---|---|---|
| **Claude API** (Anthropic) | Answer analysis, contradiction detection, evidence validation, risk narrative generation | API key (Secrets Manager) | Tier-based TPM/RPM; batch non-urgent analysis | Queue in Redis, retry w/ backoff; UI shows "analysis pending"; air-gapped mode falls back to local Llama 3.2 | Pay-per-token (dominant variable cost — batch where possible) | **Yes** — sees full vendor questionnaire responses and uploaded evidence text |
| **SOC 2 Trust Search Registry** (AICPA) / ISO 27001 national registries / FedRAMP.gov / PCI-DSS provider lists | Certification validity, expiry, scope | None (public search) — scraped, not an official API | Self-imposed: cache 24h, respect robots.txt, backoff on 429 | Fall back to vendor's self-submitted cert PDF; flag as "unverified — registry lookup failed" | Free | No — public registry data |
| **Have I Been Pwned** | Breach exposure by domain | API key | 10 req/min (Pwned 3 tier) | Skip this cycle, retry next scheduled run; source marked degraded on Monitoring Status Page | Paid (low, per-key subscription) | No — queries vendor's public domain only |
| **Shodan / Censys** | Exposed vendor infrastructure, cert transparency | API key | Plan-dependent (Shodan: 1 req/sec typical) | Same as above | Paid (freemium tier usable for demo) | No — public internet-facing data |
| **NVD API / GitHub Advisory / Rapid7** | CVEs in vendor products | NVD: API key (higher rate limit); GH Advisory: token | NVD: 50 req/30s with key | Same as above; CVE feed is the least time-sensitive of the monitoring set | Free (NVD, GH Advisory); Rapid7 paid | No |
| **NewsAPI / RSS / X (Twitter) API / Reddit** | Reputation, breach/lawsuit/bankruptcy mentions | API key per source | NewsAPI free tier: 100 req/day | Degrade gracefully — RSS has no rate limit and becomes primary source if paid APIs are capped | NewsAPI/X paid tiers optional; RSS free | Low — public news text, occasionally contains vendor employee names (PII-adjacent, handled per data-minimization policy) |
| **Dun & Bradstreet / Crunchbase / SEC EDGAR** | Financial distress signals | D&B: API key (paid); Crunchbase: API key; EDGAR: none | D&B/Crunchbase: plan-dependent | Weekly DAG, not hourly — a slow/failed run is tolerable; EDGAR (free, public companies only) used as baseline even without paid keys | D&B is the expensive one — real deployments budget for it; this build defaults to EDGAR + Crunchbase free tier + mock D&B | No — company-level financial data |
| **CISA / NIST alerts, FDA warnings, state AG breach settlements, GDPR/ICO decisions** | Regulatory events affecting vendor or its sector | None (public feeds/RSS) | None | RSS is inherently resilient; no fallback needed | Free | No |
| **Gmail API** | Parse inbound vendor breach-notification emails into structured alerts | OAuth 2.0, scoped to a dedicated intake mailbox — never the user's personal inbox | Gmail API default quotas | If unreachable, notifications queue in the mailbox and are picked up next poll — no data loss | Free | **Yes** — inbound email may contain incident detail; scoped OAuth + a dedicated service mailbox keeps this out of any individual's personal Gmail |

## Cross-cutting rules

- **Authentication.** All third-party keys live in AWS Secrets Manager
  (Phase 5), never in `.env` committed to git, never in application logs.
  Local/demo mode uses a `.env.example`-documented set of dummy values that
  only work with the `mock` provider.
- **Rate limiting is a citizen, not an afterthought.** Every live adapter
  wraps calls in a token-bucket limiter sized to the vendor's documented
  quota, so one runaway DAG can't get our API key banned mid-incident.
- **Third-party compromise.** If a monitoring API itself were compromised
  (e.g., a malicious response poisoning our alert pipeline), the blast
  radius is bounded by: (1) responses are schema-validated before being
  written to `monitoring_alerts`, never executed or templated into HTML
  unescaped; (2) alerts only ever *inform* — no monitoring source can
  directly change a vendor's status, contract, or risk score without
  passing through the same reviewed alert → finding pipeline as everything
  else. See `threat-model.md` for the full analysis.
