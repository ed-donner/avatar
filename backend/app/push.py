"""Pushover notification sender for human-in-the-loop alerts."""

import requests

from app.config import get_settings

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def push(message: str) -> str:
    """Send a push notification to the human owner and return a status string."""
    settings = get_settings()
    payload = {"user": settings.pushover_user, "token": settings.pushover_token, "message": message}
    status = requests.post(PUSHOVER_URL, data=payload).status_code
    return f"Message pushed with status code {status}."
