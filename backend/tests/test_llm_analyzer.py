import pytest

from app.services.llm_analyzer import EvidenceContext, MockLLMProvider, QuestionContext


@pytest.fixture
def provider():
    return MockLLMProvider()


async def test_empty_answer_is_missing(provider):
    q = QuestionContext(prompt="Do you use MFA?", control_title=None, scoring_rubric=None, evidence_required=False)
    result = await provider.analyze(q, "", [])
    assert result.classification == "missing"
    assert result.confidence_score == 0
    assert result.follow_up_needed is True


async def test_soc2_type_mismatch_is_contradictory(provider):
    """Reproduces the exact Phase 1 spec walkthrough: vendor answer claims
    SOC 2 Type II, but the uploaded report is Type I."""
    q = QuestionContext(prompt="Describe encryption in transit.", control_title="Encryption",
                         scoring_rubric=None, evidence_required=True)
    evidence = [EvidenceContext(document_type="soc2_type1", original_filename="soc2-report.pdf")]
    result = await provider.analyze(q, "We are SOC 2 Type II certified for all data in transit.", evidence)
    assert result.classification == "contradictory"
    assert result.evidence_status == "needs_clarification"
    assert "Type I" in result.follow_up_question and "Type II" in result.follow_up_question


async def test_strong_answer_with_evidence_scores_strong(provider):
    q = QuestionContext(prompt="MFA?", control_title="Access", scoring_rubric=None, evidence_required=True)
    evidence = [EvidenceContext(document_type="screenshot", original_filename="mfa.png")]
    answer = ("MFA is enforced org-wide for all systems, phishing-resistant methods are "
              "required, and our incident response plan has been tested.")
    result = await provider.analyze(q, answer, evidence)
    assert result.classification == "strong"
    assert result.follow_up_needed is False


async def test_evidence_required_but_not_provided_caps_at_weak(provider):
    """The system prompt's strictness rule made concrete: a well-written,
    keyword-rich answer with no evidence still can't score above Weak on a
    question that requires evidence."""
    q = QuestionContext(prompt="MFA?", control_title="Access", scoring_rubric=None, evidence_required=True)
    answer = "MFA is enforced org-wide for all systems, phishing-resistant, tested annually."
    result = await provider.analyze(q, answer, [])
    assert result.classification == "weak"
    assert result.evidence_status == "unverified"


async def test_weak_hedging_language_scores_weak(provider):
    q = QuestionContext(prompt="Backup testing?", control_title=None, scoring_rubric=None, evidence_required=False)
    result = await provider.analyze(q, "Not sure, we're working on it, no formal process yet.", [])
    assert result.classification == "weak"
    assert result.follow_up_needed is True
