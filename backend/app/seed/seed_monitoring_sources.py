import asyncpg

SOURCES = [
    ("cert_registry", "SOC 2 / ISO 27001 Certification Registries"),
    ("breach_vuln", "Breach & Vulnerability Feeds (HIBP, NVD, GitHub Advisory)"),
    ("news", "News & Reputation Monitoring"),
    ("financial", "Financial Distress Signals (SEC EDGAR, credit ratings)"),
]


async def seed_monitoring_sources(conn: asyncpg.Connection) -> None:
    for code, name in SOURCES:
        await conn.execute(
            """
            INSERT INTO monitoring_sources (code, name) VALUES ($1, $2)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            """,
            code, name,
        )
