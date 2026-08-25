"""Seed data for compliance frameworks, controls, and cross-framework
mappings (Phase 0 §2 "compliance framework mappings", exercised for real
starting in Phase 1's questionnaire templates and fully leveraged by
Phase 4's control-mapping engine).

This is a representative subset of each framework — enough to demonstrate
real cross-framework mapping (e.g. "what covers encryption in transit?")
and to back the seeded questionnaire templates — not the full control
catalog. The schema has no ceiling on control count; loading the complete
NIST SP 800-53 / ISO 27001 Annex A catalog is a data-completeness task for
whenever this goes past portfolio scope, not a schema or code change.
"""

import asyncpg

FRAMEWORKS = [
    ("NIST_CSF_2", "NIST Cybersecurity Framework", "2.0", "Govern/Protect/Detect/Respond/Recover functions"),
    ("SOC2", "SOC 2 Trust Services Criteria", "2017 (2022 revision)", "AICPA Trust Services Criteria"),
    ("ISO27001", "ISO/IEC 27001", "2022", "Information security management, Annex A controls"),
    ("HIPAA", "HIPAA Security Rule", "45 CFR 164 Subpart C", "US healthcare data protection requirements"),
]

# (framework_code, control_ref, title, category)
CONTROLS = [
    ("NIST_CSF_2", "GV.OC-1", "Organizational cybersecurity governance is established", "Govern"),
    ("NIST_CSF_2", "ID.RA-1", "Asset vulnerabilities are identified and documented", "Identify"),
    ("NIST_CSF_2", "PR.AC-1", "Identities and credentials are managed for authorized devices/users", "Protect"),
    ("NIST_CSF_2", "PR.AT-1", "Personnel are provided cybersecurity awareness training", "Protect"),
    ("NIST_CSF_2", "PR.DS-1", "Data-at-rest is protected", "Protect"),
    ("NIST_CSF_2", "PR.DS-2", "Data-in-transit is protected", "Protect"),
    ("NIST_CSF_2", "PR.DS-3", "Assets are formally managed throughout removal, transfer, and disposal", "Protect"),
    ("NIST_CSF_2", "PR.IP-4", "Backups are conducted, maintained, and tested", "Protect"),
    ("NIST_CSF_2", "PR.IP-9", "Incident response and business continuity plans are in place and managed", "Protect"),
    ("NIST_CSF_2", "DE.CM-1", "Networks and systems are monitored to detect potential cybersecurity events", "Detect"),
    ("NIST_CSF_2", "RS.CO-2", "Incidents are reported consistent with established notification criteria", "Respond"),

    ("SOC2", "CC1.1", "The entity demonstrates a commitment to integrity and governance", "Control Environment"),
    ("SOC2", "CC6.1", "Logical access security measures restrict access to authorized users", "Logical Access"),
    ("SOC2", "CC6.6", "The entity implements encryption to protect data", "Logical Access"),
    ("SOC2", "CC6.8", "The entity manages malware and unauthorized software risk", "Logical Access"),
    ("SOC2", "CC7.2", "The entity monitors systems to detect anomalies and security events", "System Operations"),
    ("SOC2", "CC7.3", "The entity responds to identified security incidents", "System Operations"),
    ("SOC2", "CC9.2", "The entity manages risk from vendors and business partners", "Risk Mitigation"),

    ("ISO27001", "A.7.2", "Personnel receive appropriate security awareness education and training", "Human Resource Security"),
    ("ISO27001", "A.9.2", "User access is provisioned, reviewed, and revoked formally", "Access Control"),
    ("ISO27001", "A.10.1", "Cryptographic controls protect confidentiality and integrity of data", "Cryptography"),
    ("ISO27001", "A.12.3", "Backup copies are taken and tested regularly", "Operations Security"),
    ("ISO27001", "A.12.4", "Event logs are produced, kept, and regularly reviewed", "Operations Security"),
    ("ISO27001", "A.15.1", "Information security requirements for supplier relationships are agreed and documented", "Supplier Relationships"),
    ("ISO27001", "A.16.1", "Incidents are managed via a consistent, documented process", "Incident Management"),

    ("HIPAA", "164.308(a)(1)(ii)(A)", "Risk analysis", "Administrative Safeguards"),
    ("HIPAA", "164.308(a)(6)", "Security incident procedures", "Administrative Safeguards"),
    ("HIPAA", "164.308(a)(7)", "Contingency plan (backup, disaster recovery, emergency mode)", "Administrative Safeguards"),
    ("HIPAA", "164.312(a)(1)", "Access control", "Technical Safeguards"),
    ("HIPAA", "164.312(e)(1)", "Transmission security", "Technical Safeguards"),
]

# (framework_a_code, control_a_ref, framework_b_code, control_b_ref, confidence, rationale)
CONTROL_MAPPINGS = [
    ("NIST_CSF_2", "PR.AC-1", "SOC2", "CC6.1", 0.90, "Both restrict logical access to authorized identities"),
    ("NIST_CSF_2", "PR.AC-1", "ISO27001", "A.9.2", 0.90, "Both govern provisioning/review/revocation of user access"),
    ("NIST_CSF_2", "PR.AC-1", "HIPAA", "164.312(a)(1)", 0.85, "Both require technical access controls tied to identity"),

    ("NIST_CSF_2", "PR.DS-2", "SOC2", "CC6.6", 0.85, "Encryption in transit is the shared control objective"),
    ("NIST_CSF_2", "PR.DS-2", "ISO27001", "A.10.1", 0.85, "Cryptographic controls cover data in transit"),
    ("NIST_CSF_2", "PR.DS-2", "HIPAA", "164.312(e)(1)", 0.85, "Transmission security maps directly to data-in-transit protection"),

    ("NIST_CSF_2", "PR.DS-1", "SOC2", "CC6.6", 0.75, "Same SOC 2 criterion covers at-rest and in-transit encryption"),
    ("NIST_CSF_2", "PR.DS-1", "ISO27001", "A.10.1", 0.75, "Cryptographic controls cover data at rest"),

    ("NIST_CSF_2", "DE.CM-1", "SOC2", "CC7.2", 0.85, "Both require continuous monitoring for security events"),
    ("NIST_CSF_2", "DE.CM-1", "ISO27001", "A.12.4", 0.80, "Event logging/review satisfies continuous detection intent"),

    ("NIST_CSF_2", "PR.IP-9", "SOC2", "CC7.3", 0.85, "Incident response process is the shared requirement"),
    ("NIST_CSF_2", "PR.IP-9", "ISO27001", "A.16.1", 0.85, "Documented incident management process"),
    ("NIST_CSF_2", "PR.IP-9", "HIPAA", "164.308(a)(6)", 0.80, "Security incident procedures overlap with IR planning"),

    ("NIST_CSF_2", "PR.IP-4", "ISO27001", "A.12.3", 0.85, "Backup testing is the shared requirement"),
    ("NIST_CSF_2", "PR.IP-4", "HIPAA", "164.308(a)(7)", 0.75, "Contingency plan requires tested backups"),

    ("NIST_CSF_2", "PR.AT-1", "ISO27001", "A.7.2", 0.80, "Security awareness training for personnel"),
    ("SOC2", "CC9.2", "ISO27001", "A.15.1", 0.85, "Vendor/supplier risk management is the shared control objective"),
    ("NIST_CSF_2", "GV.OC-1", "SOC2", "CC1.1", 0.80, "Governance/control-environment commitment"),
]


async def seed_frameworks(conn: asyncpg.Connection) -> dict[tuple[str, str], str]:
    """Idempotently seeds frameworks/controls/mappings. Returns a lookup
    dict {(framework_code, control_ref): control_id} for template seeding."""

    framework_ids: dict[str, str] = {}
    for code, name, version, description in FRAMEWORKS:
        row = await conn.fetchrow(
            """
            INSERT INTO frameworks (code, name, version, description)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            code, name, version, description,
        )
        framework_ids[code] = row["id"]

    control_ids: dict[tuple[str, str], str] = {}
    for fw_code, ref, title, category in CONTROLS:
        row = await conn.fetchrow(
            """
            INSERT INTO controls (framework_id, control_ref, title, category)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (framework_id, control_ref) DO UPDATE SET title = EXCLUDED.title
            RETURNING id
            """,
            framework_ids[fw_code], ref, title, category,
        )
        control_ids[(fw_code, ref)] = row["id"]

    for fw_a, ref_a, fw_b, ref_b, confidence, rationale in CONTROL_MAPPINGS:
        a_id, b_id = control_ids[(fw_a, ref_a)], control_ids[(fw_b, ref_b)]
        # control_mappings has a CHECK(control_a_id <> control_b_id) and a
        # UNIQUE(control_a_id, control_b_id) — order deterministically so
        # re-seeding never tries to insert the reverse pair as a "new" row.
        lo, hi = sorted([a_id, b_id])
        await conn.execute(
            """
            INSERT INTO control_mappings (control_a_id, control_b_id, confidence, rationale)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (control_a_id, control_b_id) DO NOTHING
            """,
            lo, hi, confidence, rationale,
        )

    return control_ids
