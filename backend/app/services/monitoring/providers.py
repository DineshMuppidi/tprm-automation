"""Provider interfaces for the four Phase 2 monitoring source categories
(Phase 2 spec §1). Each has a `mock` implementation (deterministic,
offline, free — the default) and a `live` implementation that calls a real
external API. See docs/architecture/integrations.md for auth/rate-limit/
cost details per source, and monitoring/live_providers.py for which ones
are actually network-tested in this build vs. correctly-implemented-but-
untested for lack of an API key.
"""

from abc import ABC, abstractmethod

from app.services.monitoring.types import BreachSignal, CertSignal, FinancialSignal, NewsSignal, VendorInfo


class CertRegistryProvider(ABC):
    """SOC 2 Trust Search / ISO 27001 / FedRAMP / PCI-DSS registries."""

    @abstractmethod
    async def check(self, vendor: VendorInfo) -> list[CertSignal]: ...


class BreachProvider(ABC):
    """Breach databases (HIBP) + vulnerability feeds (NVD, GitHub Advisory)
    — grouped into one category per the spec's own data-source grouping."""

    @abstractmethod
    async def check(self, vendor: VendorInfo) -> list[BreachSignal]: ...


class NewsProvider(ABC):
    """News/reputation monitoring — returns already-classified signals;
    a live implementation does its own sentiment/story-type classification
    (via the LLM analyzer) before returning, so callers never see raw
    unclassified articles."""

    @abstractmethod
    async def check(self, vendor: VendorInfo) -> list[NewsSignal]: ...


class FinancialProvider(ABC):
    """Financial distress signals (credit rating, SEC filings, layoffs)."""

    @abstractmethod
    async def check(self, vendor: VendorInfo) -> list[FinancialSignal]: ...
