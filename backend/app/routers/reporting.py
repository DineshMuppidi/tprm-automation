import asyncpg
from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas.reporting import BoardSummary, KPIReport
from app.security import require_admin_key
from app.services.board_reporting import build_board_summary
from app.services.remediation.reporting import build_kpi_report

router = APIRouter(prefix="/admin/reporting", tags=["reporting"], dependencies=[Depends(require_admin_key)])


@router.get("/kpis", response_model=KPIReport)
async def kpis(pool: asyncpg.Pool = Depends(get_db)):
    return await build_kpi_report(pool)


@router.get("/board-summary", response_model=BoardSummary)
async def board_summary(pool: asyncpg.Pool = Depends(get_db)):
    return await build_board_summary(pool)
