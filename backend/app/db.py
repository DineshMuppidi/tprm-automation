import json

import asyncpg
from fastapi import Request

from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    # asyncpg has no built-in Python dict <-> jsonb conversion; every table
    # with a JSONB column (questions.options, assessment_responses.extracted_claims,
    # monitoring_alerts.payload, ...) needs this codec on every pooled connection.
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text",
    )


async def connect_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url, min_size=1, max_size=10, init=_init_connection,
        )
    return _pool


async def connect_single() -> asyncpg.Connection:
    """A single connection with the same JSONB codec as the pool — used by
    one-off scripts (init_db.py, seed scripts) that don't need a pool."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    await _init_connection(conn)
    return conn


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_db(request: Request) -> asyncpg.Pool:
    """FastAPI dependency yielding the shared connection pool.

    Handlers acquire their own connection (`async with pool.acquire() as conn`)
    rather than us doing it here, so a handler that needs a transaction across
    several statements can control that explicitly.
    """
    return request.app.state.db_pool
