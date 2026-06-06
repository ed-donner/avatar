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


def _capture_posts(monkeypatch):
    posts = []

    class FakeResp:
        status_code = 200

    def fake_post(url, data=None, timeout=None):
        posts.append(data)
        return FakeResp()

    monkeypatch.setattr(push_mod.requests, "post", fake_post)
    return posts


def test_push_uses_bugle_by_default(monkeypatch):
    posts = _capture_posts(monkeypatch)
    push_mod.push("hello")
    assert posts[0]["sound"] == "bugle"


def test_notify_error_uses_gamelan(monkeypatch):
    posts = _capture_posts(monkeypatch)
    push_mod.notify_error("something broke", category="chat")
    assert posts[0]["sound"] == "gamelan"
    assert "something broke" in posts[0]["message"]


def test_notify_error_is_debounced(monkeypatch):
    posts = _capture_posts(monkeypatch)
    for i in range(6):  # well over the 3/hour budget for one category
        push_mod.notify_error(f"err {i}", category="chat")
    assert len(posts) == 3  # bursts are capped so errors can't spam / drain quota


def test_notify_error_debounce_is_per_category(monkeypatch):
    posts = _capture_posts(monkeypatch)
    push_mod.notify_error("chat error", category="chat")
    push_mod.notify_error("login error", category="login")
    assert {p["sound"] for p in posts} == {"gamelan"}
    assert len(posts) == 2  # different categories alert independently
