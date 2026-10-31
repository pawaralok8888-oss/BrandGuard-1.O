"""Brand intake gap report: status rules, coverage queries, and the routes.

No database: the pure report function gets rows and counts directly, and the routes use a fake
connection that answers the coverage queries from a dict.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_conn
from app.routes.intake import router
from app.security import current_user
from app.services.intake import COVERAGE_SQL, MANUAL, build_gap_report, field_status

MIGRATION = Path(__file__).resolve().parents[2] / "data" / "migrations" / "003_intake.sql"
MANAGER = {"id": "user-manager", "name": "Priya", "role": "manager"}


def _row(**overrides) -> dict:
    base = {
        "category_id": "brand_identity", "category_label": "Brand identity",
        "id": "IF-001", "label": "Logo", "description": "", "required": True,
        "coverage_check": "logo", "response_status": None, "response_note": None,
    }
    base.update(overrides)
    return base


# ---------- status rules ----------

def test_data_that_answers_a_field_makes_it_covered():
    assert field_status("logo", data_found=True, response_status=None) == "covered"


def test_missing_data_is_a_gap():
    assert field_status("logo", data_found=False, response_status=None) == "gap"


def test_manual_field_is_a_gap_until_someone_marks_it():
    assert field_status(MANUAL, data_found=True, response_status=None) == "gap"
    assert field_status(MANUAL, data_found=False, response_status="provided") == "provided"


def test_not_applicable_wins_over_missing_data():
    assert field_status("logo", data_found=False, response_status="not_applicable") == "not_applicable"


def test_report_counts_required_gaps_separately_from_optional_ones():
    rows = [
        _row(id="IF-001", coverage_check="logo", required=True),
        _row(id="IF-002", coverage_check="fonts", required=False),
        _row(id="IF-003", coverage_check="colour_palette", required=True),
    ]
    report = build_gap_report(rows, counts={"logo": 1, "fonts": 0, "colour_palette": 0})

    assert report["summary"]["total"] == 3
    assert report["summary"]["covered"] == 1
    assert report["summary"]["gaps"] == 2
    assert report["summary"]["requiredGaps"] == 1  # the optional fonts gap is not counted


def test_report_groups_fields_under_their_category_in_order():
    rows = [
        _row(id="IF-001", category_id="brand_identity", category_label="Brand identity"),
        _row(id="IF-002", category_id="brand_identity", category_label="Brand identity",
             coverage_check="fonts"),
        _row(id="IF-005", category_id="products", category_label="Products", coverage_check="product_list"),
    ]
    report = build_gap_report(rows, counts={"logo": 1, "fonts": 1, "product_list": 1})

    assert [c["id"] for c in report["categories"]] == ["brand_identity", "products"]
    assert [f["id"] for f in report["categories"][0]["fields"]] == ["IF-001", "IF-002"]


# ---------- seed and code agree ----------

def test_every_seeded_coverage_check_has_a_query_or_is_manual():
    text = MIGRATION.read_text(encoding="utf-8")
    seeded = set(re.findall(r"'([a-z_]+)', \d+\)", text))
    checks_allowed = set(re.findall(r"'([a-z_]+)'", text.split("coverage_check TEXT NOT NULL CHECK (")[1].split("))")[0]))

    assert seeded, "no seeded fields found: the regex is out of date"
    assert seeded <= checks_allowed, f"seeded checks missing from the CHECK list: {seeded - checks_allowed}"
    for check in checks_allowed:
        assert check == MANUAL or check in COVERAGE_SQL, f"no coverage query for {check}"


# ---------- routes ----------

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


class IntakeConn:
    def __init__(self, field_rows, counts_by_sql, known_fields=("IF-001",)):
        self.field_rows = field_rows
        self.counts_by_sql = counts_by_sql
        self.known_fields = set(known_fields)
        self.calls = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        self.calls.append((s, tuple(params)))
        if s.startswith("SELECT c.id AS category_id"):
            return _Result(rows=self.field_rows)
        if s in self.counts_by_sql:
            return _Result(row={"n": self.counts_by_sql[s]})
        if s.startswith("SELECT 1 FROM intake_fields"):
            return _Result(row={"1": 1} if params[0] in self.known_fields else None)
        return _Result()

    def transaction(self):
        return _Tx()


def _client(conn):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: MANAGER
    return TestClient(app)


def test_gap_report_route_runs_each_coverage_query_once_and_reports_gaps():
    logo_sql = " ".join(COVERAGE_SQL["logo"].split())
    rows = [_row(id="IF-001", coverage_check="logo"),
            _row(id="IF-004", coverage_check=MANUAL, category_id="brand_identity")]
    conn = IntakeConn(rows, counts_by_sql={logo_sql: 1})

    res = _client(conn).get("/api/intake/gap-report")

    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["covered"] == 1
    assert body["summary"]["requiredGaps"] == 1  # the manual brand owner field
    assert sum(1 for s, _ in conn.calls if s == logo_sql) == 1


def test_marking_a_manual_field_provided_is_saved_with_the_user():
    conn = IntakeConn([], counts_by_sql={}, known_fields=("IF-004",))
    res = _client(conn).patch("/api/intake/fields/IF-004", json={"status": "provided", "note": "Maya, brand lead"})
    assert res.status_code == 200
    upsert = next(p for s, p in conn.calls if s.startswith("INSERT INTO intake_responses"))
    assert upsert == ("IF-004", "provided", "Maya, brand lead", "user-manager")


def test_clearing_a_mark_deletes_the_response():
    conn = IntakeConn([], counts_by_sql={}, known_fields=("IF-004",))
    res = _client(conn).patch("/api/intake/fields/IF-004", json={})
    assert res.status_code == 200
    assert any(s.startswith("DELETE FROM intake_responses") for s, _ in conn.calls)


def test_unknown_field_gives_404():
    conn = IntakeConn([], counts_by_sql={}, known_fields=())
    assert _client(conn).patch("/api/intake/fields/IF-999", json={"status": "provided"}).status_code == 404


def test_invalid_status_is_rejected():
    conn = IntakeConn([], counts_by_sql={}, known_fields=("IF-004",))
    assert _client(conn).patch("/api/intake/fields/IF-004", json={"status": "maybe"}).status_code == 422
