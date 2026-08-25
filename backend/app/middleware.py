"""Phase 5 security hardening: HTTP security headers and rate limiting.
Real, tested middleware — not aspirational config that only exists in a
doc. See docs/operations/security-hardening.md for what this covers and
what it deliberately doesn't (e.g. CSRF tokens: not needed for a
bearer-token JSON API with no cookie-based session — documented there,
not silently skipped).
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_EXEMPT_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS only means something once TLS is actually terminated in
        # front of this service (Phase 0 architecture: ALB behind WAF) —
        # harmless to send locally over HTTP, meaningful in production.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket per client, in-memory, evaluated per request.

    Documented limitation: in-memory means per-process. Phase 0's
    architecture scales the API tier horizontally, and a limit tracked in
    each process's own memory is only a real *global* limit on a single
    instance — a multi-instance deployment needs a shared store (Redis,
    already in the Phase 0 architecture for queueing) for this to hold
    across instances. That's a real gap for the scaled case, documented in
    security-hardening.md rather than silently assumed away.
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self._limit = requests_per_minute
        self._buckets: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_key = (
            request.headers.get("authorization")
            or request.headers.get("x-admin-key")
            or (request.client.host if request.client else "unknown")
        )
        now = time.monotonic()
        bucket = self._buckets[client_key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self._limit:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again shortly."})
        bucket.append(now)
        return await call_next(request)
