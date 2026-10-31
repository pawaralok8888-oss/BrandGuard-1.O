"""Optional Slack notification for fact-change alerts (Member 3).

Does nothing and returns False when SLACK_BOT_TOKEN is not set,
so the demo runs offline.
"""
from __future__ import annotations

from app.config import get_settings


def is_configured() -> bool:
    """True when both the bot token and the channel are set."""
    settings = get_settings()
    return bool(settings.slack_bot_token and settings.slack_channel_id)


def notify_alert(alert: dict, client=None) -> bool:
    """Post a short alert message to Slack. Returns True only if a message was sent."""
    settings = get_settings()
    if not is_configured():
        return False

    if client is None:
        from slack_sdk import WebClient

        client = WebClient(token=settings.slack_bot_token)

    text = (
        f"*Fact alert ({alert.get('priority', 'Medium')})*\n"
        f"{alert.get('title', 'Fact changed')}\n"
        f"Content: {alert.get('content_id', 'unknown')}"
    )
    client.chat_postMessage(channel=settings.slack_channel_id, text=text)
    return True