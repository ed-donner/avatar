"""Pushover notification sender for human-in-the-loop alerts."""

import requests

from app.config import get_settings

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
TIMEOUT_SECONDS = 5


def push(message: str) -> str:
    """Send a push notification to the human owner and return a status string.

    Has a timeout and fails softly: a slow or unreachable Pushover must not hang or
    break the chat turn that called the tool.
    """
    settings = get_settings()
    payload = {"user": settings.pushover_user, "token": settings.pushover_token, "message": message}
    try:
        status = requests.post(PUSHOVER_URL, data=payload, timeout=TIMEOUT_SECONDS).status_code
        return f"Message pushed with status code {status}."
    except requests.RequestException:
        return "Could not reach the notification service; the message was not delivered."
