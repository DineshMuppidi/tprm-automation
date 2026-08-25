from app.services.risk_scoring import ScoredResponse, compute_risk_breakdown


def _resp(classification, evidence_required=False, control_id=None, control_ref=None,
          control_title=None, framework_id=None, framework_code=None):
    return ScoredResponse(
        question_id="q", classification=classification, evidence_required=evidence_required,
        control_id=control_id, control_ref=control_ref, control_title=control_title,
        framework_id=framework_id, framework_code=framework_code,
    )


def test_classification_scores_and_overall():
    responses = [_resp("strong"), _resp("adequate"), _resp("weak"), _resp("missing")]
    result = compute_risk_breakdown(responses)
    assert result["overall_score"] == (100 + 70 + 40 + 0) / 4
    assert result["vendor_risk_score"] == round(100 - result["overall_score"], 1)
    assert result["classification_counts"] == {"strong": 1, "adequate": 1, "weak": 1, "missing": 1}


def test_contradictory_scores_zero():
    result = compute_risk_breakdown([_resp("contradictory")])
    assert result["overall_score"] == 0.0


def test_evidence_required_questions_are_weighted_double():
    # A missing evidence-required response (weight 2) should drag the
    # average down further than the same gap on a non-evidence-required one.
    heavy = compute_risk_breakdown([_resp("strong"), _resp("missing", evidence_required=True)])
    light = compute_risk_breakdown([_resp("strong"), _resp("missing", evidence_required=False)])
    assert heavy["overall_score"] < light["overall_score"]


def test_control_and_framework_aggregation():
    responses = [
        _resp("strong", control_id="c1", control_ref="PR.AC-1", control_title="Access",
              framework_id="f1", framework_code="NIST_CSF_2"),
        _resp("weak", control_id="c1", control_ref="PR.AC-1", control_title="Access",
              framework_id="f1", framework_code="NIST_CSF_2"),
        _resp("adequate", control_id="c2", control_ref="PR.DS-1", control_title="Encryption",
              framework_id="f1", framework_code="NIST_CSF_2"),
    ]
    result = compute_risk_breakdown(responses)
    scores_by_control = {c["control_ref"]: c["score"] for c in result["control_scores"]}
    assert scores_by_control["PR.AC-1"] == 70.0   # (100 + 40) / 2
    assert scores_by_control["PR.DS-1"] == 70.0
    assert result["framework_scores"]["NIST_CSF_2"] == 70.0


def test_unmapped_responses_excluded_from_control_scores():
    result = compute_risk_breakdown([_resp("strong", control_id=None)])
    assert result["control_scores"] == []
    assert result["framework_scores"] == {}
