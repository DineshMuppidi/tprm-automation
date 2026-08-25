import httpx
import pytest_asyncio

from app.db import close_pool, connect_pool
from app.main import app


@pytest_asyncio.fixture
async def pool():
    """Connects to whatever DATABASE_URL points at (see .env / README) —
    schema + seed data must already be applied via db/init_db.py. Bypasses
    FastAPI's lifespan (no server process involved) by wiring the pool
    directly onto app.state, same as the lifespan handler would.

    Function-scoped deliberately: pytest-asyncio (in its default,
    non-session-scoped-loop config) gives each test function its own event
    loop, and an asyncpg pool can't be reused across loops — a
    session-scoped pool here would intermittently fail with "Future
    attached to a different loop".
    """
    p = await connect_pool()
    app.state.db_pool = p
    yield p
    await close_pool()


@pytest_asyncio.fixture
async def client(pool):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
