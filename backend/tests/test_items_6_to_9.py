"""Logo check, deleting drafts and saved images, and the backfill script's missing-key message."""
from __future__ import annotations

import io
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.db import get_conn
from app.routes import content_image, knowledge
from app.security import current_user
from app.services import image_checks
from app.services.image_checks import run_image_checks

REPO = Path(__file__).resolve().parents[2]
APPROVED_LOGO = REPO / "test_data" / "images" / "approved_logo_v3.2.png"
LOW_CONTRAST_AD = REPO / "test_data" / "images" / "low_contrast_ad.png"


def _settings(**overrides):
    base = dict(approved_logo_path=str(APPROVED_LOGO), gemini_api_key="")
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------- logo check ----------

def test_logo_check_passes_when_the_image_is_the_approved_logo(monkeypatch):
    monkeypatch.setattr(image_checks, "get_settings", lambda: _settings())
    findings = run_image_checks(APPROVED_LOGO, alt_text="GreenGlow logo", is_logo=True)
    assert not [f for f in findings if f["sourceId"] == "IMG-LOGO"]


def test_logo_check_flags_an_image_that_is_not_the_logo(monkeypatch):
    monkeypatch.setattr(image_checks, "get_settings", lambda: _settings())
    findings = run_image_checks(LOW_CONTRAST_AD, alt_text="Ad", is_logo=True)
    logo = [f for f in findings if f["sourceId"] == "IMG-LOGO"]
    assert len(logo) == 1
    assert logo[0]["title"] == "This image does not match the approved logo"
    assert logo[0]["needsHumanReview"] is True


def test_logo_check_never_runs_on_ordinary_images(monkeypatch):
    monkeypatch.setattr(image_checks, "get_settings", lambda: _settings())
    findings = run_image_checks(LOW_CONTRAST_AD, alt_text="Ad", is_logo=False)
    assert not [f for f in findings if f["sourceId"] == "IMG-LOGO"]


def test_missing_approved_logo_file_gives_an_info_finding_not_a_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(image_checks, "get_settings", lambda: _settings(approved_logo_path=str(tmp_path / "none.png")))
    findings = run_image_checks(LOW_CONTRAST_AD, alt_text="Ad", is_logo=True)
    logo = [f for f in findings if f["sourceId"] == "IMG-LOGO"]
    assert logo and logo[0]["severity"] == "info"


# ---------- rule drafts: delete ----------

class _Result:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class _RuleConn:
    def __init__(self, is_active):
        self.is_active = is_active
        self.deleted = False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT is_active FROM rule_patterns"):
            return _Result(None if self.is_active is None else {"is_active": self.is_active})
        if s.startswith("DELETE FROM rule_patterns"):
            self.deleted = True
        return _Result()

    def transaction(self):
        return nullcontext()


def _client(conn, role="manager", user_id="user-manager"):
    app = FastAPI()
    app.include_router(knowledge.router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: {"id": user_id, "name": "n", "role": role}
    return TestClient(app)


def test_an_active_rule_cannot_be_deleted():
    conn = _RuleConn(is_active=True)
    res = _client(conn).delete("/api/knowledge/rule-patterns/RP-001")
    assert res.status_code == 409
    assert not conn.deleted


def test_a_switched_off_rule_can_be_deleted():
    conn = _RuleConn(is_active=False)
    res = _client(conn).delete("/api/knowledge/rule-patterns/RP-001")
    assert res.status_code == 204
    assert conn.deleted


def test_deleting_an_unknown_rule_gives_404():
    res = _client(_RuleConn(is_active=None)).delete("/api/knowledge/rule-patterns/RP-999")
    assert res.status_code == 404


def test_creators_cannot_delete_rules():
    res = _client(_RuleConn(is_active=False), role="creator", user_id="user-creator").delete("/api/knowledge/rule-patterns/RP-001")
    assert res.status_code == 403


# ---------- saved images: delete ----------

class _ImageConn:
    def __init__(self, owner="user-creator", status="Draft"):
        self.row = {"owner_id": owner, "status": status}
        self.cleared = False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT owner_id, status"):
            return _Result(self.row)
        if s.startswith("UPDATE content") and "image_url = NULL" in s:
            self.cleared = True
        return _Result()

    def transaction(self):
        return nullcontext()


def _image_client(conn, user_id="user-creator", role="creator", monkeypatch=None, storage=None):
    app = FastAPI()
    app.include_router(content_image.router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: {"id": user_id, "name": "n", "role": role}
    if monkeypatch is not None and storage is not None:
        monkeypatch.setattr(content_image, "default_storage_dir", lambda: storage)
    return TestClient(app)


def test_owner_can_remove_the_saved_image_and_the_file_is_deleted(tmp_path, monkeypatch):
    stored = tmp_path / "cnt_1.png"
    Image.new("RGB", (4, 4), (255, 255, 255)).save(stored)
    conn = _ImageConn()
    res = _image_client(conn, monkeypatch=monkeypatch, storage=tmp_path).delete("/api/content/cnt_1/image")
    assert res.status_code == 204
    assert not stored.exists()
    assert conn.cleared


def test_someone_else_cannot_remove_the_image(tmp_path, monkeypatch):
    res = _image_client(_ImageConn(), user_id="user-other", monkeypatch=monkeypatch, storage=tmp_path).delete("/api/content/cnt_1/image")
    assert res.status_code == 403


def test_the_image_cannot_be_removed_once_in_review(tmp_path, monkeypatch):
    res = _image_client(_ImageConn(status="In Review"), monkeypatch=monkeypatch, storage=tmp_path).delete("/api/content/cnt_1/image")
    assert res.status_code == 409


# ---------- backfill script ----------

def test_backfill_explains_the_missing_key_and_makes_no_changes():
    env = {"PATH": "", "GEMINI_API_KEY": ""}
    result = subprocess.run(
        [sys.executable, str(REPO / "backend" / "scripts" / "backfill_embeddings.py")],
        capture_output=True, text=True, cwd=str(REPO / "backend"), env={**env, "DATABASE_URL": "postgresql://x:y@127.0.0.1:1/z", "JWT_SECRET": "t", "PYTHONPATH": str(REPO / "backend")},
        timeout=60,
    )
    assert result.returncode == 2
    assert "GEMINI_API_KEY is not set" in result.stdout
