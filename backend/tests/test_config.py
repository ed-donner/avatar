"""Settings env parsing, including the Docker --env-file quote gotcha."""

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
