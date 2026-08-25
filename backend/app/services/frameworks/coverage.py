"""Control framework mapping & coverage (Phase 4 spec §2). Builds on the
`controls` / `control_mappings` catalog seeded in Phase 0 and each vendor's
assessment responses (Phase 1) — this is the first code that actually
*queries* that cross-framework graph, rather than just storing it.

Coverage semantics: a framework control counts as "covered" by a vendor if
either (a) a question in their latest completed assessment maps to it
directly and scored adequate/strong, or (b) it's mapped (via
`control_mappings`) to a control that was covered that way. This is what
lets a vendor's NIST-CSF-framed questionnaire answer produce a claim about
their likely SOC 2 / ISO 27001 / HIPAA coverage without a separate
questionnaire per framework — directly implementing the spec's own
example ("vendor covers 85% of NIST CSF, 78% of SOC 2...").
"""

import asyncpg

_COVERING_CLASSIFICATIONS = ("strong", "adequate")


async def _directly_covered_control_ids(conn: asyncpg.Connection, vendor_id: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT DISTINCT q.control_id
        FROM assessment_responses r
        JOIN questions q ON q.id = r.question_id
        JOIN assessments a ON a.id = r.assessment_id
        WHERE a.vendor_id = $1 AND a.status = 'completed' AND q.control_id IS NOT NULL
          AND r.classification = ANY($2::response_classification[])
          AND a.id = (SELECT id FROM assessments WHERE vendor_id = $1 AND status = 'completed' ORDER BY completed_at DESC LIMIT 1)
        """,
        vendor_id, list(_COVERING_CLASSIFICATIONS),
    )
    return {str(r["control_id"]) for r in rows if r["control_id"]}


async def _mapped_control_ids(conn: asyncpg.Connection, control_ids: set[str]) -> set[str]:
    if not control_ids:
        return set()
    rows = await conn.fetch(
        """
        SELECT control_a_id, control_b_id FROM control_mappings
        WHERE control_a_id = ANY($1::uuid[]) OR control_b_id = ANY($1::uuid[])
        """,
        list(control_ids),
    )
    mapped = set()
    for r in rows:
        a, b = str(r["control_a_id"]), str(r["control_b_id"])
        if a in control_ids:
            mapped.add(b)
        if b in control_ids:
            mapped.add(a)
    return mapped


async def vendor_framework_coverage(conn: asyncpg.Connection, vendor_id: str) -> dict:
    """Returns {framework_code: {covered, total, pct}} for every seeded framework."""
    direct = await _directly_covered_control_ids(conn, vendor_id)
    mapped = await _mapped_control_ids(conn, direct)
    covered_ids = direct | mapped

    frameworks = await conn.fetch("SELECT id, code FROM frameworks")
    result = {}
    for fw in frameworks:
        controls = await conn.fetch("SELECT id FROM controls WHERE framework_id = $1", fw["id"])
        total = len(controls)
        covered = sum(1 for c in controls if str(c["id"]) in covered_ids)
        result[fw["code"]] = {
            "covered": covered, "total": total,
            "pct": round(covered / total * 100, 1) if total else 0.0,
        }
    return result


async def framework_gap_analysis(conn: asyncpg.Connection, vendor_id: str, target_framework_code: str) -> dict:
    """Given a vendor's actual assessment coverage, which controls of
    `target_framework_code` are NOT covered (directly or via mapping)?
    Implements the spec's own scenario: vendor claims 'SOC 2 certified, so
    we're compliant' against a HIPAA-covered entity's actual requirement —
    this answers 'compliant with what, specifically, is still missing.'"""
    direct = await _directly_covered_control_ids(conn, vendor_id)
    mapped = await _mapped_control_ids(conn, direct)
    covered_ids = direct | mapped

    target_fw = await conn.fetchrow("SELECT id FROM frameworks WHERE code = $1", target_framework_code)
    if not target_fw:
        return {"framework_code": target_framework_code, "covered": [], "gaps": [], "coverage_pct": 0.0}

    controls = await conn.fetch(
        "SELECT id, control_ref, title, category FROM controls WHERE framework_id = $1 ORDER BY control_ref",
        target_fw["id"],
    )
    covered, gaps = [], []
    for c in controls:
        entry = {"control_ref": c["control_ref"], "title": c["title"], "category": c["category"]}
        (covered if str(c["id"]) in covered_ids else gaps).append(entry)

    total = len(controls)
    return {
        "framework_code": target_framework_code,
        "covered": covered, "gaps": gaps,
        "coverage_pct": round(len(covered) / total * 100, 1) if total else 0.0,
    }


async def control_coverage_scorecard(pool: asyncpg.Pool) -> list[dict]:
    """For each control, how many vendors have adequate/strong coverage,
    and how many *critical-tier* vendors are missing it — Phase 4 spec §4a
    ("how many vendors have this control, how many need it, what's the
    risk if the gap-vendors don't implement it"). Sorted so the biggest,
    highest-stakes gaps surface first.
    """
    async with pool.acquire() as conn:
        controls = await conn.fetch(
            "SELECT c.id, c.control_ref, c.title, f.code AS framework_code FROM controls c JOIN frameworks f ON f.id = c.framework_id",
        )
        vendors = await conn.fetch("SELECT id, tier FROM vendors WHERE status != 'terminated'")

        vendor_covered_ids: dict[str, set[str]] = {}
        for v in vendors:
            direct = await _directly_covered_control_ids(conn, str(v["id"]))
            vendor_covered_ids[str(v["id"])] = direct | await _mapped_control_ids(conn, direct)

    scorecard = []
    total_vendors = len(vendors)
    for c in controls:
        cid = str(c["id"])
        covered_count = sum(1 for covered in vendor_covered_ids.values() if cid in covered)
        critical_gaps = sum(
            1 for v in vendors if v["tier"] == "tier_1_critical" and cid not in vendor_covered_ids[str(v["id"])]
        )
        scorecard.append({
            "control_ref": c["control_ref"], "title": c["title"], "framework_code": c["framework_code"],
            "vendors_covered": covered_count, "vendors_total": total_vendors,
            "coverage_pct": round(covered_count / total_vendors * 100, 1) if total_vendors else 0.0,
            "critical_tier_gaps": critical_gaps,
        })

    return sorted(scorecard, key=lambda s: (-s["critical_tier_gaps"], s["coverage_pct"]))


async def related_controls(conn: asyncpg.Connection, control_id: str) -> list[dict]:
    """'Show me all controls related to encryption' — direct control_mappings
    neighbors of a given control, across frameworks, with confidence/rationale."""
    rows = await conn.fetch(
        """
        SELECT cm.confidence, cm.rationale,
               CASE WHEN cm.control_a_id = $1 THEN cm.control_b_id ELSE cm.control_a_id END AS related_id
        FROM control_mappings cm
        WHERE cm.control_a_id = $1 OR cm.control_b_id = $1
        """,
        control_id,
    )
    result = []
    for r in rows:
        c = await conn.fetchrow(
            "SELECT c.control_ref, c.title, f.code AS framework_code FROM controls c JOIN frameworks f ON f.id = c.framework_id WHERE c.id = $1",
            r["related_id"],
        )
        if c:
            result.append({
                "control_ref": c["control_ref"], "title": c["title"], "framework_code": c["framework_code"],
                "confidence": float(r["confidence"]), "rationale": r["rationale"],
            })
    return result
