"""Pure-logic tests for phase 2 safeguards. No database, no model, no network."""
from app.services.vision_safeguards import (
    MAX_CALLS_PER_SUBMISSION,
    REVIEW_BELOW,
    BudgetExceeded,
    CallBudget,
    apply_safeguards,
    clamp_confidence,
    decide_route,
    quote_in_text,
    valid_bbox,
)

ALLOWED = {"G-012", "G-021"}
TEXT = "Protect your skin with up to 2 hours of water resistance."


def _output(findings, facts=None):
    return {
        "facts": facts if facts is not None else [
            {"id": "F1", "kind": "text", "value": "SPF 50", "bbox": [0.1, 0.2, 0.3, 0.05], "confidence": 0.9},
            {"id": "F2", "kind": "logo", "value": "logo", "bbox": [0.7, 0.05, 0.2, 0.1], "confidence": 0.8},
        ],
        "findings": findings,
        "notFound": [],
    }


def _text_claim(**over):
    base = {"type": "claim", "severity": "critical", "title": "Claim", "reason": "r", "suggestedFix": "f",
            "guidelineId": "G-012", "factIds": ["F1"], "quote": "up to 2 hours", "confidence": 0.9}
    base.update(over)
    return base


def _visual(**over):
    base = {"type": "visual", "severity": "warning", "title": "Logo small", "reason": "r", "suggestedFix": "f",
            "guidelineId": "G-021", "factIds": ["F2"], "confidence": 0.7}
    base.update(over)
    return base


# bbox
def test_valid_bbox_accepted():
    assert valid_bbox([0.1, 0.2, 0.3, 0.4]) == [0.1, 0.2, 0.3, 0.4]


def test_bbox_out_of_range_rejected():
    assert valid_bbox([1.2, 0, 0.1, 0.1]) is None
    assert valid_bbox([0, 0, 0, 0.1]) is None  # zero width
    assert valid_bbox([0, 0, 0.1]) is None  # wrong length


def test_bbox_nan_and_text_rejected():
    assert valid_bbox([float("nan"), 0, 0.1, 0.1]) is None
    assert valid_bbox(["a", 0, 0.1, 0.1]) is None
    assert valid_bbox(None) is None


# quotes and confidence
def test_quote_must_appear_exactly():
    assert quote_in_text("up to 2 hours", TEXT)
    assert not quote_in_text("all day", TEXT)
    assert not quote_in_text("", TEXT)


def test_confidence_clamped_and_bad_values_rejected():
    assert clamp_confidence(1.7) == 1.0
    assert clamp_confidence(-0.2) == 0.0
    assert clamp_confidence("high") is None
    assert clamp_confidence(float("nan")) is None


# route decision
def test_confidential_match_holds_before_any_model_call():
    assert decide_route(1) == "hold"
    assert decide_route(0) == "proceed"


# budget
def test_budget_allows_limit_then_stops():
    budget = CallBudget(limit=2)
    budget.consume()
    budget.consume()
    assert budget.remaining == 0
    try:
        budget.consume()
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("expected BudgetExceeded")


def test_default_budget_matches_contract():
    assert CallBudget().limit == MAX_CALLS_PER_SUBMISSION == 10


# safeguards
def test_valid_text_claim_is_kept_as_claim():
    kept, dropped = apply_safeguards(_output([_text_claim()]), ALLOWED, TEXT)
    assert dropped == {}
    assert kept[0]["type"] == "claim"
    assert kept[0]["originalText"] == "up to 2 hours"
    assert kept[0]["bbox"] is None
    assert kept[0]["needsHumanReview"] is False


def test_unknown_guideline_dropped():
    _, dropped = apply_safeguards(_output([_text_claim(guidelineId="G-999")]), ALLOWED, TEXT)
    assert dropped == {"unknown_guideline": 1}


def test_missing_fact_dropped():
    _, dropped = apply_safeguards(_output([_text_claim(factIds=[])]), ALLOWED, TEXT)
    assert dropped == {"no_fact": 1}


def test_fact_not_in_response_dropped():
    _, dropped = apply_safeguards(_output([_text_claim(factIds=["F9"])]), ALLOWED, TEXT)
    assert dropped == {"unknown_fact": 1}


def test_text_quote_not_in_post_dropped():
    _, dropped = apply_safeguards(_output([_text_claim(quote="all day protection")]), ALLOWED, TEXT)
    assert dropped == {"quote_not_found": 1}


def test_low_confidence_dropped():
    _, dropped = apply_safeguards(_output([_text_claim(confidence=0.1)]), ALLOWED, TEXT)
    assert dropped == {"low_confidence": 1}


def test_visual_finding_takes_fact_bbox_and_needs_review():
    kept, dropped = apply_safeguards(_output([_visual(confidence=0.95)]), ALLOWED, TEXT)
    assert dropped == {}
    assert kept[0]["type"] == "image"
    assert kept[0]["bbox"] == [0.7, 0.05, 0.2, 0.1]
    assert kept[0]["needsHumanReview"] is True  # visual findings always need review


def test_visual_finding_with_bad_fact_bbox_becomes_whole_image():
    facts = [{"id": "F2", "kind": "logo", "value": "logo", "bbox": [1.5, 0, 0.2, 0.1], "confidence": 0.8}]
    kept, _ = apply_safeguards(_output([_visual()], facts=facts), ALLOWED, TEXT)
    assert kept[0]["bbox"] is None


def test_low_confidence_text_is_kept_for_review():
    kept, _ = apply_safeguards(_output([_text_claim(confidence=0.45)]), ALLOWED, TEXT)
    assert kept[0]["needsHumanReview"] is True
    assert 0.45 < REVIEW_BELOW


def test_unknown_type_and_malformed_dropped():
    out = _output([_text_claim(type="mystery"), "not a dict"])
    kept, dropped = apply_safeguards(out, ALLOWED, TEXT)
    assert kept == []
    assert dropped == {"unknown_type": 1, "malformed": 1}


def test_terminology_maps_to_rule_type():
    kept, _ = apply_safeguards(_output([_text_claim(type="terminology", quote="water resistance")]), ALLOWED, TEXT)
    assert kept[0]["type"] == "rule"


def test_mixed_response_keeps_good_and_counts_bad():
    out = _output([_text_claim(), _text_claim(guidelineId="G-999"), _visual()])
    kept, dropped = apply_safeguards(out, ALLOWED, TEXT)
    assert [k["type"] for k in kept] == ["claim", "image"]
    assert dropped == {"unknown_guideline": 1}
