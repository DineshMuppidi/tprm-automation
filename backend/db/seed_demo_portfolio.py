"""Seeds a realistic small vendor portfolio (~15 vendors across all four
tiers, varying industries and assessment quality) on top of whatever's
already in the database — for demoing/screenshotting the admin dashboards
(board reporting, monitoring scoreboard, control-gap analysis) with more
than one vendor. `seed_demo_data.py` intentionally stays a single-vendor
minimal fixture for portal walkthroughs; this is the "populated org" view.

Talks to a *running* backend over HTTP (like scripts/load_test.py) rather
than the DB directly, so every vendor goes through the real create ->
assign -> answer -> submit -> monitor pipeline, not hand-inserted rows.

Usage (with the backend already running on localhost:8000):
    python backend/db/seed_demo_portfolio.py
"""

import asyncio
import os

import httpx

BASE_URL = os.environ.get("TPRM_BASE_URL", "http://127.0.0.1:8000")
ADMIN_KEY = os.environ.get("TPRM_ADMIN_KEY", "dev-admin-key")

# quality controls how questions get answered (see _answer_for below);
# stage controls how far through the workflow the assessment gets taken.
VENDORS = [
    {"legal_name": "CloudVault Storage Corp", "industry": "Cloud Storage", "tier": "tier_1_critical",
     "data_access_level": "restricted_pii", "quality": "excellent", "stage": "complete"},
    {"legal_name": "PayrollPro Systems", "industry": "Payroll", "tier": "tier_1_critical",
     "data_access_level": "restricted_pii", "quality": "poor", "stage": "complete"},
    {"legal_name": "BackupGuard Systems", "industry": "Backup & DR", "tier": "tier_1_critical",
     "data_access_level": "confidential", "quality": "excellent", "stage": "complete"},
    {"legal_name": "BenefitsAdmin Co", "industry": "HR Benefits", "tier": "tier_1_critical",
     "data_access_level": "phi", "quality": "average", "stage": "complete"},
    {"legal_name": "SecureAuth Identity", "industry": "Identity & Access", "tier": "tier_2_high",
     "data_access_level": "confidential", "quality": "good", "stage": "complete"},
    {"legal_name": "DataSync Analytics", "industry": "Analytics", "tier": "tier_2_high",
     "data_access_level": "internal_only", "quality": "average", "stage": "complete"},
    {"legal_name": "VideoConf Plus", "industry": "Video Conferencing", "tier": "tier_2_high",
     "data_access_level": "confidential", "quality": "poor", "stage": "in_progress"},
    {"legal_name": "InvoiceFlow Billing", "industry": "Billing & Invoicing", "tier": "tier_2_high",
     "data_access_level": "confidential", "quality": "good", "stage": "complete"},
    {"legal_name": "QuickShip Logistics API", "industry": "Logistics", "tier": "tier_3_medium",
     "data_access_level": "internal_only", "quality": "average", "stage": "complete"},
    {"legal_name": "MailBlast Marketing", "industry": "Email Marketing", "tier": "tier_3_medium",
     "data_access_level": "internal_only", "quality": "poor", "stage": "complete"},
    {"legal_name": "ExpenseTrack", "industry": "Expense Management", "tier": "tier_3_medium",
     "data_access_level": "confidential", "quality": "poor", "stage": "complete"},
    {"legal_name": "ChatWidget Co", "industry": "Customer Support", "tier": "tier_3_medium",
     "data_access_level": "none", "quality": "good", "stage": "in_progress"},
    {"legal_name": "DevTools Inc", "industry": "Developer Tooling", "tier": "tier_4_low",
     "data_access_level": "none", "quality": "good", "stage": "complete"},
    {"legal_name": "FormBuilder SaaS", "industry": "Forms & Surveys", "tier": "tier_4_low",
     "data_access_level": "none", "quality": "average", "stage": "pending"},
    {"legal_name": "AnalyticsPixel", "industry": "Marketing Tech", "tier": "tier_4_low",
     "data_access_level": "none", "quality": "average", "stage": "pending"},
]

_STRONG_TEXT = (
    "This is enforced org-wide across all systems and audited quarterly. We are "
    "SOC 2 Type II certified and ISO 27001 certified, with AES-256 encryption and "
    "MFA required for all admin access; our incident response plan is tested annually."
)
_ADEQUATE_TEXT = (
    "We have a documented process for this that the security team maintains and "
    "reviews periodically as part of our standard operating procedures."
)
_WEAK_TEXT = (
    "We don't have a formal process for this yet — it's still in progress and not "
    "currently implemented org-wide. No formal schedule is in place."
)

_TEXT_BY_QUALITY = {
    "excellent": _STRONG_TEXT, "good": _STRONG_TEXT,
    "average": _ADEQUATE_TEXT, "poor": _WEAK_TEXT,
}


def _answer_for(question: dict, quality: str) -> str:
    if question["input_type"] == "select":
        choices = question["options"]["choices"]
        if quality in ("excellent", "good"):
            return choices[0]
        if quality == "average":
            return choices[len(choices) // 2]
        return choices[-1]
    return _TEXT_BY_QUALITY[quality]


async def _fill_and_maybe_submit(client: httpx.AsyncClient, assessment_id: str, quality: str, submit: bool, partial: bool):
    answered = set()
    for _ in range(6):  # a few passes to pick up conditional follow-ups as they appear
        r = await client.get(f"/assessments/{assessment_id}")
        questions = r.json()["questions"]
        new = [q for q in questions if q["id"] not in answered]
        if not new:
            break
        target = new[: max(1, len(new) // 2)] if partial else new
        for q in target:
            await client.put(
                f"/assessments/{assessment_id}/responses/{q['id']}",
                json={"raw_answer": _answer_for(q, quality)},
            )
            answered.add(q["id"])
        if partial:
            break
    if submit:
        await client.post(f"/assessments/{assessment_id}/submit")


async def main():
    admin = httpx.AsyncClient(base_url=BASE_URL, headers={"X-Admin-Key": ADMIN_KEY}, timeout=30)

    templates = {t["tier"]: t for t in (await admin.get("/admin/templates")).json()}

    created = []
    for i, v in enumerate(VENDORS):
        vr = await admin.post("/admin/vendors", json={
            "legal_name": v["legal_name"], "industry": v["industry"], "tier": v["tier"],
            "data_access_level": v["data_access_level"],
            "primary_contact": {
                "full_name": "Demo Contact", "email": f"contact+{i}@{v['legal_name'].lower().replace(' ', '').replace(',', '').replace('.', '')}.example.com",
                "role": "Security Lead", "is_primary": True,
            },
        })
        vendor = vr.json()
        template = templates.get(v["tier"])
        if not template:
            print(f"SKIP {v['legal_name']}: no template for {v['tier']}")
            continue

        ar = await admin.post("/admin/assessments", json={
            "vendor_id": vendor["id"], "template_id": template["id"], "due_in_days": 14,
        })
        assessment = ar.json()
        print(f"{v['legal_name']:<28} tier={v['tier']:<16} stage={v['stage']:<10} assessment={assessment['id']}")

        if v["stage"] == "pending":
            created.append((v["legal_name"], vendor["id"], None))
            continue

        token = assessment["dev_login_url"].split("token=")[1]
        session_resp = await httpx.AsyncClient(base_url=BASE_URL, timeout=30).post("/auth/verify", json={"token": token})
        session = session_resp.json()["access_token"]
        vendor_client = httpx.AsyncClient(base_url=BASE_URL, headers={"Authorization": f"Bearer {session}"}, timeout=30)

        await _fill_and_maybe_submit(
            vendor_client, assessment["id"], v["quality"],
            submit=(v["stage"] == "complete"), partial=(v["stage"] == "in_progress"),
        )
        await vendor_client.aclose()
        created.append((v["legal_name"], vendor["id"], assessment["id"]))

    print("\nRunning monitoring checks across the portfolio...")
    checks = await admin.post("/admin/monitoring/run-checks", json={})
    print(checks.json())

    print(f"\nSeeded {len(created)} vendors.")
    await admin.aclose()


if __name__ == "__main__":
    asyncio.run(main())
