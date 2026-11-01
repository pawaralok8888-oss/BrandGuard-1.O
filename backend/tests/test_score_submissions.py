"""Tests for the evaluation scorer. Pure: small in-memory manifest, no files."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "score_submissions.py"
_spec = importlib.util.spec_from_file_location("score_submissions", _path)
scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)

MANIFEST = {"submissions": [
    {"id": "S1", "kind": "script", "holdExpected": False, "expected": []},
    {"id": "S2", "kind": "script", "holdExpected": False,
     "expected": [{"guidelineId": "G-001", "mustMention": ["all wrinkles"]}]},
    {"id": "M3", "kind": "marketing_idea", "holdExpected": True, "expected": []},
]}


def test_perfect_run_scores_100():
    results = {
        "S1": {"status": "ready", "findings": []},
        "S2": {"status": "ready", "findings": [{"guidelineId": "G-001", "title": "Claim",
                                               "originalText": "removes all wrinkles"}]},
        "M3": {"status": "held", "findings": []},
    }
    report = scorer.score(MANIFEST, results)
    assert report["recall_percent"] == 100.0
    assert report["precision_percent"] == 100.0
    assert report["holds"] == {"expected": 1, "correct": 1, "wrong": 0}
    assert report["missed"] == []


def test_missed_problem_and_wrong_phrase_lower_recall():
    results = {"S2": {"status": "ready", "findings": [{"guidelineId": "G-001", "title": "Claim",
                                                       "originalText": "guaranteed"}]}}
    report = scorer.score(MANIFEST, results)
    assert report["recall_percent"] == 0.0
    assert any("G-001 not found" in m for m in report["missed"])


def test_extra_finding_on_clean_submission_is_a_false_positive():
    results = {"S1": {"status": "ready", "findings": [{"guidelineId": "G-002", "title": "Superlative"}]}}
    report = scorer.score(MANIFEST, results)
    assert report["total"]["false_positives"] == 1
    assert report["false_positive_rate_percent"] == 100.0


def test_unheld_confidential_and_wrong_hold_are_counted():
    results = {
        "M3": {"status": "ready", "findings": []},
        "S1": {"status": "held", "findings": []},
    }
    report = scorer.score(MANIFEST, results)
    assert report["holds"]["wrong"] == 2
    assert report["holds"]["correct"] == 0


def test_missing_results_count_as_misses():
    report = scorer.score(MANIFEST, {})
    assert report["recall_percent"] == 0.0
    assert report["holds"]["wrong"] == 1  # M3 expected a hold and got none


def test_no_expected_items_gives_no_recall_percentage():
    report = scorer.score({"submissions": [{"id": "X", "kind": "image", "holdExpected": False, "expected": []}]}, {})
    assert report["recall_percent"] is None
