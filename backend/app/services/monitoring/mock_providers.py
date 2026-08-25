"""Mock monitoring providers — deterministic and offline (default; see
app/config.py's *_PROVIDER settings). Determinism matters here beyond
"tests are reproducible": the alert engine only raises a new alert when a
signal is new or changed (Phase 2 spec §1: "Change detection — alert if
cert status changes unexpectedly"), so a mock that returned fresh random
data on every run would spam duplicate alerts on every check instead of
demonstrating that change-detection logic actually working.

One vendor is special-cased end to end: whichever vendor has
`primary_domain == "acmehr-demo.example.com"` (the demo vendor
`db/seed_demo_data.py` creates) reproduces the healthcare-vendor
ransomware scenario from `docs/architecture/scenario-vendor-ransomware.md`
across all four sources — breach, an expiring SOC 2 cert, negative press,
and a credit downgrade — so running the monitoring checks against the
Phase 1 demo data tells the same story Phase 0 designed around. Every
other vendor gets a stable, mostly-quiet signal set derived from a hash of
its own id, so the dashboard has believable variety without being noisy.
"""

import hashlib
from datetime import date, datetime, timedelta, timezone

from app.services.monitoring.providers import (
    BreachProvider, CertRegistryProvider, FinancialProvider, NewsProvider,
)
from app.services.monitoring.types import BreachSignal, CertSignal, FinancialSignal, NewsSignal, VendorInfo

INCIDENT_VENDOR_DOMAIN = "acmehr-demo.example.com"


def _stable_fraction(vendor_id: str, salt: str) -> float:
    """Deterministic pseudo-random float in [0, 1) for a (vendor, salt) pair."""
    digest = hashlib.sha256(f"{vendor_id}:{salt}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _is_incident_vendor(vendor: VendorInfo) -> bool:
    return vendor.primary_domain == INCIDENT_VENDOR_DOMAIN


class MockCertRegistryProvider(CertRegistryProvider):
    async def check(self, vendor: VendorInfo) -> list[CertSignal]:
        if _is_incident_vendor(vendor):
            # Matches the Phase 2 spec's own "Certification Expiring Soon" example verbatim.
            return [CertSignal(
                certificate_type="SOC 2 Type II", status="expiring_soon",
                expiration_date=date.today() + timedelta(days=21),
                days_until_expiry=21, auditor="Big4 Audit Firm",
            )]

        roll = _stable_fraction(vendor.id, "cert")
        if roll < 0.10:
            days = int(15 + roll * 200)
            return [CertSignal(
                certificate_type="SOC 2 Type II", status="expiring_soon",
                expiration_date=date.today() + timedelta(days=days),
                days_until_expiry=days, auditor="Independent Audit Firm",
            )]
        return [CertSignal(
            certificate_type="SOC 2 Type II", status="valid",
            expiration_date=date.today() + timedelta(days=180 + int(roll * 180)),
            days_until_expiry=180 + int(roll * 180), auditor="Independent Audit Firm",
        )]


class MockBreachProvider(BreachProvider):
    async def check(self, vendor: VendorInfo) -> list[BreachSignal]:
        now = datetime.now(timezone.utc)
        if _is_incident_vendor(vendor):
            return [BreachSignal(
                kind="breach",
                headline=f"{vendor.legal_name} discloses ransomware incident affecting customer records",
                source="mock:dark-web-monitoring + press coverage",
                detected_at=now,
                detail={
                    "estimated_records_affected": 50000,
                    "data_types_involved": ["employee_pii", "compensation_data"],
                    "attack_type": "ransomware",
                },
            )]

        roll = _stable_fraction(vendor.id, "breach")
        if roll < 0.08:
            return [BreachSignal(
                kind="cve",
                headline=f"New high-severity CVE published in an open-source component used by {vendor.legal_name}",
                source="mock:github-advisory",
                detected_at=now,
                detail={"cve_id": f"CVE-2026-{10000 + int(roll * 9999)}", "cvss_score": round(7 + roll * 2, 1)},
            )]
        return []


class MockNewsProvider(NewsProvider):
    async def check(self, vendor: VendorInfo) -> list[NewsSignal]:
        now = datetime.now(timezone.utc)
        if _is_incident_vendor(vendor):
            return [NewsSignal(
                headline=f"{vendor.legal_name} ransomware attack draws regulatory scrutiny",
                source_url="https://example-news.test/acme-hr-ransomware",
                published_at=now, sentiment="negative", story_type="breach",
                summary="Coverage of the disclosed ransomware incident and its impact on customers.",
            )]

        roll = _stable_fraction(vendor.id, "news")
        if roll < 0.05:
            return [NewsSignal(
                headline=f"{vendor.legal_name} CEO departs amid investor disputes",
                source_url="https://example-news.test/leadership-change",
                published_at=now, sentiment="negative", story_type="leadership_change",
                summary="Leadership transition reported; investor confidence questioned.",
            )]
        if roll < 0.15:
            return [NewsSignal(
                headline=f"{vendor.legal_name} announces new product partnership",
                source_url="https://example-news.test/partnership",
                published_at=now, sentiment="positive", story_type="other",
                summary="Routine positive business news, no security or compliance relevance.",
            )]
        return []


class MockFinancialProvider(FinancialProvider):
    async def check(self, vendor: VendorInfo) -> list[FinancialSignal]:
        if _is_incident_vendor(vendor):
            return [FinancialSignal(
                signal_type="credit_downgrade",
                detail="Credit rating downgraded one notch; agency cites incident-response costs and cash flow concerns.",
                severity="medium", source="mock:credit-rating-agency",
            )]

        roll = _stable_fraction(vendor.id, "financial")
        if roll < 0.04:
            return [FinancialSignal(
                signal_type="mass_layoffs", detail="Vendor reported a workforce reduction exceeding 15%.",
                severity="medium", source="mock:layoffs-tracker",
            )]
        return []
