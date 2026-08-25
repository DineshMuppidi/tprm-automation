"""Creates one demo vendor + contact + assigned Tier 1 assessment, and
prints a ready-to-use magic-link login URL — for local/manual testing of
the vendor portal without going through the (not-yet-built) admin UI flow.

Usage:
    python backend/db/init_db.py        # once
    python backend/db/seed_demo_data.py [--email you@example.com]
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.db import connect_single  # noqa: E402
from app.security import create_magic_link_token  # noqa: E402


async def main(email: str) -> None:
    conn = await connect_single()
    settings = get_settings()
    try:
        bu = await conn.fetchrow(
            """
            INSERT INTO business_units (name, description) VALUES ('Human Resources', 'Demo business unit')
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
            """
        )

        vendor = await conn.fetchrow(
            """
            INSERT INTO vendors (legal_name, dba_name, primary_domain, industry, tier, status, data_access_level)
            VALUES ('Acme HR Solutions, Inc.', 'AcmeHR', 'acmehr-demo.example.com', 'HR SaaS',
                    'tier_1_critical', 'onboarding', 'restricted_pii')
            RETURNING id
            """
        )
        vendor_id = vendor["id"]

        await conn.execute(
            """
            INSERT INTO vendor_business_units (vendor_id, business_unit_id, affected_user_count, data_types)
            VALUES ($1, $2, 500, ARRAY['pii','payroll'])
            ON CONFLICT DO NOTHING
            """,
            vendor_id, bu["id"],
        )

        contact = await conn.fetchrow(
            """
            INSERT INTO vendor_contacts (vendor_id, full_name, email, role, is_primary)
            VALUES ($1, 'Jordan Vendor-Rep', $2, 'Security Lead', true)
            ON CONFLICT (vendor_id, email) DO UPDATE SET full_name = EXCLUDED.full_name
            RETURNING id
            """,
            vendor_id, email,
        )
        contact_id = contact["id"]

        template = await conn.fetchrow(
            "SELECT id, name FROM questionnaire_templates WHERE tier = 'tier_1_critical' LIMIT 1"
        )
        if template is None:
            raise SystemExit("No Tier 1 template found — run init_db.py first.")

        existing = await conn.fetchrow(
            "SELECT id FROM assessments WHERE vendor_id = $1 AND status != 'completed' LIMIT 1",
            vendor_id,
        )
        if existing:
            assessment_id = existing["id"]
            print(f"Reusing existing in-progress assessment {assessment_id}")
        else:
            due_at = datetime.now(timezone.utc) + timedelta(days=14)
            assessment = await conn.fetchrow(
                """
                INSERT INTO assessments (vendor_id, template_id, status, assigned_at, due_at)
                VALUES ($1, $2, 'assigned', now(), $3)
                RETURNING id
                """,
                vendor_id, template["id"], due_at,
            )
            assessment_id = assessment["id"]
            print(f"Created assessment {assessment_id} using template '{template['name']}'")

        token = create_magic_link_token(contact_id, email)
        login_url = f"{settings.app_base_url}/verify?token={token}"

        print("\n--- Demo vendor ready ---")
        print(f"Vendor:        Acme HR Solutions, Inc.  ({vendor_id})")
        print(f"Contact email: {email}")
        print(f"Assessment:    {assessment_id}")
        print(f"\nLogin URL (expires in {settings.magic_link_ttl_minutes} min):\n{login_url}\n")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="vendor-demo@example.com")
    args = parser.parse_args()
    asyncio.run(main(args.email))
