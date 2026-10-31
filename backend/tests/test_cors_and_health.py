"""CORS origins and the health endpoint's service flags.

The browser calls the API through the Vercel rewrite, so CORS applies only when VITE_API_URL is
set. These tests check the configuration that matters in both cases.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings, find_origin_problems

SECRET_KEY = "AIzaSy-SECRET-VALUE-123"


def _settings(**overrides) -> Settings:
    base = dict(DATABASE_URL="postgresql://x", JWT_SECRET="x")
    base.update(overrides)
    return Settings(**base)


# ---------- origins ----------

def test_origins_are_trimmed_and_lose_trailing_slashes():
    s = _settings(FRONTEND_ORIGINS=" https://brand-guard-1.vercel.app/ , http://localhost:5173 ")
    assert s.cors_origins == ["https://brand-guard-1.vercel.app", "http://localhost:5173"]


def test_empty_entries_are_ignored():
    assert _settings(FRONTEND_ORIGINS="https://a.example,, ").cors_origins == ["https://a.example"]


def test_a_valid_list_has_no_problems():
    assert find_origin_problems(["https://brand-guard-1.vercel.app", "http://localhost:5173"]) == []


def test_a_wildcard_is_reported():
    assert any("'*'" in p for p in find_origin_problems(["*"]))


def test_an_origin_without_a_scheme_is_reported():
    assert any("needs a scheme" in p for p in find_origin_problems(["brand-guard-1.vercel.app"]))


def test_an_origin_with_a_path_is_reported():
    assert any("should not include a path" in p for p in find_origin_problems(["https://a.example/app"]))


# ---------- health ----------

def _health(monkeypatch, **overrides) -> dict:
    monkeypatch.setattr(main, "get_settings", lambda: _settings(**overrides))
    return TestClient(main.app).get("/api/health").json()


def test_health_reports_ai_as_not_configured_without_a_key(monkeypatch):
    body = _health(monkeypatch, GEMINI_API_KEY="")
    assert body["services"]["ai"] == "not_configured"


def test_health_reports_ai_as_configured_with_a_key_and_never_shows_the_key(monkeypatch):
    body = _health(monkeypatch, GEMINI_API_KEY=SECRET_KEY)
    assert body["services"]["ai"] == "configured"
    assert SECRET_KEY not in str(body)


def test_health_reports_slack_and_email_separately(monkeypatch):
    body = _health(monkeypatch, SLACK_BOT_TOKEN="xoxb-x", SLACK_CHANNEL_ID="C1", SMTP_HOST="", SMTP_FROM="")
    assert body["services"]["slack"] == "configured"
    assert body["services"]["email"] == "not_configured"


def test_health_still_answers_when_the_database_is_down(monkeypatch):
    body = _health(monkeypatch, GEMINI_API_KEY="")
    assert body["status"] == "ok"
    assert body["database"] == "down"


# ---------- preflight ----------

def test_cors_allows_the_configured_origin_and_blocks_others():
    client = TestClient(main.app)
    allowed = client.options("/api/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    })
    blocked = client.options("/api/health", headers={
        "Origin": "https://not-allowed.example",
        "Access-Control-Request-Method": "GET",
    })
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in blocked.headers
