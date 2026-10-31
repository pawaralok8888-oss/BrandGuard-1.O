"""Categories and channels are read from the database, and the list endpoints return them."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_conn
from app.routes import knowledge
from app.security import current_user
from tests.lookups import CATEGORY_IDS, CHANNEL_IDS, lookup_rows


class _Result:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def execute(self, sql, params=()):
        return _Result(lookup_rows(sql) or [])

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()


def _client(role="creator"):
    app = FastAPI()
    app.include_router(knowledge.router)
    app.dependency_overrides[get_conn] = lambda: _Conn()
    app.dependency_overrides[current_user] = lambda: {"id": "u", "name": "n", "role": role}
    return TestClient(app)


def test_categories_endpoint_returns_the_database_list_in_order():
    assert _client().get("/api/knowledge/categories").json() == CATEGORY_IDS


def test_channels_endpoint_returns_the_database_list_in_order():
    assert _client().get("/api/knowledge/channels").json() == CHANNEL_IDS


def test_lookups_need_a_signed_in_user():
    app = FastAPI()
    app.include_router(knowledge.router)
    app.dependency_overrides[get_conn] = lambda: _Conn()
    # no current_user override: the dependency rejects the request
    assert TestClient(app).get("/api/knowledge/categories").status_code == 401


def test_seed_migration_matches_the_lookup_list():
    """The migration seeds must match the answers the tests (and the app) expect."""
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "data" / "migrations" / "005_categories_channels_logo.sql").read_text(encoding="utf-8")
    for category in CATEGORY_IDS:
        assert f"'{category}'" in text, category
    for channel in CHANNEL_IDS:
        assert f"'{channel}'" in text, channel
