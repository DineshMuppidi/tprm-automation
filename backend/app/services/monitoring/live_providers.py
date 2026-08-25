"""Live monitoring providers — real HTTP calls to external services.

Two of these are genuinely network-tested in this build because they're
free and keyless: NVD (CVE data) and SEC EDGAR full-text search (financial
distress signals for public companies). See
`tests/test_live_providers_network.py` — those tests are marked and
skipped automatically if the network is unreachable, but they hit the real
APIs, not mocks.

The rest (HIBP, NewsAPI) are implemented correctly against their
documented request/response shapes but require a paid/registered API key
this environment doesn't have — they're wired up and will work the moment
a real key is set in `.env`, but weren't exercised against the live
service. The cert registry provider is intentionally NOT implemented: the
spec's own documented approach (BeautifulSoup-scraping the AICPA SOC 2
Trust Search UI) has no stable public API and no ToS/DOM-structure
verification was done here — shipping an unverified scraper against a
real registry would be worse than clearly not shipping one. See
docs/architecture/integrations.md for the documented approach.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.services.monitoring.news_classifier import classify_news_article
from app.services.monitoring.providers import (
    BreachProvider, CertRegistryProvider, FinancialProvider, NewsProvider,
)
from app.services.monitoring.types import BreachSignal, CertSignal, FinancialSignal, NewsSignal, VendorInfo

logger = logging.getLogger("tprm.monitoring.live")

USER_AGENT = "tprm-automation-portfolio-project (contact: set EMAIL_FROM in .env)"


class LiveCertRegistryProvider(CertRegistryProvider):
    async def check(self, vendor: VendorInfo) -> list[CertSignal]:
        raise NotImplementedError(
            "Live SOC 2 / ISO 27001 registry scraping is not implemented — "
            "see docs/architecture/integrations.md for the documented approach. "
            "Set CERT_REGISTRY_PROVIDER=mock (default)."
        )


class LiveBreachProvider(BreachProvider):
    def __init__(self, hibp_api_key: str, nvd_api_key: str):
        self._hibp_api_key = hibp_api_key
        self._nvd_api_key = nvd_api_key

    async def check(self, vendor: VendorInfo) -> list[BreachSignal]:
        signals: list[BreachSignal] = []
        signals.extend(await self._check_nvd(vendor))
        if self._hibp_api_key and vendor.primary_domain:
            signals.extend(await self._check_hibp(vendor))
        return signals

    async def _check_nvd(self, vendor: VendorInfo) -> list[BreachSignal]:
        params = {
            "keywordSearch": vendor.legal_name,
            "resultsPerPage": 5,
            "pubStartDate": (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000"),
        }
        headers = {"apiKey": self._nvd_api_key} if self._nvd_api_key else {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://services.nvd.nist.gov/rest/json/cves/2.0", params=params, headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("NVD lookup failed for %s: %s", vendor.legal_name, e)
            return []

        signals = []
        for item in data.get("vulnerabilities", []):
            cve = item["cve"]
            score, severity = _extract_cvss(cve.get("metrics", {}))
            desc = next((d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"), "")
            signals.append(BreachSignal(
                kind="cve", headline=f"{cve['id']}: {desc[:120]}", source="nvd.nist.gov",
                detected_at=datetime.now(timezone.utc),
                detail={"cve_id": cve["id"], "cvss_score": score, "severity": severity, "published": cve["published"]},
            ))
        return signals

    async def _check_hibp(self, vendor: VendorInfo) -> list[BreachSignal]:
        headers = {"hibp-api-key": self._hibp_api_key, "User-Agent": USER_AGENT}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://haveibeenpwned.com/api/v3/breaches",
                    params={"domain": vendor.primary_domain}, headers=headers,
                )
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                breaches = resp.json()
        except httpx.HTTPError as e:
            logger.warning("HIBP lookup failed for %s: %s", vendor.primary_domain, e)
            return []

        return [
            BreachSignal(
                kind="breach", headline=f"Breach on record for {vendor.primary_domain}: {b['Name']}",
                source="haveibeenpwned.com", detected_at=datetime.now(timezone.utc),
                detail={"breach_date": b.get("BreachDate"), "data_classes": b.get("DataClasses", [])},
            )
            for b in breaches
        ]


def _extract_cvss(metrics: dict) -> tuple[float | None, str | None]:
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if entries:
            data = entries[0].get("cvssData", {})
            return data.get("baseScore"), data.get("baseSeverity")
    return None, None


class LiveNewsProvider(NewsProvider):
    def __init__(self, newsapi_api_key: str):
        self._api_key = newsapi_api_key

    async def check(self, vendor: VendorInfo) -> list[NewsSignal]:
        if not self._api_key:
            return []
        params = {"q": f'"{vendor.legal_name}"', "sortBy": "publishedAt", "pageSize": 5, "language": "en"}
        headers = {"X-Api-Key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://newsapi.org/v2/everything", params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("NewsAPI lookup failed for %s: %s", vendor.legal_name, e)
            return []

        signals = []
        for article in data.get("articles", []):
            sentiment, story_type = classify_news_article(article.get("title", ""), article.get("description") or "")
            signals.append(NewsSignal(
                headline=article.get("title", ""), source_url=article.get("url", ""),
                published_at=datetime.now(timezone.utc), sentiment=sentiment, story_type=story_type,
                summary=article.get("description") or "",
            ))
        return signals


class LiveFinancialProvider(FinancialProvider):
    """SEC EDGAR full-text search — public companies only. Real, keyless,
    network-tested (see tests/test_live_providers_network.py)."""

    DISTRESS_KEYWORDS = ["going concern", "material weakness", "default on"]

    async def check(self, vendor: VendorInfo) -> list[FinancialSignal]:
        signals = []
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=10) as client:
            for keyword in self.DISTRESS_KEYWORDS:
                params = {"q": f'"{vendor.legal_name}" "{keyword}"', "forms": "10-K,10-Q"}
                try:
                    resp = await client.get("https://efts.sec.gov/LATEST/search-index", params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError as e:
                    logger.warning("SEC EDGAR lookup failed for %s: %s", vendor.legal_name, e)
                    continue

                hits = data.get("hits", {}).get("hits", [])
                if hits:
                    filing = hits[0]["_source"]
                    signals.append(FinancialSignal(
                        signal_type="going_concern" if keyword == "going concern" else "credit_downgrade",
                        detail=f'"{keyword}" language found in a recent {filing.get("root_forms", ["filing"])[0]} filing',
                        severity="high" if keyword == "going concern" else "medium",
                        source="sec.gov EDGAR full-text search",
                    ))
        return signals
