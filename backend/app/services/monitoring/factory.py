from app.config import get_settings
from app.services.monitoring.live_providers import (
    LiveBreachProvider, LiveCertRegistryProvider, LiveFinancialProvider, LiveNewsProvider,
)
from app.services.monitoring.mock_providers import (
    MockBreachProvider, MockCertRegistryProvider, MockFinancialProvider, MockNewsProvider,
)
from app.services.monitoring.providers import (
    BreachProvider, CertRegistryProvider, FinancialProvider, NewsProvider,
)


def get_cert_registry_provider() -> CertRegistryProvider:
    settings = get_settings()
    return LiveCertRegistryProvider() if settings.cert_registry_provider == "live" else MockCertRegistryProvider()


def get_breach_provider() -> BreachProvider:
    settings = get_settings()
    if settings.breach_provider == "live":
        return LiveBreachProvider(hibp_api_key=settings.hibp_api_key, nvd_api_key=settings.nvd_api_key)
    return MockBreachProvider()


def get_news_provider() -> NewsProvider:
    settings = get_settings()
    if settings.news_provider == "live":
        return LiveNewsProvider(newsapi_api_key=settings.newsapi_api_key)
    return MockNewsProvider()


def get_financial_provider() -> FinancialProvider:
    settings = get_settings()
    return LiveFinancialProvider() if settings.financial_provider == "live" else MockFinancialProvider()
