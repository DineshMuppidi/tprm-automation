from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas.playbook import PlaybookDefinitionOut, PlaybookExecutionOut
from app.security import require_admin_key

router = APIRouter(prefix="/admin/playbooks", tags=["playbooks"], dependencies=[Depends(require_admin_key)])


@router.get("/definitions", response_model=list[PlaybookDefinitionOut])
async def list_definitions(pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM playbook_definitions ORDER BY code")
    return [dict(r) for r in rows]


@router.get("/executions", response_model=list[PlaybookExecutionOut])
async def list_executions(vendor_id: UUID | None = None, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT pe.*, pd.code AS playbook_code, pd.name AS playbook_name, v.legal_name AS vendor_name
            FROM playbook_executions pe
            JOIN playbook_definitions pd ON pd.id = pe.playbook_id
            LEFT JOIN vendors v ON v.id = pe.vendor_id
            WHERE $1::uuid IS NULL OR pe.vendor_id = $1
            ORDER BY pe.started_at DESC LIMIT 100
            """,
            vendor_id,
        )
    return [dict(r) for r in rows]
