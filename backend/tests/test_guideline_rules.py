"""Uploaded guidelines become draft rules: extraction, saved as inactive, and approved by a manager.

The sample guideline in test_data is the real example from the project. The route tests use a
fake connection and stub embedding, so no network call is made.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.knowledge as knowledge
from app.db import get_conn
from tests.lookups import lookup_rows
from app.pipeline.guideline_rules import extract_rule_candidates
from app.security import current_user

SAMPLE = Path(__file__).resolve().parents[2] / "test_data" / "guidelines" / "sample_guideline.txt"
MANAGER = {"id": "user-manager", "name": "Priya", "role": "manager"}


# ---------- extraction ----------

def test_sample_guideline_banned_terms_become_phrase_rules_with_replacements():
    result = extract_rule_candidates(SAMPLE.read_text(encoding="utf-8"))
    phrases = {c.pattern: c for c in result.candidates if c.kind == "phrase"}

    assert phrases["miracle"].replacement == "effective"
    assert phrases["cure"].replacement == "treat"
    assert phrases["100% effective"].replacement == "results may vary"
    assert "Alternatives: clinically proven" in phrases["miracle"].note


def test_context_after_a_banned_term_is_kept_as_a_note():
    result = extract_rule_candidates(SAMPLE.read_text(encoding="utf-8"))
    drug = next(c for c in result.candidates if c.pattern == "drug")
    assert drug.note == "in product context"


def test_disclaimer_sentence_becomes_required_text():
    result = extract_rule_candidates(SAMPLE.read_text(encoding="utf-8"))
    required = [c for c in result.candidates if c.kind == "required_text"]
    assert [c.pattern for c in required] == [
        "Results may vary. Individual skin types may respond differently."
    ]
    assert required[0].note == "Applies to: All skincare products"


def test_approved_terminology_is_never_turned_into_a_banned_phrase():
    """Product and company names are under APPROVED TERMINOLOGY, not a prohibitive heading."""
    result = extract_rule_candidates(SAMPLE.read_text(encoding="utf-8"))
    patterns = {c.pattern for c in result.candidates}
    assert "GreenGlow Cleansing Milk" not in patterns
    assert "GreenGlow Skincare" not in patterns
    assert any(line.startswith("Products:") for line in result.unparsed)


def test_single_word_under_disclaimers_is_left_for_a_person():
    result = extract_rule_candidates(SAMPLE.read_text(encoding="utf-8"))
    assert not any(c.pattern == "Dermatologist-tested" for c in result.candidates)
    assert any("Dermatologist-tested" in line for line in result.unparsed)


def test_prose_and_unquoted_bullets_are_unparsed_not_rules():
    text = "AVOID:\n- Before/after photos without consent forms\n- Unverified testimonials\n"
    result = extract_rule_candidates(text)
    assert result.candidates == []
    assert result.unparsed == [
        "Before/after photos without consent forms",
        "Unverified testimonials",
    ]


# ---------- fake connection for the routes ----------

class _Result:
    def __init__(self, row=None, rows=None):
        self._row, self._rows = row, rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class RouteConn:
    def __init__(self, rule_row=None):
        self.calls = []
        self.rule_row = rule_row

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        lookup = lookup_rows(sql)
        if lookup is not None:
            return _Result(rows=lookup)
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO guidelines"):
            return _Result(row={
                "id": params[0], "short_name": params[1], "title": params[2], "text": params[3],
                "category": params[4], "rule_type": params[5], "severity": params[6],
                "applies_to_channels": params[7], "required_text": None, "version": 1,
                "owner_id": params[9], "is_active": True, "updated_at": None,
            })
        if s.startswith("SELECT id FROM rule_patterns"):
            return _Result(rows=[])
        if s.startswith("SELECT kind FROM rule_patterns"):
            return _Result(row=self.rule_row)
        if s.startswith("UPDATE rule_patterns"):
            return _Result(row=self.rule_row)
        return _Result()

    def transaction(self):
        return _Tx()


def _client(conn, monkeypatch):
    app = FastAPI()
    app.include_router(knowledge.router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: MANAGER
    monkeypatch.setattr(knowledge, "index_item", lambda *a, **k: False)  # no network in tests
    return TestClient(app)


def _inserted_rules(conn):
    return [params for sql, params in conn.calls if sql.startswith("INSERT INTO rule_patterns")]


def test_upload_saves_extracted_rules_as_inactive_drafts(monkeypatch):
    conn = RouteConn()
    client = _client(conn, monkeypatch)

    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("sample.txt", SAMPLE.read_bytes(), "text/plain")},
        data={"category": "Terminology"},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["ruleCandidates"] == 5
    assert "Products:" in " ".join(body["unparsedLines"])

    rules = _inserted_rules(conn)
    assert len(rules) == 5
    for params in rules:
        sql_text = " ".join(next(sql for sql, p in conn.calls if p is params).split())
        assert "FALSE)" in sql_text  # is_active is written as FALSE: a draft
        assert params[1] == body["id"]  # linked to the new guideline


def test_upload_with_no_rules_still_succeeds(monkeypatch):
    conn = RouteConn()
    client = _client(conn, monkeypatch)
    res = client.post(
        "/api/knowledge/guidelines/upload",
        files={"file": ("tone.txt", b"Professional but approachable.", "text/plain")},
        data={"category": "Tone of Voice"},
    )
    assert res.status_code == 201
    assert res.json()["ruleCandidates"] == 0
    assert _inserted_rules(conn) == []


def test_manager_can_approve_a_draft_rule(monkeypatch):
    conn = RouteConn(rule_row={
        "id": "RP-010", "guideline_id": "G-002", "kind": "phrase", "pattern": "miracle",
        "replacement": "effective", "note": "", "channel": None, "is_active": True,
    })
    client = _client(conn, monkeypatch)
    res = client.patch("/api/knowledge/rule-patterns/RP-010", json={"is_active": True})
    assert res.status_code == 200
    assert res.json()["isActive"] is True


def test_editing_a_regex_rule_rejects_an_invalid_pattern(monkeypatch):
    conn = RouteConn(rule_row={"kind": "regex"})
    client = _client(conn, monkeypatch)
    res = client.patch("/api/knowledge/rule-patterns/RP-002", json={"pattern": "(unclosed"})
    assert res.status_code == 422
    assert not any(sql.startswith("UPDATE rule_patterns") for sql, _ in conn.calls)


def test_rule_patch_on_unknown_rule_gives_404(monkeypatch):
    client = _client(RouteConn(rule_row=None), monkeypatch)
    res = client.patch("/api/knowledge/rule-patterns/RP-999", json={"is_active": True})
    assert res.status_code == 404
