"""Asset format on content: accepted, validated, stored and returned.

The fake connection records the INSERT so the test can check the format value is stored.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db import get_conn
from app.routes.content import ContentCreate, ContentUpdate, router
from app.security import current_user

CREATOR = {"id": "user-creator", "name": "Maya", "role": "creator"}


def _base(**extra) -> dict:
    base = {"title": "Launch post", "channel": "Instagram", "team": "Marketing",
            "bodyText": "Hello", "bodyHtml": "<p>Hello</p>"}
    base.update(extra)
    return base


def test_format_defaults_to_not_chosen():
    assert ContentCreate(**_base()).format == ""


def test_a_known_format_is_accepted():
    assert ContentCreate(**_base(format="social_post")).format == "social_post"


def test_an_unknown_format_is_rejected():
    with pytest.raises(ValidationError):
        ContentCreate(**_base(format="billboard"))


def test_update_accepts_a_format_and_rejects_unknown_ones():
    assert ContentUpdate(format="email").format == "email"
    with pytest.raises(ValidationError):
        ContentUpdate(format="billboard")


class _Result:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Conn:
    def __init__(self):
        self.inserts = []
        self.saved_format = None

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO content ("):
            self.inserts.append((normalized, params))
            self.saved_format = params[-1]
            return _Result()
        if "WHERE c.id = %s" in normalized:
            # The create route reads the row back; return it with the format that was saved.
            return _Result(row={
                "id": params[0], "title": "Launch post", "channel": "Instagram", "team": "Marketing",
                "status": "Draft", "body_text": "Hello", "body_html": "<p>Hello</p>",
                "owner_id": CREATOR["id"], "created_at": "2026-10-31", "updated_at": "2026-10-31",
                "current_version": 1, "thumbnail_art": None, "image_url": None,
                "alt_text": None, "format": self.saved_format or "", "image_is_logo": False,
            })
        return _Result()

    def transaction(self):
        return _Tx()


def test_create_stores_the_format_in_the_insert():
    conn = _Conn()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: CREATOR
    res = TestClient(app).post("/api/content", json=_base(format="email"))
    assert res.status_code == 201
    sql, params = conn.inserts[0]
    assert "format" in sql
    assert params[-1] == "email"
    assert res.json()["format"] == "email"


def test_list_and_detail_queries_select_the_format_column():
    """The list and detail queries must select c.format, or to_item fails with KeyError."""
    from app.routes.content import _content_select
    assert "c.format" in " ".join(_content_select().split())
