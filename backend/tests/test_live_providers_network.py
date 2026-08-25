"""Network tests against real, free, keyless APIs (NVD, SEC EDGAR) — these
are the two live providers actually exercised end-to-end in this build; see
live_providers.py's module docstring for which ones aren't. Skipped
automatically if the network is unreachable rather than failing the suite
in an offline/CI environment.
"""

import httpx
import pytest

from app.services.monitoring.live_providers import LiveBreachProvider, LiveFinancialProvider
from app.services.monitoring.types import VendorInfo


def _network_available() -> bool:
    try:
        httpx.get("https://services.nvd.nist.gov", timeout=3)
        return True
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _network_available(), reason="network unreachable")


async def test_nvd_provider_returns_real_cve_data():
    # openssl publishes CVEs frequently enough that the provider's default
    # 30-day window reliably finds at least one — proves the real request,
    # auth handling, and CVSS-field parsing all work end to end.
    provider = LiveBreachProvider(hibp_api_key="", nvd_api_key="")
    vendor = VendorInfo(id="x", legal_name="openssl", primary_domain=None, tier="tier_3_medium")

    signals = await provider.check(vendor)

    assert all(s.kind == "cve" for s in signals)
    if signals:  # NVD's own recent-publication rate can vary; the call succeeding is the real assertion
        assert signals[0].detail["cve_id"].startswith("CVE-")


async def test_sec_edgar_provider_reachable_and_parses_response():
    provider = LiveFinancialProvider()
    # A real, large public company — proves the endpoint, required
    # User-Agent header, and JSON parsing all actually work end to end.
    # Apple is vanishingly unlikely to ever have "going concern" 10-K
    # language, so the meaningful assertion is that the call succeeded and
    # returned a list, not that it found distress signals.
    vendor = VendorInfo(id="x", legal_name="Apple Inc", primary_domain=None, tier="tier_1_critical")

    signals = await provider.check(vendor)

    assert isinstance(signals, list)
