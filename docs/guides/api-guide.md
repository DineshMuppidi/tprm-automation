# API Guide

The backend is a FastAPI service — the full, always-current, interactive
reference is auto-generated and lives at `/docs` (Swagger UI) or `/redoc`
on any running instance, and the raw OpenAPI schema at `/openapi.json`.
This guide is the "how do the pieces fit together" companion to that
reference, not a duplicate of it — endpoint-by-endpoint details belong in
`/docs`, where they can't drift out of sync with the actual code.

## Authentication

Three schemes, used by different callers:

| Scheme | Header | Who | Issued by |
|---|---|---|---|
| Vendor session | `Authorization: Bearer <jwt>` | Vendor contacts | `POST /auth/verify` (after `POST /auth/request-link`) |
| Staff session | `Authorization: Bearer <jwt>` | Internal staff (role-gated) | `POST /staff/auth/verify` (after `POST /staff/auth/request-link`) |
| Admin key | `X-Admin-Key: <key>` | Internal tooling / most of `/admin/*` | Configured, not issued — see `admin-guide.md` |

Both magic-link flows follow the same shape: request a link (always
returns 202, enumeration-safe — the response doesn't reveal whether the
email matched an account), the link's token is a short-lived (15 min)
JWT, exchanging it via `/verify` issues the actual session token (4 hours
for vendors, 8 for staff).

Some endpoints (assessments, findings) accept **either** a vendor session
or the admin key — `AccessContext` in `app/security.py` unifies both, and
enforces that a vendor session only ever sees its own vendor's data (a
mismatched ID returns 404, not 403 — see `security-hardening.md` for why).

## Core flows, by example

**Complete an assessment** (as a vendor):
```
POST /auth/request-link          {"email": "you@vendor.com"}
POST /auth/verify                {"token": "<from email>"}  -> access_token
GET  /assessments/mine           (Bearer)
GET  /assessments/{id}           (Bearer) -> questions + current responses
PUT  /assessments/{id}/responses/{question_id}   {"raw_answer": "..."}
POST /assessments/{id}/submit    (Bearer) -> risk breakdown, auto-generates findings
GET  /assessments/{id}/report    (Bearer) -> PDF
```

**Work a finding** (as a vendor):
```
GET  /findings/mine
POST /findings/{id}/acknowledge
PUT  /findings/{id}/plan         {"plan_text": "..."}
POST /findings/{id}/evidence     (multipart file upload)
POST /findings/{id}/submit       -> closed or rejected, with a reason
```

**Run monitoring checks manually** (admin key — what the Airflow DAGs
would trigger on a schedule):
```
POST /admin/monitoring/run-checks
```

**Upload and check a contract** (admin key):
```
POST /admin/vendors/{vendor_id}/contracts   (multipart: file, contract_name, effective_date)
POST /admin/vendors/{vendor_id}/contracts/check-compliance
```

## Rate limits

120 requests/minute per client (by `Authorization`/`X-Admin-Key` header,
falling back to source IP) — see `app/middleware.py`. `/health*` and
`/metrics` are exempt. A `429` response means back off and retry after a
few seconds; there's no `Retry-After` header yet (a reasonable client-side
addition — noted, not built).

## Errors

Standard HTTP status codes; error bodies are `{"detail": "..."}` (FastAPI's
default) except validation errors, which follow Pydantic's more detailed
`{"detail": [{"loc": [...], "msg": "...", ...}]}` shape — check `/docs`
for the exact schema per endpoint (FastAPI generates this from the actual
Pydantic models, so it's always accurate).

## Versioning

There is no `/v1/` prefix or API versioning scheme yet — a single evolving
API surface, appropriate for a project still adding phases. Introducing
real versioning is a Phase 6+ concern if this platform ever needs to
support multiple frontend versions against different backend versions
simultaneously.
