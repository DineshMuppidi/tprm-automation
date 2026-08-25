"""One-shot setup: applies schema.sql, then seeds frameworks/controls/
mappings and questionnaire templates. Safe to re-run — schema DDL uses
CREATE TYPE/TABLE without IF NOT EXISTS (so re-running against an already
-initialized database will error on the DDL step; drop and recreate the
database first if you need a clean slate) but every seed insert is
idempotent (ON CONFLICT DO NOTHING/UPDATE, or check-then-insert).

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
from app.seed.seed_templates import seed_templates  # noqa: E402

SCHEMA_PATH = Path(__file__).parent / "schema" / "schema.sql"


async def schema_already_applied(conn) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'vendors'"
    )
    return row is not None


async def main() -> None:
    conn = await connect_single()
    try:
        if await schema_already_applied(conn):
            print("Schema already applied — skipping DDL, running seed only.")
        else:
            print(f"Applying {SCHEMA_PATH} ...")
            await conn.execute(SCHEMA_PATH.read_text())
            print("Schema applied.")

        print("Seeding frameworks/controls/mappings ...")
        control_ids = await seed_frameworks(conn)
        print(f"  {len(control_ids)} controls seeded.")

        print("Seeding questionnaire templates ...")
        await seed_templates(conn, control_ids)
        print("  Done.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
