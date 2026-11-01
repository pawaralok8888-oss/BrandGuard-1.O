"""Shape tests for the vision reply. Needs pydantic (installed in the project venv)."""
import pytest
from pydantic import ValidationError

from app.ai.vision_schemas import VisionOutput


def test_valid_reply_parses():
    out = VisionOutput.model_validate({
        "facts": [{"id": "F1", "kind": "text", "value": "SPF 50", "bbox": [0.1, 0.2, 0.3, 0.05], "confidence": 0.9}],
        "findings": [{"factIds": ["F1"], "type": "claim", "severity": "critical", "title": "Claim",
                      "quote": "SPF 50", "reason": "r", "guidelineId": "G-012",
                      "suggestedFix": "f", "confidence": 0.8}],
        "notFound": ["IF-011"],
    })
    assert out.facts[0].id == "F1"
    assert out.findings[0].guidelineId == "G-012"
    assert out.notFound == ["IF-011"]


def test_missing_sections_default_to_empty():
    out = VisionOutput.model_validate({})
    assert out.facts == [] and out.findings == [] and out.notFound == []


def test_unknown_keys_are_ignored():
    out = VisionOutput.model_validate({"facts": [], "extra": "ignored", "findings": []})
    assert out.facts == []


def test_one_odd_confidence_does_not_reject_the_reply():
    out = VisionOutput.model_validate({"facts": [{"id": "F1", "confidence": "high"}], "findings": []})
    assert out.facts[0].confidence == "high"  # safeguards decide what to do with it


def test_wrong_top_level_structure_is_rejected():
    with pytest.raises(ValidationError):
        VisionOutput.model_validate({"facts": "not a list"})
    with pytest.raises(ValidationError):
        VisionOutput.model_validate({"notFound": [1, 2]})
