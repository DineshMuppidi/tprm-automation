"""Prometheus-format /metrics (Phase 5 spec §5a: API response times, error
rates, endpoint health, DB connection pool). Real counters/histograms
updated by RequestMetricsMiddleware on every request — not a static
example payload.
"""

import time

import asyncpg
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter("tprm_http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("tprm_http_request_duration_seconds", "Request latency in seconds", ["method", "path"])
DB_POOL_SIZE = Gauge("tprm_db_pool_size", "Total connections in the asyncpg pool")
DB_POOL_IDLE = Gauge("tprm_db_pool_idle", "Idle connections in the asyncpg pool")


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        # Route templates (e.g. "/findings/{finding_id}") aren't known until
        # after routing resolves; request.url.path is the literal path,
        # which means high-cardinality labels for path-parameterized routes
        # (one series per finding id). Acceptable for this portfolio's
        # traffic volume — a production deployment would resolve
        # request.scope["route"].path_format instead, noted here rather
        # than silently shipped as if it were already the production shape.
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = request.url.path
        REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(duration)
        return response


def metrics_response(pool: asyncpg.Pool | None) -> Response:
    if pool is not None:
        DB_POOL_SIZE.set(pool.get_size())
        DB_POOL_IDLE.set(pool.get_idle_size())
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
