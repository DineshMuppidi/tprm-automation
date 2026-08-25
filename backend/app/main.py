import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import close_pool, connect_pool
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.observability import RequestMetricsMiddleware, metrics_response
from app.routers import (
    admin, assessments, auth, contracts, findings, frameworks, monitoring, playbooks, reporting, staff_auth,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await connect_pool()
    yield
    await close_pool()


app = FastAPI(
    title="TPRM Automation Platform — API",
    description="Vendor assessment, continuous monitoring, remediation workflow, and advanced compliance features.",
    version="0.5.0",
    lifespan=lifespan,
)

settings = get_settings()

# Middleware stack (Starlette wraps in reverse-add order — CORS added last
# so it's outermost and handles preflight before rate limiting/headers).
app.add_middleware(RequestMetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_requests_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(staff_auth.router)
app.include_router(assessments.router)
app.include_router(admin.router)
app.include_router(monitoring.router)
app.include_router(findings.router)
app.include_router(findings.admin_router)
app.include_router(reporting.router)
app.include_router(contracts.router)
app.include_router(frameworks.router)
app.include_router(playbooks.router)


@app.get("/health")
async def health():
    """Kept for backward compatibility with the Phase 0-4 healthcheck
    convention; /health/live and /health/ready below are the K8s-style
    pair the Phase 0 architecture doc's deployment story actually needs."""
    return {"status": "ok"}


@app.get("/health/live")
async def health_live():
    """Liveness: is the process itself responsive? No dependency checks —
    a DB outage should not make an orchestrator kill and restart healthy
    app instances that can't fix a DB outage anyway."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request):
    """Readiness: can this instance actually serve traffic right now?
    Real DB connectivity check, not a static 200 — matches Runbook 1
    (System Down) in docs/operations/runbooks/."""
    try:
        pool = request.app.state.db_pool
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as e:  # noqa: BLE001 — reported in the response, not swallowed
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": str(e)})
    return {"status": "ready"}


@app.get("/metrics")
async def metrics(request: Request):
    return metrics_response(getattr(request.app.state, "db_pool", None))
