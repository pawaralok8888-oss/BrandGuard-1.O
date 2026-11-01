"""Confidential pre-scan tests. Pure: uses the existing redaction matcher, no database."""
from app.services.prescan import scan_for_confidential


def test_no_terms_means_proceed():
    assert scan_for_confidential(["Project Nightingale launch"], []) == {"decision": "proceed", "matches": 0}


def test_term_in_body_holds():
    result = scan_for_confidential(["Our new Project Nightingale campaign"], ["Project Nightingale"])
    assert result == {"decision": "hold", "matches": 1}


def test_case_insensitive_and_whole_word_only():
    assert scan_for_confidential(["PROJECT NIGHTINGALE"], ["project nightingale"])["decision"] == "hold"
    assert scan_for_confidential(["Nightingales are birds"], ["Nightingale"])["decision"] == "proceed"


def test_match_in_any_text_part_counts():
    texts = ["clean body", "file: nightingale_banner.png", "OCR: Project Nightingale"]
    assert scan_for_confidential(texts, ["Project Nightingale"])["matches"] == 1


def test_short_terms_are_ignored():
    assert scan_for_confidential(["an ox"], ["ox"]) == {"decision": "proceed", "matches": 0}


def test_result_never_contains_the_term_or_text():
    result = scan_for_confidential(["secret Project Nightingale plan"], ["Project Nightingale"])
    assert "Nightingale" not in str(result)
    assert set(result) == {"decision", "matches"}
