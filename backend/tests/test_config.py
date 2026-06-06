"""Settings env parsing, including the Docker --env-file quote gotcha."""

import pytest

from app import config
from app.config import _env


def test_env_strips_surrounding_double_quotes(monkeypatch):
    monkeypatch.setenv("AVATAR_T", '"openai/gpt-5.4-nano"')
    assert _env("AVATAR_T") == "openai/gpt-5.4-nano"


def test_env_strips_surrounding_single_quotes(monkeypatch):
    monkeypatch.setenv("AVATAR_T", "'Ed Donner'")
    assert _env("AVATAR_T") == "Ed Donner"


def test_env_keeps_inner_quotes_and_unquoted(monkeypatch):
    monkeypatch.setenv("AVATAR_T", 'say "hi"')
    assert _env("AVATAR_T") == 'say "hi"'
    monkeypatch.setenv("AVATAR_T", "plain")
    assert _env("AVATAR_T") == "plain"


def test_env_default_when_missing(monkeypatch):
    monkeypatch.delenv("AVATAR_MISSING", raising=False)
    assert _env("AVATAR_MISSING", "fallback") == "fallback"


def test_empty_admin_password_fails_closed(monkeypatch):
    """The app must refuse to start without ADMIN_PASSWORD (no fail-open admin)."""
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
            config.get_settings()
    finally:
        config.get_settings.cache_clear()  # let the restored env reload cleanly for other tests
