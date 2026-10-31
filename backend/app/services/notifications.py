"""Deliver fact-change alerts to Slack and by email, and record every attempt.

Each alert produces one notification_log row per channel. The status says what happened:
  sent     the message was delivered
  failed   the attempt raised an error (the error class name is kept, never the message or secrets)
  skipped  it was not attempted, with the reason in error (for example: SMTP not configured)

Delivery is best effort. A failure here is logged and recorded, and never stops a fact from saving.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from typing import Callable

import psycopg
from psycopg import Connection

from app.config import get_settings
from app.services import slack_notifier

logger = logging.getLogger(__name__)

CHANNEL_SLACK = "slack"
CHANNEL_EMAIL = "email"
SMTP_TIMEOUT_SECONDS = 15


def email_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def build_alert_email(alert: dict, app_base_url: str = "") -> tuple[str, str]:
    """Subject and plain-text body for one alert. Pure, so it is easy to test."""
    subject = f"[BrandGuard] {alert['priority']} priority: {alert['title']}"
    lines = [
        "A fact used in one of your published posts has changed.",
        "",
        f"Fact: {alert['title']}",
        f"Post: {alert['content_id']}",
        f"Was: {alert.get('old_value') or '-'}",
        f"Now: {alert.get('new_value') or '-'}",
    ]
    if alert.get("suggested_fix"):
        lines += ["", f"Suggested fix: {alert['suggested_fix']}"]
    if app_base_url:
        lines += ["", f"Review it here: {app_base_url.rstrip('/')}/alerts"]
    return subject, "\n".join(lines)


def send_email(to_address: str, subject: str, body: str) -> None:
    """Send one plain-text email over SMTP. Raises on any failure."""
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def _record(conn: Connection, channel: str, recipient_id: str, subject: str, body: str,
            status: str, error: str = "") -> None:
    try:
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO notification_log (id, channel, recipient_id, subject, body, status, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (f"NL-{uuid.uuid4().hex[:12]}", channel, recipient_id, subject, body, status, error),
            )
    except psycopg.Error:
        logger.exception("Could not record a %s notification for %s", channel, recipient_id)


def _deliver_slack(conn: Connection, alert: dict, client) -> str:
    subject = f"Slack: {alert['title']}"
    body = f"{alert['priority']} priority alert on {alert['content_id']}"
    if not slack_notifier.is_configured():
        _record(conn, CHANNEL_SLACK, alert["recipient_id"], subject, body, "skipped",
                "Slack is not configured (SLACK_BOT_TOKEN and SLACK_CHANNEL_ID)")
        return "skipped"
    try:
        posted = slack_notifier.notify_alert(
            {"title": alert["title"], "priority": alert["priority"], "content_id": alert["content_id"]},
            client=client,
        )
    except Exception as exc:
        logger.warning("Slack alert failed: %s", exc.__class__.__name__)
        _record(conn, CHANNEL_SLACK, alert["recipient_id"], subject, body, "failed", exc.__class__.__name__)
        return "failed"
    status = "sent" if posted else "failed"
    _record(conn, CHANNEL_SLACK, alert["recipient_id"], subject, body, status,
            "" if posted else "No message was posted")
    return status


def _deliver_email(conn: Connection, alert: dict, to_address: str | None, sender: Callable) -> str:
    settings = get_settings()
    subject, body = build_alert_email(alert, settings.app_base_url)
    if not email_is_configured():
        _record(conn, CHANNEL_EMAIL, alert["recipient_id"], subject, body, "skipped",
                "Email is not configured (SMTP_HOST and SMTP_FROM)")
        return "skipped"
    if not to_address:
        _record(conn, CHANNEL_EMAIL, alert["recipient_id"], subject, body, "skipped",
                "No email address on file for this user")
        return "skipped"
    try:
        sender(to_address, subject, body)
    except Exception as exc:
        logger.warning("Alert email failed: %s", exc.__class__.__name__)
        _record(conn, CHANNEL_EMAIL, alert["recipient_id"], subject, body, "failed", exc.__class__.__name__)
        return "failed"
    _record(conn, CHANNEL_EMAIL, alert["recipient_id"], subject, body, "sent")
    return "sent"


def deliver_alerts(
    conn: Connection,
    alerts: list[dict],
    *,
    slack_client=None,
    email_sender: Callable | None = None,
) -> dict[str, int]:
    """Send every alert on every channel and record the result. Never raises.

    Returns counts of sent, failed and skipped attempts.
    """
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    if not alerts:
        return counts

    sender = email_sender or send_email
    try:
        recipients = [a["recipient_id"] for a in alerts]
        emails = {
            row["id"]: row["email"]
            for row in conn.execute(
                "SELECT id, email FROM users WHERE id = ANY(%s)", (recipients,)
            ).fetchall()
        }
    except Exception:
        logger.exception("Could not load alert recipients; email skipped")
        emails = {}

    for alert in alerts:
        for outcome in (
            _deliver_slack(conn, alert, slack_client),
            _deliver_email(conn, alert, emails.get(alert["recipient_id"]), sender),
        ):
            counts[outcome] += 1
    return counts
