"""Redaction of confidential terms before the model call (plan step 6).

The first group needs only the standard library. The second group checks the AI stage
end to end with the model and database replaced by stubs, so no network is used.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.pipeline.redact import MASK_CHAR, mask_text, normalise_terms, terms_digest


# ---- pure redaction -------------------------------------------------------

def test_masked_text_has_the_same_length_so_offsets_still_match():
    text = "Our Project Nightingale formula is new."
    masked, hits = mask_text(text, ["Project Nightingale"])
    assert hits == 1
    assert len(masked) == len(text)
    assert masked == "Our " + MASK_CHAR * len("Project Nightingale") + " formula is new."


def test_matching_is_case_insensitive():
    masked, hits = mask_text("NIGHTINGALE and nightingale", ["Nightingale"])
    assert hits == 2
    assert "Nightingale" not in masked.lower()


def test_term_inside_a_longer_word_is_not_masked():
    masked, hits = mask_text("Glowing skin, not a glow-up", ["Glow"])
    assert hits == 1  # 'glow-up' is masked, 'Glowing' is not (a word character follows)
    assert masked.startswith("Glowing")


def test_longest_term_wins_when_terms_overlap():
    masked, hits = mask_text("Project Nightingale launch", ["Nightingale", "Project Nightingale"])
    assert hits == 1
    assert masked == MASK_CHAR * len("Project Nightingale") + " launch"


def test_short_terms_are_ignored_so_ordinary_words_are_not_masked():
    assert normalise_terms(["ab", "  ", None, "Nightingale"]) == ["Nightingale"]
    masked, hits = mask_text("an ab test", ["ab"])
    assert hits == 0 and masked == "an ab test"


def test_duplicate_terms_are_removed_case_insensitively():
    assert normalise_terms(["Nightingale", "nightingale", "NIGHTINGALE"]) == ["Nightingale"]


def test_no_terms_returns_text_unchanged():
    assert mask_text("plain text", []) == ("plain text", 0)


def test_terms_digest_changes_when_the_list_changes():
    assert terms_digest(["Nightingale"]) != terms_digest(["Nightingale", "Helix"])
    assert terms_digest(["Nightingale"]) == terms_digest(["nightingale "])


# ---- AI stage: the term never reaches the model -----------------------------

POST = "Project Nightingale gives 100% clear skin. Dermatologically tested."


def _stub_stage(monkeypatch, captured: dict, evidence_text: str):
    from app.ai import client as ai_client
    from app.services import ai_check

    monkeypatch.setattr(ai_check, "get_settings", lambda: SimpleNamespace(brandguard_model="test-model"))
    monkeypatch.setattr(ai_check, "get_evidence", lambda conn, channel, **kwargs: [
        {"source_id": "F-001", "version": 1, "text": evidence_text, "kind": "fact"},
        {"source_id": "G-001", "version": 1, "text": "No absolute claims", "kind": "guideline"},
    ])
    monkeypatch.setattr(ai_check, "_read_cache", lambda conn, key: None)
    monkeypatch.setattr(ai_check, "_write_cache", lambda conn, key, output: None)

    def fake_call_llm(system, user, schema):
        captured["user"] = user
        return ai_client.CallResult(
            output=schema.model_validate({"findings": []}),
            model="test-model", latency_ms=1, input_tokens=0, output_tokens=0,
        )

    monkeypatch.setattr(ai_check, "call_llm", fake_call_llm)
    return ai_check


def test_confidential_term_is_not_sent_to_the_model(monkeypatch):
    captured: dict = {}
    ai_check = _stub_stage(monkeypatch, captured,
                           evidence_text="Project Nightingale is unreleased. Serum is 30 ml.")

    stage = ai_check.run_ai_stage(object(), POST, "instagram", [],
                                  confidential_terms=["Project Nightingale"])

    assert stage.status == "success"
    assert "Project Nightingale" not in captured["user"]
    assert "Nightingale" not in captured["user"]
    assert MASK_CHAR in captured["user"]
    assert "Serum is 30 ml." in captured["user"]  # non-confidential evidence still reaches the model
    assert stage.redacted == 2  # one in the post, one in the evidence


def test_quote_that_hits_masked_text_is_dropped_not_misplaced(monkeypatch):
    """A model quote that contains a mask character cannot match the original post."""
    from app.ai import client as ai_client
    from app.ai.schemas import AIOutput
    from app.services import ai_check

    captured: dict = {}
    ai_check_mod = _stub_stage(monkeypatch, captured, evidence_text="Serum is 30 ml.")

    def bad_reply(system, user, schema):
        quote = MASK_CHAR * len("Project Nightingale") + " gives 100% clear skin."
        return ai_client.CallResult(
            output=AIOutput.model_validate({"findings": [{
                "quote": quote, "source_id": "G-001", "severity": "critical",
                "title": "Absolute claim", "reason": "Absolute claim.",
                "suggested_fix": "Helps skin look clearer.", "suggestion_kind": "Claim correction",
                "confidence": 0.9,
            }]}),
            model="test-model", latency_ms=1, input_tokens=0, output_tokens=0,
        )

    monkeypatch.setattr(ai_check_mod, "call_llm", bad_reply)
    stage = ai_check_mod.run_ai_stage(object(), POST, "instagram", [],
                                      confidential_terms=["Project Nightingale"])
    assert stage.findings == []
    assert stage.dropped == 1


def test_changing_the_term_list_changes_the_cache_key(monkeypatch):
    captured: dict = {}
    ai_check = _stub_stage(monkeypatch, captured, evidence_text="Serum is 30 ml.")
    keys = []
    monkeypatch.setattr(ai_check, "_read_cache", lambda conn, key: keys.append(key) or None)

    ai_check.run_ai_stage(object(), POST, "instagram", [], confidential_terms=["Project Nightingale"])
    ai_check.run_ai_stage(object(), POST, "instagram", [], confidential_terms=["Project Nightingale", "Helix"])
    assert keys[0] != keys[1]
