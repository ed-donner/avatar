"""Pushover notifications: human-in-the-loop alerts, and debounced backend-error alerts."""

import requests
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.config import get_settings

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
TIMEOUT_SECONDS = 5
DEFAULT_SOUND = "bugle"  # human-in-the-loop notifications
ERROR_SOUND = "gamelan"  # backend-error alerts

# Backend-error alerts are debounced so a burst of the same error (e.g. every chat turn
# failing once the OpenRouter daily cap is hit, or a brute-force login flood) can't spam
# notifications or drain the Pushover quota. Per category, a few per hour is plenty.
_error_storage = MemoryStorage()
_error_limiter = MovingWindowRateLimiter(_error_storage)
_error_rate = parse("3/hour")


def _send(message: str, sound: str, title: str | None = None) -> str:
    """POST one message to Pushover with a timeout, failing softly on any network error."""
    settings = get_settings()
    payload = {
        "user": settings.pushover_user,
        "token": settings.pushover_token,
        "message": message,
        "sound": sound,
    }
    if title:
        payload["title"] = title
    try:
        status = requests.post(PUSHOVER_URL, data=payload, timeout=TIMEOUT_SECONDS).status_code
        return f"Message pushed with status code {status}."
    except requests.RequestException:
        return "Could not reach the notification service; the message was not delivered."


def push(message: str, sound: str = DEFAULT_SOUND) -> str:
    """Send a human-in-the-loop notification to the owner (default sound: bugle)."""
    return _send(message, sound)


def notify_error(summary: str, category: str = "error") -> None:
    """Alert the owner about a backend error (sound: gamelan), debounced per category.

    A slow/unreachable Pushover or a flood of errors must never hang or spam, so this
    fails softly and sends at most a few alerts per category per hour.
    """
    if not _error_limiter.hit(_error_rate, "error", category):
        return  # already alerted for this category recently
    _send(summary, ERROR_SOUND, title="Avatar backend alert")
