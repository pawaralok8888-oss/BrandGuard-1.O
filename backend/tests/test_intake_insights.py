"""Pure-logic tests for approved insights in the intake gap report and for insight chunking.

No database needed. Database and endpoint tests belong in test_intake_documents.py.
"""
from app.services.guideline_insights import (
    CHUNK_CHARS,
    MAX_SINGLE_CALL_CHARS,
    fields_needing_second_pass,
    is_placeholder,
    split_text,
)
from app.services.intake import build_gap_report, field_status


def _row(field_id, coverage_check="manual", required=True, response_status=None, category="brand_identity"):
    return {
        "id": field_id,
        "label": field_id,
        "description": "",
        "required": required,
        "coverage_check": coverage_check,
        "response_status": response_status,
        "response_note": None,
        "category_id": category,
        "category_label": category,
    }


def test_approved_insight_covers_manual_field():
    assert field_status("manual", False, None, insight_found=True) == "covered"


def test_no_insight_and_no_data_is_gap():
    assert field_status("manual", False, None, insight_found=False) == "gap"


def test_manual_answer_beats_approved_insight():
    assert field_status("manual", False, "provided", insight_found=True) == "provided"
    assert field_status("logo", True, "not_applicable", insight_found=True) == "not_applicable"


def test_existing_behaviour_unchanged_without_insight():
    assert field_status("logo", True, None) == "covered"
    assert field_status("logo", False, None) == "gap"
    assert field_status("manual", True, None) == "gap"  # manual fields never count coverage data


def test_gap_report_counts_approved_insights_per_field():
    rows = [_row("IF-004"), _row("IF-005", coverage_check="product_list", category="products")]
    report = build_gap_report(rows, counts={"product_list": 0}, insight_counts={"IF-004": 2})
    fields = {f["id"]: f for c in report["categories"] for f in c["fields"]}
    assert fields["IF-004"]["status"] == "covered"
    assert fields["IF-004"]["approvedInsightCount"] == 2
    assert fields["IF-005"]["status"] == "gap"
    assert fields["IF-005"]["approvedInsightCount"] == 0
    assert report["summary"]["covered"] == 1
    assert report["summary"]["requiredGaps"] == 1


def test_gap_report_without_insight_argument_still_works():
    rows = [_row("IF-004")]
    report = build_gap_report(rows, counts={})
    assert report["categories"][0]["fields"][0]["status"] == "gap"
    assert report["categories"][0]["fields"][0]["approvedInsightCount"] == 0


def test_short_text_is_one_chunk():
    assert split_text("short") == ["short"]


def test_long_text_is_split_into_chunks_that_cover_everything():
    text = "x" * (MAX_SINGLE_CALL_CHARS + 1)
    chunks = split_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    assert "".join(chunks) == text


def test_placeholder_detected_in_source_text():
    assert is_placeholder("Reapplication: [PLACEHOLDER: interval].")
    assert is_placeholder("[placeholder: colour]")
    assert not is_placeholder("Reapply every two hours.")


def test_second_pass_asks_only_about_unanswered_fields_not_listed_as_missing():
    fields = [{"id": "IF-012"}, {"id": "IF-013"}, {"id": "IF-014"}]
    missing = fields_needing_second_pass(fields, answered_ids={"IF-012"}, not_found_ids={"IF-014"})
    assert [f["id"] for f in missing] == ["IF-013"]


def test_second_pass_empty_when_every_field_is_answered_or_missing():
    fields = [{"id": "IF-012"}, {"id": "IF-013"}]
    assert fields_needing_second_pass(fields, {"IF-012"}, {"IF-013"}) == []
