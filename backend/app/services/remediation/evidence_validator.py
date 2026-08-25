"""LLM-powered remediation review (Phase 3 spec §2 plan review, §3 evidence
validation engine) — two related but distinct judgment calls, both behind
the same mock/live provider split as Phase 1's llm_analyzer.py, governed
by the same `LLM_PROVIDER`/`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` settings
(one env var controls every LLM-backed feature in the platform, not one
per feature).

  * review_plan       — is the vendor's proposed remediation plan credible
                         (concrete actions + timeline), or vague hand-waving?
  * validate_evidence  — does what the vendor uploaded actually prove the
                         finding is fixed, per the spec's own strictness
                         rule: a screenshot of one account isn't proof MFA
                         is enforced everywhere.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import get_settings
from app.services.llm_analyzer import EvidenceContext

logger = logging.getLogger("tprm.remediation")

VALID_RECOMMENDATIONS = {"approve", "request_clarification", "reject"}

PLAN_REVIEW_SYSTEM_PROMPT = (
    "You are a cybersecurity GRC expert reviewing a vendor's proposed remediation plan "
    "for a security finding. A credible plan names concrete actions and a timeline. Vague "
    "language ('we will look into it', 'planning to review') without specifics is not "
    "credible. Return results as structured JSON."
)

EVIDENCE_VALIDATION_SYSTEM_PROMPT = (
    "You are a cybersecurity GRC expert validating evidence a vendor submitted to close a "
    "security finding. Be strict and specific: evidence must actually demonstrate the fix "
    "at the required scope (e.g. a screenshot of one account does not prove a control is "
    "enforced organization-wide). Return results as structured JSON."
)


@dataclass
class FindingContext:
    title: str
    description: str
    required_evidence: str | None
    severity: str


@dataclass
class PlanReviewResult:
    credible: bool
    reasoning: str
    follow_up_question: str | None = None


@dataclass
class EvidenceValidationResult:
    recommendation: str   # 'approve' | 'request_clarification' | 'reject'
    confidence: float
    reasoning: str
    follow_up_question: str | None = None


class RemediationReviewProvider(ABC):
    @abstractmethod
    async def review_plan(self, finding: FindingContext, plan_text: str) -> PlanReviewResult: ...

    @abstractmethod
    async def validate_evidence(
        self, finding: FindingContext, evidence: list[EvidenceContext], vendor_notes: str,
    ) -> EvidenceValidationResult: ...


_WEAK_PLAN_MARKERS = ("we will review", "planning to", "look into", "tbd", "to be determined", "consider", "best effort", "when possible", "eventually")
_STRONG_PLAN_MARKERS = ("deploy", "implement", "configure", "roll out", "enforce", "milestone", "complete by")
_TIMELINE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2}|\d{1,3}\s*(day|week|month)s?|q[1-4]\s*20\d{2})\b", re.IGNORECASE)

_STRONG_EVIDENCE_TYPES = {"audit_report", "penetration_test", "soc2_type2", "iso27001_cert", "pci_aoc"}


class MockRemediationReviewProvider(RemediationReviewProvider):
    async def review_plan(self, finding: FindingContext, plan_text: str) -> PlanReviewResult:
        text = (plan_text or "").strip()
        if not text:
            return PlanReviewResult(
                credible=False, reasoning="No plan provided.",
                follow_up_question=f"Please describe how and when you will remediate: {finding.title}",
            )

        text_lower = text.lower()
        weak_hits = sum(1 for m in _WEAK_PLAN_MARKERS if m in text_lower)
        strong_hits = sum(1 for m in _STRONG_PLAN_MARKERS if m in text_lower)
        has_timeline = bool(_TIMELINE_PATTERN.search(text_lower))
        credible = len(text) > 40 and has_timeline and strong_hits >= weak_hits

        if credible:
            return PlanReviewResult(credible=True, reasoning="Plan names concrete actions and a timeline.")
        return PlanReviewResult(
            credible=False,
            reasoning="Plan is vague or lacks a concrete timeline — self-reported intent without specifics does not meet the bar for a credible remediation plan.",
            follow_up_question=(
                f"Your plan doesn't include a clear timeline or concrete steps. Can you specify "
                f"exactly what you'll do and by when to remediate: {finding.title}?"
            ),
        )

    async def validate_evidence(
        self, finding: FindingContext, evidence: list[EvidenceContext], vendor_notes: str,
    ) -> EvidenceValidationResult:
        if not evidence:
            return EvidenceValidationResult(
                recommendation="reject", confidence=10.0, reasoning="No evidence was uploaded.",
                follow_up_question=f"Please upload evidence proving: {finding.required_evidence or finding.title}",
            )

        if any(e.document_type in _STRONG_EVIDENCE_TYPES for e in evidence):
            return EvidenceValidationResult(
                recommendation="approve", confidence=85.0,
                reasoning="A third-party audit/certification report is strong, verifiable evidence.",
            )

        if all(e.document_type == "screenshot" for e in evidence) and finding.severity in ("critical", "high"):
            return EvidenceValidationResult(
                recommendation="request_clarification", confidence=45.0,
                reasoning="A screenshot shows a point-in-time configuration but doesn't confirm scope.",
                follow_up_question=(
                    f"Your evidence shows a single configuration screenshot. For a {finding.severity} "
                    f"finding, can you confirm this control is enforced across all in-scope systems, "
                    f"not just the one shown — or provide an audit report covering full scope?"
                ),
            )

        if all(e.document_type == "policy_doc" for e in evidence):
            return EvidenceValidationResult(
                recommendation="request_clarification", confidence=40.0,
                reasoning="A policy document shows intent, not implementation.",
                follow_up_question="A policy document describes what should happen — can you also provide evidence the control is actually implemented (e.g. a system configuration screenshot or audit report)?",
            )

        return EvidenceValidationResult(
            recommendation="approve", confidence=65.0,
            reasoning="Evidence provided appears to reasonably address the finding.",
        )


class AnthropicRemediationReviewProvider(RemediationReviewProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic  # lazy import: not required for mock mode

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def review_plan(self, finding: FindingContext, plan_text: str) -> PlanReviewResult:
        prompt = f"""Finding: {finding.title}
Description: {finding.description}
Severity: {finding.severity}

Vendor's proposed remediation plan:
\"\"\"{plan_text}\"\"\"

Return ONLY a JSON object with keys: credible (boolean), reasoning (string), follow_up_question (string or null)."""
        data = await self._call(PLAN_REVIEW_SYSTEM_PROMPT, prompt)
        return PlanReviewResult(
            credible=bool(data.get("credible", False)),
            reasoning=data.get("reasoning", ""),
            follow_up_question=data.get("follow_up_question"),
        )

    async def validate_evidence(
        self, finding: FindingContext, evidence: list[EvidenceContext], vendor_notes: str,
    ) -> EvidenceValidationResult:
        evidence_desc = ", ".join(f"{e.document_type} ({e.original_filename})" for e in evidence) or "none"
        prompt = f"""Finding: {finding.title}
Description: {finding.description}
Required evidence: {finding.required_evidence or "not specified"}
Severity: {finding.severity}
Evidence submitted: {evidence_desc}
Vendor's notes: {vendor_notes or "none"}

Return ONLY a JSON object with keys: recommendation (one of "approve", "request_clarification", "reject"),
confidence (0-100), reasoning (string), follow_up_question (string or null)."""
        data = await self._call(EVIDENCE_VALIDATION_SYSTEM_PROMPT, prompt)
        recommendation = data.get("recommendation")
        return EvidenceValidationResult(
            recommendation=recommendation if recommendation in VALID_RECOMMENDATIONS else "request_clarification",
            confidence=float(data.get("confidence", 0)),
            reasoning=data.get("reasoning", ""),
            follow_up_question=data.get("follow_up_question"),
        )

    async def _call(self, system_prompt: str, user_prompt: str) -> dict:
        response = await self._client.messages.create(
            model=self._model, max_tokens=500, system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            logger.error("Could not parse LLM response as JSON: %s", text)
            raise


_provider: RemediationReviewProvider | None = None


def get_remediation_review_provider() -> RemediationReviewProvider:
    global _provider
    if _provider is not None:
        return _provider
    settings = get_settings()
    if settings.llm_provider == "live" and settings.anthropic_api_key:
        _provider = AnthropicRemediationReviewProvider(settings.anthropic_api_key, settings.anthropic_model)
    else:
        _provider = MockRemediationReviewProvider()
    return _provider
