from datetime import date
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.db import get_db
from app.schemas.contract import ComplianceCheckResult, ContractOut, ObligationOut
from app.security import require_admin_key
from app.services.contracts.contract_compliance import check_contract_compliance, generate_obligations
from app.services.contracts.contract_parser import get_contract_parser_provider
from app.services.contracts.pdf_text import extract_text
from app.services.storage import save_evidence_file

router = APIRouter(prefix="/admin", tags=["contracts"], dependencies=[Depends(require_admin_key)])


@router.post("/vendors/{vendor_id}/contracts", response_model=ContractOut, status_code=201)
async def upload_contract(
    vendor_id: UUID, file: UploadFile, contract_name: str = Form(...),
    effective_date: date = Form(...), expiration_date: date | None = Form(None),
    pool: asyncpg.Pool = Depends(get_db),
):
    content = await file.read()
    raw_text = extract_text(file.filename or "contract.txt", content)
    terms = await get_contract_parser_provider().extract_terms(raw_text)
    storage_uri = save_evidence_file(f"contract-{vendor_id}", file.filename or "contract", content)

    async with pool.acquire() as conn:
        vendor = await conn.fetchrow("SELECT id FROM vendors WHERE id = $1", vendor_id)
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        contract = await conn.fetchrow(
            """
            INSERT INTO contracts (vendor_id, contract_name, storage_uri, effective_date, expiration_date,
                                    auto_renews, renewal_notice_days, extracted_terms, parsed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
            RETURNING *
            """,
            vendor_id, contract_name, storage_uri, effective_date, expiration_date,
            terms.auto_renews, terms.renewal_notice_days, terms.to_dict(),
        )
        await generate_obligations(conn, str(contract["id"]), terms)

    return dict(contract)


@router.get("/vendors/{vendor_id}/contracts", response_model=list[ContractOut])
async def list_vendor_contracts(vendor_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM contracts WHERE vendor_id = $1 ORDER BY effective_date DESC", vendor_id)
    return [dict(r) for r in rows]


@router.get("/contracts/{contract_id}/obligations", response_model=list[ObligationOut])
async def list_obligations(contract_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM contract_obligations WHERE contract_id = $1", contract_id)
    return [dict(r) for r in rows]


@router.post("/vendors/{vendor_id}/contracts/check-compliance", response_model=list[ComplianceCheckResult])
async def check_compliance(vendor_id: UUID, pool: asyncpg.Pool = Depends(get_db)):
    async with pool.acquire() as conn:
        results = await check_contract_compliance(conn, str(vendor_id))
    return results
