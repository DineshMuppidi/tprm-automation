import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool, connect_pool
from app.routers import admin, assessments, auth

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await connect_pool()
    yield
    await close_pool()


app = FastAPI(
    title="TPRM Automation Platform — API",
    description="Phase 1: Vendor Assessment Engine",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assessments.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
