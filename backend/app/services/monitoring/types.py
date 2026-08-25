"""Shared value types for the four Phase 2 monitoring sources. These are
plain dataclasses, not Pydantic/DB models — providers hand them to
alert_engine, which is the only place that touches the database."""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class VendorInfo:
    id: str
    legal_name: str
    primary_domain: str | None
    tier: str


@dataclass
class CertSignal:
    certificate_type: str          # 'SOC 2 Type II', 'ISO 27001', ...
    status: str                    # 'valid' | 'expiring_soon' | 'expired' | 'not_found'
    expiration_date: date | None
    days_until_expiry: int | None
    auditor: str | None
    source: str = "registry"


@dataclass
class BreachSignal:
    kind: str                      # 'breach' | 'cve'
    headline: str
    source: str
    detected_at: datetime
    detail: dict = field(default_factory=dict)


@dataclass
class NewsSignal:
    headline: str
    source_url: str
    published_at: datetime
    sentiment: str                 # 'positive' | 'neutral' | 'negative'
    story_type: str                # 'breach' | 'lawsuit' | 'bankruptcy' | 'leadership_change' | 'other'
    summary: str


@dataclass
class FinancialSignal:
    signal_type: str               # 'credit_downgrade' | 'missed_payment' | 'mass_layoffs' | 'debt_increase' | 'going_concern'
    detail: str
    severity: str                  # 'low' | 'medium' | 'high'
    source: str = "unknown"
