"""Automated risk scoring (Phase 1 §4).

Scoring model, made explicit rather than left as a black box:

1. Each analyzed response gets a 0-100 "compliance strength" score from its
   classification, using the exact scoring-matrix values in the Phase 1
   spec's MFA example (Strong=100, Adequate=70, Weak=40, Missing=0).
   `contradictory` scores 0 — an unresolved inconsistency is worse than an
   honestly-reported gap.
2. Responses to evidence-required questions are weighted 2x when rolling up
   to control/assessment scores — those are the higher-stakes controls the
   spec calls out (MFA, encryption, audit logging), and a template author
   marks that by setting `evidence_required` on the question.
3. Per-control score = weighted average of every response mapped to that
   control_id within the assessment.
4. Per-framework score = average of that framework's control scores that
   were actually touched by this assessment (see the caveat below).
5. `overall_score` (compliance strength, higher = better) is the weighted
   average across all responses.
6. `vendor_risk_score` (risk exposure, higher = worse) is the metric the
   rest of the platform uses everywhere else (Phase 2 alert deltas, the
   Green/Yellow/Red dashboard bands from the Phase 2 spec) — it starts as
   `100 - overall_score` at assessment completion and later phases add
   monitoring-alert deltas on top of that baseline.

Caveat on framework coverage: this only scores controls the assessment's
questionnaire actually maps to, not the full framework catalog — an
accurate "% of NIST CSF covered" figure needs the complete control catalog
loaded, which is a data-completeness task, not a scoring-logic one.
"""

from dataclasses import dataclass

CLASSIFICATION_SCORES: dict[str, float] = {
    "strong": 100.0,
    "adequate": 70.0,
    "weak": 40.0,
    "missing": 0.0,
    "contradictory": 0.0,
}

EVIDENCE_REQUIRED_WEIGHT = 2.0
DEFAULT_WEIGHT = 1.0


@dataclass
class ScoredResponse:
    question_id: str
    classification: str | None
    evidence_required: bool
    control_id: str | None
    control_ref: str | None
    control_title: str | None
    framework_id: str | None
    framework_code: str | None


def _weight(r: ScoredResponse) -> float:
    return EVIDENCE_REQUIRED_WEIGHT if r.evidence_required else DEFAULT_WEIGHT


def _score(r: ScoredResponse) -> float:
    if r.classification is None:
        return 0.0
    return CLASSIFICATION_SCORES.get(r.classification, 0.0)


def compute_risk_breakdown(responses: list[ScoredResponse]) -> dict:
    classification_counts: dict[str, int] = {}
    for r in responses:
        key = r.classification or "unanalyzed"
        classification_counts[key] = classification_counts.get(key, 0) + 1

    total_weight = sum(_weight(r) for r in responses) or 1.0
    overall_score = sum(_score(r) * _weight(r) for r in responses) / total_weight

    control_groups: dict[str, list[ScoredResponse]] = {}
    for r in responses:
        if r.control_id:
            control_groups.setdefault(r.control_id, []).append(r)

    control_scores = []
    for control_id, group in control_groups.items():
        w = sum(_weight(r) for r in group) or 1.0
        control_score = sum(_score(r) * _weight(r) for r in group) / w
        sample = group[0]
        control_scores.append({
            "control_id": control_id,
            "control_ref": sample.control_ref,
            "control_title": sample.control_title,
            "framework_code": sample.framework_code,
            "score": round(control_score, 1),
            "question_count": len(group),
        })

    framework_groups: dict[str, list[dict]] = {}
    for cs in control_scores:
        code = cs["framework_code"] or "unmapped"
        framework_groups.setdefault(code, []).append(cs)
    framework_scores = {
        code: round(sum(c["score"] for c in group) / len(group), 1)
        for code, group in framework_groups.items()
    }

    overall_score = round(overall_score, 1)
    vendor_risk_score = round(100.0 - overall_score, 1)

    return {
        "overall_score": overall_score,
        "vendor_risk_score": vendor_risk_score,
        "classification_counts": classification_counts,
        "control_scores": sorted(control_scores, key=lambda c: c["score"]),
        "framework_scores": framework_scores,
    }
