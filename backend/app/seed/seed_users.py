"""Seeds a minimal internal staff directory so Phase 2 alert routing has
real recipients. Phase 1 only needed vendor_contacts (external); Phase 2's
alert engine routes to internal roles (CISO, Compliance Officer, Category
Manager, Legal) per the spec's alert-routing table — this is that
directory's first real use. Real SSO/user-provisioning is still Phase 5's
job (see the security.py docstring); these are fixed demo accounts.
"""

import asyncpg

USERS = [
    ("ciso@example.com", "Jamie CISO", "ciso"),
    ("compliance@example.com", "Riley Compliance-Officer", "compliance_officer"),
    ("category-manager@example.com", "Morgan Category-Manager", "category_manager"),
    ("legal@example.com", "Avery Legal-Counsel", "legal"),
]


async def seed_internal_users(conn: asyncpg.Connection) -> None:
    for email, full_name, role in USERS:
        await conn.execute(
            """
            INSERT INTO users (email, full_name, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name, role = EXCLUDED.role
            """,
            email, full_name, role,
        )
