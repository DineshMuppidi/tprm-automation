"""One-shot setup: applies schema.sql, then any not-yet-applied migrations
in db/migrations/ (in filename order), then seeds frameworks/controls/
mappings and questionnaire templates. Safe to re-run — schema.sql DDL uses
CREATE TYPE/TABLE without IF NOT EXISTS (so re-running against an already
-initialized database will error on that one step; drop and recreate the
database first if you need a clean slate), but every migration file is
itself idempotent (IF NOT EXISTS / ON CONFLICT), and schema_migrations
tracks which ones already ran so this script never re-applies one.

Usage:
    createdb tprm                     # first time only
    python backend/db/init_db.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from app.db import connect_single  # noqa: E402
from app.seed.seed_frameworks import seed_frameworks  # noqa: E402
from app.seed.seed_monitoring_sources import seed_monitoring_sources  # noqa: E402
from app.seed.seed_templates import seed_templates  # noqa: E402
from app.seed.seed_users import seed_internal_users  # noqa: E402

SCHEMA_PATH = Path(__file__).parent / "schema" / "schema.sql"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def schema_already_applied(conn) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'vendors'"
    )
    return row is not None


async def apply_migrations(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        print(f"Applying migration {path.name} ...")
        await conn.execute(path.read_text())
        await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", path.name)


async def main() -> None:
    conn = await connect_single()
    try:
        if await schema_already_applied(conn):
            print("Schema already applied — skipping DDL, running migrations + seed only.")
        else:
            print(f"Applying {SCHEMA_PATH} ...")
            await conn.execute(SCHEMA_PATH.read_text())
            print("Schema applied.")

        await apply_migrations(conn)

        print("Seeding frameworks/controls/mappings ...")
        control_ids = await seed_frameworks(conn)
        print(f"  {len(control_ids)} controls seeded.")

        print("Seeding questionnaire templates ...")
        await seed_templates(conn, control_ids)
        print("  Done.")

        print("Seeding monitoring sources ...")
        await seed_monitoring_sources(conn)

        print("Seeding internal staff directory ...")
        await seed_internal_users(conn)
        print("  Done.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
