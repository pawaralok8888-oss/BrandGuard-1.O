"""Pure tests for mapping findings to table rows. No database."""
import pytest

from app.services.findings_mapper import MappingError, to_finding_row, to_finding_rows

TEXT = "Protect your skin up to 2 hours of water resistance."


def _finding(**over):
    base = {
        "type": "claim", "severity": "critical", "title": "Claim", "reason": "Needs evidence.",
        "suggestedFix": "Say up to 2 hours.", "sourceId": "G-012", "originalText": "up to 2 hours",
        "bbox": None, "confidence": 0.8, "aiGenerated": True, "needsHumanReview": False,
        "attachmentIds": ["ATT-0001"],
    }
    base.update(over)
    return base


def _map(finding, **kw):
    return to_finding_row(finding, content_id="CNT-1", check_run_id="CR-1",
                          visible_text=TEXT, known_guideline_versions={"G-012": 3}, **kw)


def test_text_claim_maps_to_claim_row_with_offsets_and_version():
    row, attachments = _map(_finding())
    assert row["type"] == "claim"
    assert row["suggestion_kind"] == "Claim correction"
    assert row["guideline_id"] == "G-012"
    assert row["source_version"] == 3
    assert row["start"] == TEXT.index("up to 2 hours")
    assert row["end"] == row["start"] + len("up to 2 hours")
    assert row["status"] == "open"
    assert attachments == ["ATT-0001"]


def test_visual_finding_keeps_bbox_and_needs_review():
    f = _finding(type="image", title="Logo small", originalText="", bbox=[0.7, 0.05, 0.2, 0.1],
                 needsHumanReview=True, sourceId="G-021")
    row, _ = to_finding_row(f, content_id="CNT-1", check_run_id=None, visible_text=TEXT,
                            known_guideline_versions={"G-021": 1})
    assert row["type"] == "image"
    assert row["suggestion_kind"] == "Visual suggestion"
    assert row["bbox"] == [0.7, 0.05, 0.2, 0.1]
    assert row["start"] is None and row["end"] is None
    assert row["original_text"] is None
    assert row["needs_human_review"] is True


def test_invalid_bbox_becomes_null_not_an_error():
    row, _ = _map(_finding(type="image", originalText="", bbox=[2, 0, 0.1, 0.1]))
    assert row["bbox"] is None


def test_confidential_finding_has_no_guideline_and_uses_allowed_kind():
    f = _finding(type="security", title="Confidential term detected", sourceId="confidential-terms",
                 originalText="", severity="critical", needsHumanReview=True, aiGenerated=False)
    row, _ = _map(f)
    assert row["type"] == "security"
    assert row["guideline_id"] is None
    assert row["source_id"] == "confidential-terms"
    assert row["suggestion_kind"] == "Terminology change"
    assert row["ai_generated"] is False


def test_unknown_guideline_source_is_stored_without_foreign_key():
    row, _ = _map(_finding(sourceId="G-999"))
    assert row["guideline_id"] is None
    assert row["source_version"] == 1


def test_offset_is_null_when_quote_not_found_in_visible_text():
    row, _ = _map(_finding(originalText="not in the text"))
    assert row["start"] is None and row["end"] is None


def test_confidence_is_clamped_and_rounded():
    assert _map(_finding(confidence=1.7))[0]["confidence"] == 1.0
    assert _map(_finding(confidence=0.123456))[0]["confidence"] == 0.123


def test_bad_type_and_bad_confidence_are_refused():
    with pytest.raises(MappingError):
        _map(_finding(type="mystery"))
    with pytest.raises(MappingError):
        _map(_finding(confidence="high"))


def test_unknown_severity_becomes_warning():
    assert _map(_finding(severity="urgent"))[0]["severity"] == "warning"


def test_long_title_is_cut_and_empty_reason_gets_default():
    row, _ = _map(_finding(title="x" * 500, reason=""))
    assert len(row["title"]) == 200
    assert row["reason"] == "No reason given."


def test_every_row_has_only_known_columns():
    row, _ = _map(_finding())
    assert set(row) == {
        "content_id", "check_run_id", "type", "start", "end", "bbox", "severity", "title", "reason",
        "source_id", "source_version", "guideline_id", "suggested_fix", "original_text", "confidence",
        "ai_generated", "needs_human_review", "status", "suggestion_kind",
    }


def test_many_findings_map_in_order():
    rows = to_finding_rows([_finding(), _finding(type="tone", title="Tone")], content_id="CNT-1",
                           check_run_id="CR-1", visible_text=TEXT, known_guideline_versions={"G-012": 3})
    assert [r[0]["type"] for r in rows] == ["claim", "tone"]
