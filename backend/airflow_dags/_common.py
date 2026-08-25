"""Shared glue between Airflow tasks and the framework-agnostic monitoring
service layer. See README.md in this directory for why these DAGs aren't
executed in the dev sandbox this project was built in."""

import asyncio
import sys
from pathlib import Path
from typing import Awaitable, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

import asyncpg  # noqa: E402

from app.db import close_pool, connect_pool  # noqa: E402


def run_monitoring_check(check_fn: Callable[[asyncpg.Pool], Awaitable[int | dict]], result_key: str = "alerts_created") -> dict:
    """Wraps a service-layer check function (int or dict result — the
    monitoring checks return a count, the finding escalation check returns
    a breakdown dict) as a plain dict under `result_key`, for the Airflow
    task to return as its XCom value."""
    async def _inner() -> dict:
        pool = await connect_pool()
        try:
            result = await check_fn(pool)
            return {result_key: result}
        finally:
            await close_pool()

    return asyncio.run(_inner())
