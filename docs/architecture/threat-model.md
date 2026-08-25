# Threat Model & Security Considerations

Phase 0 deliverable.

## 1. Who has access to vendor data?

Role-based access control, enforced at the API layer (every endpoint checks
`role` from the authenticated session, not just the UI hiding buttons):

| Role | Access |
|---|---|
| `admin` | Full system access, user management. No standing access to raw evidence files — must justify access, which is logged. |
| `ciso` | All vendors, all findings/alerts, cannot edit questionnaire templates |
| `compliance_officer` | Assigned vendors' assessments, findings, evidence; can close findings |
| `category_manager` | Read vendor risk scores + contract status for their category; cannot see raw questionnaire answers |
| `vendor_manager` | Procurement-side: contract terms, renewal dates, vendor performance KPIs; not security evidence detail |
| `legal` | Contracts, breach-related findings, exception approvals |
| `read_only` | Dashboards and reports only, no PII/evidence detail |
| vendor contact (external) | Only their own vendor's assessments/findings — see §4 |

Every role is least-privilege by default; broader access is an explicit
grant, not a fallback.

## 2. Data encryption

- **At rest:** AES-256 via AWS KMS for RDS (PostgreSQL) and S3 (contracts,
  certs, evidence uploads). Each S3 object uses SSE-KMS with a
  customer-managed key so key rotation and access are independently
  auditable from bucket policy.
- **In transit:** TLS 1.3 for every API call — vendor portal, internal
  service-to-service, and outbound calls to third-party integrations.
  No plaintext HTTP path exists, including health-check endpoints.
- **In processing:** LLM calls to Claude API send only what's needed for
  the specific analysis (a single response's text, not a full vendor
  dossier) — this limits blast radius if a prompt/response were ever
  logged upstream, and keeps token cost down as a side effect.

## 3. Audit logging

Every read *and* write of vendor assessment data, evidence, findings, and
contracts is logged to `audit_logs` (see schema) — actor, action, entity,
before/after state, timestamp, source IP. The table is append-only: `UPDATE`
and `DELETE` are rejected by a trigger (verified in Phase 0 — see schema
comments), not just by convention or application-layer discipline. This
matters specifically because the audit log's value to a regulator is that
*we couldn't have edited it after the fact even if we wanted to*.

Read-access logging (not just writes) is required for one reason: if a
vendor later disputes "who saw our unredacted pen-test report," the answer
has to come from the log, not from asking around.

## 4. Vendor data privacy — can vendors see other vendors' data?

No. Vendor portal sessions are scoped by `vendor_contacts.vendor_id` at the
query layer (every vendor-portal query includes a `WHERE vendor_id = :session_vendor_id`
predicate enforced by a shared query-builder helper, not left to each
endpoint to remember). This is the single most consequential access-control
bug this kind of platform can have — a leak here means Vendor A reads
Vendor B's security posture, which is both a breach and a trust-destroying
event for the whole platform. It gets its own integration test suite
(Phase 5) that specifically tries cross-vendor access and asserts 403/404
for every endpoint the vendor portal exposes, not just the ones we remember
to test manually.

## 5. API security

- OAuth 2.0 for internal staff SSO; scoped API keys for vendor-portal
  sessions (short-lived JWT, refreshed, tied to a single vendor contact).
- Rate limiting per authenticated principal (100 req/min default; tighter
  on password-reset / OTP-request endpoints specifically, since those are
  the ones worth abusing).
- WAF + Shield in front of the ALB for DDoS/OWASP-pattern filtering before
  traffic reaches application code.
- CSRF tokens on all state-changing vendor-portal forms (session-based,
  since that surface is browser-driven).

## 6. Third-party API compromise

If a monitoring integration (HIBP, Shodan, NewsAPI, etc.) were compromised
or started returning malicious/poisoned data:

- **Containment by construction:** monitoring responses are parsed into a
  strict schema before touching the database (`monitoring_alerts.payload`
  is validated JSON, not raw response bodies) — a crafted response can't
  inject SQL, execute code, or corrupt unrelated rows.
- **No autonomous state changes:** a monitoring source can create an
  *alert*. It cannot directly close a finding, change a vendor's risk
  score, alter a contract, or suspend a vendor — those all require the
  alert to flow through the same human-reviewable finding/playbook
  pipeline used everywhere else. This is a deliberate design constraint,
  not just a permissions default: it bounds the damage a single compromised
  integration can do to "created some noisy alerts we can dismiss," not
  "silently altered our vendor risk register."
- **Credential blast radius:** each source's API key is scoped to only
  that source's needs (e.g., HIBP key can only query HIBP) and stored
  separately in Secrets Manager, so a leaked key doesn't cascade into
  other integrations.

## 7. Threats considered out of scope for this build (documented, not solved)

- Nation-state-level compromise of the LLM provider itself — mitigated by
  data-minimization (§2) but not fully solvable at this layer; noted for
  the reader rather than hand-waved.
- Physical security of on-prem deployment (the "Kali Linux VM" deployment
  target) — assumed to inherit whatever physical/host controls the
  deploying org already has; this platform's threat model starts at the
  network boundary.
