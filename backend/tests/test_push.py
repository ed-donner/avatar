"""Tests for the Pushover sender: it must use a timeout and fail softly."""

import requests

from app import push as push_mod


def test_push_passes_a_timeout(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

    def fake_post(url, data=None, timeout=None):
        captured["timeout"] = timeout
        return FakeResp()

    monkeypatch.setattr(push_mod.requests, "post", fake_post)
    result = push_mod.push("hi")
    assert captured["timeout"] == push_mod.TIMEOUT_SECONDS
    assert "status code 200" in result


def test_push_fails_softly_on_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(push_mod.requests, "post", boom)
    # Must not raise - a Pushover hiccup can't be allowed to break the chat turn.
    result = push_mod.push("hi")
    assert "Could not reach" in result
