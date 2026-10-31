"""Brand rules: lifecycle rules and what the check pipeline loads.

A fake connection keeps one brand rule in memory and applies each statement to it, so the tests
check the state changes, not only the calls. No database is needed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_conn
from app.routes.brand_rules import router
from app.security import current_user
from app.services import checks

CREATOR = {"id": "user-manager", "name": "Priya", "role": "manager"}
APPROVER = {"id": "user-admin", "name": "Sam", "role": "admin"}
NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


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


class BrandRuleConn:
    def __init__(self, rule: dict | None = None):
        self.rule = rule
        self.history: list[tuple] = []
        self.calls: list[str] = []

    def _row(self):
        return dict(self.rule) if self.rule else None

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        self.calls.append(s)
        if s.startswith("LOCK TABLE"):
            return _Result()
        if s.startswith("SELECT id FROM brand_rules"):
            return _Result(rows=[{"id": self.rule["id"]}] if self.rule else [])
        if s.startswith("INSERT INTO brand_rules"):
            self.rule = {
                "id": params[0], "title": params[1], "kind": params[2], "pattern": params[3],
                "replacement": params[4], "reason": params[5], "channel": params[6],
                "severity": params[7], "status": "draft", "created_by": params[8],
                "approved_by": None, "approved_at": None, "retired_at": None,
                "created_at": NOW, "updated_at": NOW,
            }
            return _Result(row=self._row())
        if s.startswith("SELECT") and "FROM brand_rules WHERE id = %s FOR UPDATE" in s:
            return _Result(row=self._row() if self.rule and self.rule["id"] == params[0] else None)
        if s.startswith("UPDATE brand_rules SET status = 'approved'"):
            self.rule.update(status="approved", approved_by=params[0], approved_at=NOW)
            return _Result(row=self._row())
        if s.startswith("UPDATE brand_rules SET status = 'retired'"):
            self.rule.update(status="retired", retired_at=NOW)
            return _Result(row=self._row())
        if s.startswith("UPDATE brand_rules SET"):
            for column, value in zip([c.split(" = ")[0] for c in s.split("SET ")[1].split(", ") if " = %s" in c], params):
                self.rule[column] = value
            return _Result(row=self._row())
        if s.startswith("INSERT INTO brand_rule_history"):
            self.history.append(params)
            return _Result()
        return _Result()

    def transaction(self):
        return _Tx()


def _rule(**overrides) -> dict:
    base = {
        "id": "BR-001", "title": "No miracle claims", "kind": "phrase", "pattern": "miracle",
        "replacement": "effective", "reason": "Unsupported claim", "channel": None,
        "severity": "critical", "status": "draft", "created_by": CREATOR["id"],
        "approved_by": None, "approved_at": None, "retired_at": None,
        "created_at": NOW, "updated_at": NOW,
    }
    base.update(overrides)
    return base


def _client(conn, user):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: user
    return TestClient(app)


# ---------- lifecycle ----------

def test_create_makes_a_draft_and_records_history():
    conn = BrandRuleConn()
    res = _client(conn, CREATOR).post("/api/brand-rules", json={
        "title": "No miracle claims", "kind": "phrase", "pattern": "miracle",
        "replacement": "effective", "severity": "critical",
    })
    assert res.status_code == 201
    assert res.json()["status"] == "draft"
    assert res.json()["id"] == "BR-001"
    assert conn.history[0][1:3] == (None, "draft")


def test_creator_cannot_approve_their_own_rule():
    conn = BrandRuleConn(_rule())
    res = _client(conn, CREATOR).post("/api/brand-rules/BR-001/approve")
    assert res.status_code == 403
    assert conn.rule["status"] == "draft"


def test_a_different_person_can_approve_and_it_is_recorded():
    conn = BrandRuleConn(_rule())
    res = _client(conn, APPROVER).post("/api/brand-rules/BR-001/approve", json={"note": "checked"})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
    assert res.json()["approvedBy"] == APPROVER["id"]
    assert conn.history[-1][1:4] == ("draft", "approved", APPROVER["id"])


def test_a_draft_cannot_be_retired_directly():
    conn = BrandRuleConn(_rule())
    assert _client(conn, APPROVER).post("/api/brand-rules/BR-001/retire").status_code == 409


def test_approved_rule_can_be_retired_and_retirement_is_final():
    conn = BrandRuleConn(_rule(status="approved", approved_by=APPROVER["id"], approved_at=NOW))
    client = _client(conn, APPROVER)
    assert client.post("/api/brand-rules/BR-001/retire").json()["status"] == "retired"
    assert client.post("/api/brand-rules/BR-001/approve").status_code == 409


def test_only_drafts_can_be_edited():
    conn = BrandRuleConn(_rule(status="approved", approved_by=APPROVER["id"], approved_at=NOW))
    res = _client(conn, CREATOR).patch("/api/brand-rules/BR-001", json={"replacement": "clear"})
    assert res.status_code == 409


def test_draft_edit_is_saved():
    conn = BrandRuleConn(_rule())
    res = _client(conn, CREATOR).patch("/api/brand-rules/BR-001", json={"replacement": "clinically tested"})
    assert res.status_code == 200
    assert res.json()["replacement"] == "clinically tested"


def test_invalid_regex_is_rejected_on_create():
    res = _client(BrandRuleConn(), CREATOR).post("/api/brand-rules", json={
        "title": "bad", "kind": "regex", "pattern": "(unclosed",
    })
    assert res.status_code == 422


def test_confidential_terms_cannot_be_created_as_brand_rules():
    """Confidential terms stay in rule_patterns, where redaction reads them."""
    res = _client(BrandRuleConn(), CREATOR).post("/api/brand-rules", json={
        "title": "secret", "kind": "confidential_term", "pattern": "ProjectOrion",
    })
    assert res.status_code == 422


def test_unknown_rule_gives_404():
    res = _client(BrandRuleConn(None), APPROVER).post("/api/brand-rules/BR-999/approve")
    assert res.status_code == 404


# ---------- what the check pipeline loads ----------

class _LoaderConn:
    """Answers the two queries load_active_rules makes."""

    def __init__(self, brand_rows):
        self.brand_rows = brand_rows
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append(" ".join(sql.split()))
        if "FROM rule_patterns" in sql:
            return _Result(rows=[])
        return _Result(rows=self.brand_rows)


def test_loader_asks_only_for_approved_brand_rules_in_this_channel():
    conn = _LoaderConn([])
    checks.load_active_rules(conn, "Website")
    brand_sql = next(s for s in conn.sql if "FROM brand_rules" in s)
    assert "status = 'approved'" in brand_sql
    assert "channel = %s" in brand_sql


def test_approved_brand_rule_becomes_a_checkable_rule_with_its_own_source():
    row = {"id": "BR-001", "kind": "phrase", "pattern": "miracle", "replacement": "effective",
           "channel": None, "guideline_id": None, "title": "No miracle claims",
           "text": "Unsupported claim", "severity": "critical", "version": 1}
    rules = checks.load_active_rules(_LoaderConn([row]), "Website")

    assert len(rules) == 1
    rule = rules[0]
    assert rule["type"] == "phrase"
    assert rule["patterns"] == ["miracle"]
    assert rule["source_id"] == "BR-001"          # not a G- id, so no guideline link is written
    assert rule["severity_default"] == "critical"
    assert rule["replacement"] == "effective"


def test_an_approved_brand_rule_flags_the_text_it_names():
    """End to end through the rule engine: the approved rule finds 'miracle' in a post."""
    from app.pipeline.rules import run_rules

    row = {"id": "BR-001", "kind": "phrase", "pattern": "miracle", "replacement": "effective",
           "channel": None, "guideline_id": None, "title": "No miracle claims",
           "text": "Unsupported claim", "severity": "critical", "version": 1}
    rules = checks.load_active_rules(_LoaderConn([row]), "Website")
    findings = run_rules("This is a miracle serum.", "cnt_1", rules)

    assert len(findings) == 1
    assert findings[0]["sourceId"] == "BR-001"
    assert findings[0]["originalText"] == "miracle"
    assert findings[0]["suggestedFix"] == "effective"
