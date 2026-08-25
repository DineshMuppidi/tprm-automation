from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas.framework import ControlScorecardEntry, FrameworkCoverageOut, GapAnalysisOut, RelatedControlOut
from app.security import require_admin_key
from app.services.frameworks import coverage

router = APIRouter(prefix="/admin", tags=["frameworks"], dependencies=[Depends(require_admin_key)])


@router.get("/vendors/{vendor_id}/framework-coverage", response_model=dict[str, FrameworkCoverageOut])
async def vendor_framework_coverage(vendor_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        return await coverage.vendor_framework_coverage(conn, str(vendor_id))


@router.get("/vendors/{vendor_id}/framework-gap-analysis", response_model=GapAnalysisOut)
async def vendor_gap_analysis(vendor_id: UUID, target_framework: str, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        return await coverage.framework_gap_analysis(conn, str(vendor_id), target_framework)


@router.get("/controls/{control_id}/related", response_model=list[RelatedControlOut])
async def get_related_controls(control_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        return await coverage.related_controls(conn, str(control_id))


@router.get("/reporting/control-gaps", response_model=list[ControlScorecardEntry])
async def control_gap_scorecard(pool: asyncpg.Pool = Depends(get_db)):
    return await coverage.control_coverage_scorecard(pool)
