"""Alert notifications: Slack and email delivery, the recorded outcome of every attempt, and the log route.

No network: Slack is a fake client, email is an injected sender, and SMTP is replaced in one test.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.notifications as notifications
from app.db import get_conn
from app.routes.notifications import router
from app.security import current_user
from app.services import impact, slack_notifier

ALERT = {
    "id": "AL-1", "recipient_id": "user-creator", "content_id": "cnt_9",
    "title": "Fact F-001 changed: Certification", "priority": "High",
    "old_value": "Certified until 2026", "new_value": "Certified until 2027",
    "suggested_fix": "Update the post to match the new certification date",
}


def _settings(**overrides):
    base = dict(smtp_host="", smtp_port=587, smtp_user="", smtp_password="", smtp_from="",
                smtp_starttls=True, app_base_url="", slack_bot_token="", slack_channel_id="")
    base.update(overrides)
    return SimpleNamespace(**base)


def _configure(monkeypatch, **overrides):
    settings = _settings(**overrides)
    monkeypatch.setattr(notifications, "get_settings", lambda: settings)
    monkeypatch.setattr(slack_notifier, "get_settings", lambda: settings)
    return settings


class RecordingConn:
    """Stores notification_log inserts and answers the recipient email lookup."""

    def __init__(self, emails=None, fail_insert=False):
        self.emails = emails or {}
        self.fail_insert = fail_insert
        self.logged = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT id, email FROM users"):
            ids = params[0]
            rows = [{"id": i, "email": self.emails.get(i)} for i in ids]
            return SimpleNamespace(fetchall=lambda: rows)
        if normalized.startswith("INSERT INTO notification_log"):
            if self.fail_insert:
                raise psycopg.OperationalError("database went away")
            self.logged.append(params)
        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: None)

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()


def _status_and_error(logged, channel):
    return [(p[5], p[6]) for p in logged if p[1] == channel]


# ---------- what each channel does ----------

def test_slack_unconfigured_is_recorded_as_skipped_with_the_reason(monkeypatch):
    _configure(monkeypatch)
    conn = RecordingConn(emails={"user-creator": None})
    client = MagicMock()

    counts = notifications.deliver_alerts(conn, [ALERT], slack_client=client, email_sender=MagicMock())

    client.chat_postMessage.assert_not_called()
    [(status, error)] = _status_and_error(conn.logged, "slack")
    assert status == "skipped"
    assert "SLACK_BOT_TOKEN" in error
    assert counts["skipped"] == 2  # slack and email both skipped


def test_slack_configured_posts_and_records_sent(monkeypatch):
    _configure(monkeypatch, slack_bot_token="xoxb-test", slack_channel_id="C123")
    conn = RecordingConn()
    client = MagicMock()

    notifications.deliver_alerts(conn, [ALERT], slack_client=client)

    client.chat_postMessage.assert_called_once()
    assert ("sent", "") in _status_and_error(conn.logged, "slack")


def test_slack_error_is_recorded_as_failed_without_the_token_text(monkeypatch):
    _configure(monkeypatch, slack_bot_token="xoxb-SECRET", slack_channel_id="C123")
    client = MagicMock()
    client.chat_postMessage.side_effect = RuntimeError("xoxb-SECRET invalid_auth")
    conn = RecordingConn()

    counts = notifications.deliver_alerts(conn, [ALERT], slack_client=client)

    [(status, error)] = _status_and_error(conn.logged, "slack")
    assert status == "failed"
    assert error == "RuntimeError"
    assert all("xoxb-SECRET" not in str(part) for row in conn.logged for part in row)
    assert counts["failed"] == 1


def test_email_unconfigured_is_skipped_with_the_reason(monkeypatch):
    _configure(monkeypatch)
    conn = RecordingConn(emails={"user-creator": "maya@example.com"})
    notifications.deliver_alerts(conn, [ALERT], slack_client=MagicMock(), email_sender=MagicMock())
    [(status, error)] = _status_and_error(conn.logged, "email")
    assert status == "skipped"
    assert "SMTP_HOST" in error


def test_email_is_sent_to_the_recipients_address(monkeypatch):
    _configure(monkeypatch, smtp_host="smtp.example.com", smtp_from="alerts@brandguard.test")
    conn = RecordingConn(emails={"user-creator": "maya@example.com"})
    sent = []

    notifications.deliver_alerts(conn, [ALERT], slack_client=MagicMock(),
                                 email_sender=lambda to, subject, body: sent.append((to, subject, body)))

    [(to, subject, body)] = sent
    assert to == "maya@example.com"
    assert "Certified until 2027" in body
    assert "High priority" in subject
    assert ("sent", "") in _status_and_error(conn.logged, "email")


def test_user_without_an_email_address_is_skipped_not_failed(monkeypatch):
    _configure(monkeypatch, smtp_host="smtp.example.com", smtp_from="alerts@brandguard.test")
    conn = RecordingConn(emails={"user-creator": None})
    sender = MagicMock()

    notifications.deliver_alerts(conn, [ALERT], slack_client=MagicMock(), email_sender=sender)

    sender.assert_not_called()
    [(status, error)] = _status_and_error(conn.logged, "email")
    assert status == "skipped"
    assert "No email address" in error


def test_smtp_error_is_recorded_as_failed(monkeypatch):
    _configure(monkeypatch, smtp_host="smtp.example.com", smtp_from="alerts@brandguard.test")
    conn = RecordingConn(emails={"user-creator": "maya@example.com"})

    def broken(to, subject, body):
        raise ConnectionRefusedError("refused")

    counts = notifications.deliver_alerts(conn, [ALERT], slack_client=MagicMock(), email_sender=broken)

    assert ("failed", "ConnectionRefusedError") in _status_and_error(conn.logged, "email")
    assert counts["failed"] == 1


def test_delivery_never_raises_even_if_the_log_cannot_be_written(monkeypatch):
    _configure(monkeypatch, slack_bot_token="x", slack_channel_id="C1")
    conn = RecordingConn(fail_insert=True)
    counts = notifications.deliver_alerts(conn, [ALERT], slack_client=MagicMock(),
                                          email_sender=MagicMock())
    assert set(counts) == {"sent", "failed", "skipped"}


def test_no_alerts_means_nothing_to_do(monkeypatch):
    _configure(monkeypatch)
    conn = RecordingConn()
    assert notifications.deliver_alerts(conn, []) == {"sent": 0, "failed": 0, "skipped": 0}
    assert conn.logged == []


# ---------- SMTP details ----------

def test_send_email_uses_starttls_and_login(monkeypatch):
    _configure(monkeypatch, smtp_host="smtp.example.com", smtp_port=587, smtp_user="bot",
               smtp_password="pw", smtp_from="alerts@brandguard.test", smtp_starttls=True)
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    monkeypatch.setattr(notifications.smtplib, "SMTP", MagicMock(return_value=smtp))

    notifications.send_email("maya@example.com", "Subject", "Body")

    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("bot", "pw")
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "maya@example.com"
    assert message["From"] == "alerts@brandguard.test"


def test_email_body_links_to_alerts_when_the_app_url_is_set():
    _, body = notifications.build_alert_email(ALERT, app_base_url="https://brandguard.test/")
    assert "https://brandguard.test/alerts" in body


# ---------- the alerts the impact service creates are returned ----------

class ImpactConn:
    def __init__(self):
        self.inserted = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if "SELECT DISTINCT c.id AS content_id" in normalized:
            rows = [{"content_id": "cnt_9", "title": "Launch post", "owner_id": "user-creator"}]
            return SimpleNamespace(fetchall=lambda: rows)
        if normalized.startswith("INSERT INTO alerts"):
            self.inserted.append(params)
        return SimpleNamespace(fetchall=lambda: [], fetchone=lambda: None)


def test_apply_fact_change_returns_the_alerts_it_created_with_their_ids():
    conn = ImpactConn()
    result = impact.apply_fact_change(conn, "F-001", "old", "new", 2, "High", "fix")

    [alert] = result["alerts"]
    assert alert["id"].startswith("AL-")
    assert alert["recipient_id"] == "user-creator"
    assert conn.inserted[0][0] == alert["id"]  # the same id is the one written to alerts


# ---------- the log route ----------

class LogConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append(" ".join(sql.split()))
        return SimpleNamespace(fetchall=lambda: self.rows)


def _route_client(conn, role):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[current_user] = lambda: {"id": "u", "name": "n", "role": role}
    return TestClient(app)


def test_log_shows_skipped_rows_with_their_reason():
    from datetime import datetime, timezone
    row = {"id": "NL-1", "channel": "slack", "recipient_id": "user-creator", "subject": "s",
           "status": "skipped", "error": "Slack is not configured", "created_at": datetime(2026, 10, 31, tzinfo=timezone.utc)}
    conn = LogConn([row])
    res = _route_client(conn, "manager").get("/api/notifications?status=skipped")
    assert res.status_code == 200
    assert res.json()[0]["error"] == "Slack is not configured"
    assert "status = %s" in conn.sql[0]


def test_log_is_hidden_from_creators():
    assert _route_client(LogConn([]), "creator").get("/api/notifications").status_code == 403
