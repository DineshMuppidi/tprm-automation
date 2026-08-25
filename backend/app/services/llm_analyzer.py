"""LLM-powered vendor answer analysis (Phase 1 §3).

Two providers behind one interface:
  * MockLLMProvider  — deterministic, offline, free. Default. Implements the
    exact SOC 2 Type I/II contradiction check from the Phase 1 spec's own
    walkthrough scenario, so that scenario is a real, testable code path
    and not just a paragraph in a doc.
  * AnthropicLLMProvider — calls the real Claude API using the system
    prompt specified in the project brief, for when ANTHROPIC_API_KEY is
    configured and LLM_PROVIDER=live.

Selection is via `LLM_PROVIDER` env var — see app/config.py.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import get_settings

logger = logging.getLogger("tprm.llm")

SYSTEM_PROMPT = (
    "You are a cybersecurity GRC expert analyzing vendor security assessments. "
    "Your job is to extract key control evidence from vendor responses and flag "
    "inconsistencies. Be strict: self-reported claims without evidence = Weak. "
    "Return results as structured JSON."
)

VALID_CLASSIFICATIONS = {"strong", "adequate", "weak", "missing", "contradictory"}
VALID_EVIDENCE_STATUS = {"verified", "unverified", "needs_clarification", "rejected"}


@dataclass
class QuestionContext:
    prompt: str
    control_title: str | None
    scoring_rubric: dict | None
    evidence_required: bool


@dataclass
class EvidenceContext:
    document_type: str
    original_filename: str


@dataclass
class AnalysisResult:
    classification: str
    confidence_score: float
    extracted_claims: list[str] = field(default_factory=list)
    evidence_status: str = "unverified"
    follow_up_needed: bool = False
    follow_up_question: str | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def analyze(
        self, question: QuestionContext, raw_answer: str, evidence: list[EvidenceContext]
    ) -> AnalysisResult: ...


_STRONG_MARKERS = (
    "enforced", "org-wide", "organization-wide", "all systems", "all admin",
    "quarterly", "annually audited", "aes-256", "soc 2 type ii", "soc2 type ii",
    "iso 27001 certified", "mfa required", "phishing-resistant", "penetration tested",
    "incident response tested",
)
_WEAK_MARKERS = (
    "not sure", "n/a", "don't know", "working on it", "planned", "not implemented",
    "no formal", "none", "not currently", "in progress", "best effort",
)


def _split_claims(raw_answer: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", raw_answer.strip())
    return [p.strip() for p in parts if p.strip()][:5]


class MockLLMProvider(LLMProvider):
    async def analyze(
        self, question: QuestionContext, raw_answer: str, evidence: list[EvidenceContext]
    ) -> AnalysisResult:
        answer = (raw_answer or "").strip()

        if not answer:
            return AnalysisResult(
                classification="missing",
                confidence_score=0,
                extracted_claims=[],
                evidence_status="unverified" if question.evidence_required else "verified",
                follow_up_needed=True,
                follow_up_question=f"Please provide an answer to: {question.prompt}",
            )

        # The Phase 1 walkthrough scenario, made real: vendor claims SOC 2
        # Type II in the answer text but the attached report is Type I.
        answer_lower = answer.lower()
        claims_type_ii = "type ii" in answer_lower or "type 2" in answer_lower
        has_type_i_evidence = any(e.document_type == "soc2_type1" for e in evidence)
        if claims_type_ii and has_type_i_evidence:
            return AnalysisResult(
                classification="contradictory",
                confidence_score=30,
                extracted_claims=_split_claims(answer),
                evidence_status="needs_clarification",
                follow_up_needed=True,
                follow_up_question=(
                    "Your uploaded report appears to be a SOC 2 Type I audit, but your "
                    "answer states Type II. Can you clarify, or provide an updated Type II report?"
                ),
            )

        strong_hits = sum(1 for m in _STRONG_MARKERS if m in answer_lower)
        weak_hits = sum(1 for m in _WEAK_MARKERS if m in answer_lower)
        score_points = strong_hits * 2 - weak_hits
        if len(answer) > 40:
            score_points += 1

        has_evidence = len(evidence) > 0
        if question.evidence_required and not has_evidence:
            # Self-reported claims without evidence are capped at Weak,
            # matching the system prompt's explicit strictness rule.
            score_points = min(score_points, 0)

        if score_points >= 3:
            classification, confidence = "strong", 88.0
        elif score_points >= 1:
            classification, confidence = "adequate", 65.0
        else:
            classification, confidence = "weak", 35.0

        evidence_status = (
            "verified" if (has_evidence or not question.evidence_required) else "unverified"
        )
        follow_up_needed = classification in ("weak", "missing")
        follow_up_question = None
        if follow_up_needed and question.evidence_required and not has_evidence:
            follow_up_question = f"Can you provide supporting evidence (document/screenshot) for: {question.prompt}"
        elif follow_up_needed:
            follow_up_question = f"Can you provide more detail on: {question.prompt}"

        return AnalysisResult(
            classification=classification,
            confidence_score=confidence,
            extracted_claims=_split_claims(answer),
            evidence_status=evidence_status,
            follow_up_needed=follow_up_needed,
            follow_up_question=follow_up_question,
        )


class AnthropicLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic  # lazy import: not required for mock mode

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def analyze(
        self, question: QuestionContext, raw_answer: str, evidence: list[EvidenceContext]
    ) -> AnalysisResult:
        evidence_desc = ", ".join(f"{e.document_type} ({e.original_filename})" for e in evidence) or "none"
        user_prompt = f"""Analyze this vendor security assessment answer.

Question: {question.prompt}
Control this question maps to: {question.control_title or "unspecified"}
Scoring rubric: {json.dumps(question.scoring_rubric or {})}
Evidence uploaded by vendor: {evidence_desc}

Vendor's answer:
\"\"\"{raw_answer}\"\"\"

Return ONLY a JSON object with exactly these keys:
- classification: one of "strong", "adequate", "weak", "missing", "contradictory"
- confidence_score: number 0-100
- extracted_claims: array of short strings, key statements extracted from the answer
- evidence_status: one of "verified", "unverified", "needs_clarification", "rejected"
- follow_up_needed: boolean
- follow_up_question: string or null
"""
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        data = _extract_json(text)
        return AnalysisResult(
            classification=data["classification"] if data.get("classification") in VALID_CLASSIFICATIONS else "weak",
            confidence_score=float(data.get("confidence_score", 0)),
            extracted_claims=list(data.get("extracted_claims", []))[:10],
            evidence_status=data["evidence_status"] if data.get("evidence_status") in VALID_EVIDENCE_STATUS else "unverified",
            follow_up_needed=bool(data.get("follow_up_needed", False)),
            follow_up_question=data.get("follow_up_question"),
        )


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        logger.error("Could not parse LLM response as JSON: %s", text)
        raise


_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is not None:
        return _provider
    settings = get_settings()
    if settings.llm_provider == "live" and settings.anthropic_api_key:
        _provider = AnthropicLLMProvider(settings.anthropic_api_key, settings.anthropic_model)
    else:
        _provider = MockLLMProvider()
    return _provider
