"""Contract ingestion & parsing (Phase 4 spec §1a): extract SLA,
incident-notification SLA, security requirements, audit rights, liability,
indemnification, and termination/renewal terms from a contract's raw text.

Same mock/live provider split as every other LLM-backed feature in this
platform (Phase 1's answer analyzer, Phase 3's plan/evidence reviewer),
governed by the same `LLM_PROVIDER` setting. The mock provider uses
targeted regexes against real contract language patterns rather than
toy string matching — see the patterns below — so it produces sensible
output on an actual sample contract, not just a hand-crafted test fixture.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import get_settings

logger = logging.getLogger("tprm.contracts")

SYSTEM_PROMPT = (
    "You are a contracts specialist extracting security and compliance-relevant terms from a "
    "vendor contract for a Third-Party Risk Management platform. Extract only what is actually "
    "stated — do not infer values that aren't in the text. Return results as structured JSON."
)


@dataclass
class ContractTerms:
    sla_uptime_pct: float | None = None
    incident_notification_sla_hours: int | None = None
    security_requirements: list[str] = field(default_factory=list)
    audit_rights: str | None = None
    liability_cap: str | None = None
    indemnification: str | None = None
    termination_notice_days: int | None = None
    auto_renews: bool = False
    renewal_notice_days: int | None = None

    def to_dict(self) -> dict:
        return {
            "sla_uptime_pct": self.sla_uptime_pct,
            "incident_notification_sla_hours": self.incident_notification_sla_hours,
            "security_requirements": self.security_requirements,
            "audit_rights": self.audit_rights,
            "liability_cap": self.liability_cap,
            "indemnification": self.indemnification,
            "termination_notice_days": self.termination_notice_days,
            "auto_renews": self.auto_renews,
            "renewal_notice_days": self.renewal_notice_days,
        }


class ContractParserProvider(ABC):
    @abstractmethod
    async def extract_terms(self, raw_text: str) -> ContractTerms: ...


# Real contract-language patterns, not toy strings — this is what makes the
# mock provider useful against an actual sample contract rather than only
# ever matching a hand-crafted fixture written to match the regex.
_UPTIME_RE = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:monthly\s*)?uptime", re.IGNORECASE)
_NOTIFICATION_HOURS_RE = re.compile(
    r"notify.{0,80}?within\s*(\d+)\s*hours|within\s*(\d+)\s*hours.{0,80}?notif", re.IGNORECASE | re.DOTALL,
)
_TERMINATION_DAYS_RE = re.compile(r"terminat\w*.{0,60}?(\d+)\s*days?\s*(?:prior\s*)?(?:written\s*)?notice", re.IGNORECASE | re.DOTALL)
_RENEWAL_DAYS_RE = re.compile(r"renew\w*.{0,80}?(\d+)\s*days?", re.IGNORECASE | re.DOTALL)
_AUTO_RENEW_RE = re.compile(r"automatically\s*renew|auto-renew", re.IGNORECASE)

_SECURITY_KEYWORDS = (
    "SOC 2 Type II", "SOC 2 Type I", "ISO 27001", "ISO/IEC 27001", "PCI DSS", "PCI-DSS",
    "encrypt", "penetration test", "annual audit", "multi-factor authentication", "MFA",
    "background check", "security awareness training",
)


_MIN_CLAUSE_WORDS = 5  # real estate for skipping numbered section headings, e.g. "5. Liability."


def _find_sentence_containing(text: str, keyword: str) -> str | None:
    for sentence in re.split(r"(?<=[.;])\s+", text):
        sentence = sentence.strip()
        # A numbered heading ("5. Liability.") also literally contains its
        # own keyword but isn't the clause — skip anything too short to be
        # an actual sentence rather than a section title.
        if keyword.lower() in sentence.lower() and len(sentence.split()) >= _MIN_CLAUSE_WORDS:
            return sentence
    return None


class MockContractParserProvider(ContractParserProvider):
    async def extract_terms(self, raw_text: str) -> ContractTerms:
        terms = ContractTerms()

        if m := _UPTIME_RE.search(raw_text):
            terms.sla_uptime_pct = float(m.group(1))

        if m := _NOTIFICATION_HOURS_RE.search(raw_text):
            terms.incident_notification_sla_hours = int(m.group(1) or m.group(2))

        for keyword in _SECURITY_KEYWORDS:
            sentence = _find_sentence_containing(raw_text, keyword)
            if sentence and sentence not in terms.security_requirements:
                terms.security_requirements.append(sentence)

        terms.audit_rights = _find_sentence_containing(raw_text, "right to audit") or _find_sentence_containing(raw_text, "audit rights")
        terms.liability_cap = _find_sentence_containing(raw_text, "liability")
        terms.indemnification = _find_sentence_containing(raw_text, "indemnif")

        if m := _TERMINATION_DAYS_RE.search(raw_text):
            terms.termination_notice_days = int(m.group(1))

        terms.auto_renews = bool(_AUTO_RENEW_RE.search(raw_text))
        if terms.auto_renews:
            if m := _RENEWAL_DAYS_RE.search(raw_text):
                terms.renewal_notice_days = int(m.group(1))

        return terms


class AnthropicContractParserProvider(ContractParserProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic  # lazy import: not required for mock mode

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def extract_terms(self, raw_text: str) -> ContractTerms:
        prompt = f"""Contract text:
\"\"\"{raw_text[:12000]}\"\"\"

Return ONLY a JSON object with keys:
- sla_uptime_pct: number or null
- incident_notification_sla_hours: number or null
- security_requirements: array of strings (verbatim clauses naming specific security requirements)
- audit_rights: string or null
- liability_cap: string or null
- indemnification: string or null
- termination_notice_days: number or null
- auto_renews: boolean
- renewal_notice_days: number or null"""
        response = await self._client.messages.create(
            model=self._model, max_tokens=1000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                logger.error("Could not parse LLM response as JSON: %s", text)
                raise
            data = json.loads(match.group(0))

        return ContractTerms(
            sla_uptime_pct=data.get("sla_uptime_pct"),
            incident_notification_sla_hours=data.get("incident_notification_sla_hours"),
            security_requirements=list(data.get("security_requirements", [])),
            audit_rights=data.get("audit_rights"),
            liability_cap=data.get("liability_cap"),
            indemnification=data.get("indemnification"),
            termination_notice_days=data.get("termination_notice_days"),
            auto_renews=bool(data.get("auto_renews", False)),
            renewal_notice_days=data.get("renewal_notice_days"),
        )


_provider: ContractParserProvider | None = None


def get_contract_parser_provider() -> ContractParserProvider:
    global _provider
    if _provider is not None:
        return _provider
    settings = get_settings()
    if settings.llm_provider == "live" and settings.anthropic_api_key:
        _provider = AnthropicContractParserProvider(settings.anthropic_api_key, settings.anthropic_model)
    else:
        _provider = MockContractParserProvider()
    return _provider
