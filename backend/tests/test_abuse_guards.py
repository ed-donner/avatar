"""Abuse guards: over-long message truncation and per-conversation rate limiting."""

from limits import parse

from app.main import (
    MAX_MESSAGE_CHARS,
    TRUNCATION_NOTE,
    clamp_message,
)


def test_clamp_message_leaves_short_text_unchanged():
    text = "a normal length question about your courses"
    assert clamp_message(text) == text


def test_clamp_message_boundary_is_inclusive():
    exactly = "x" * MAX_MESSAGE_CHARS
    assert clamp_message(exactly) == exactly
    assert clamp_message(exactly + "x") != exactly + "x"


def test_clamp_message_truncates_and_appends_note():
    text = "y" * (MAX_MESSAGE_CHARS + 5_000)
    clamped = clamp_message(text)
    assert clamped == "y" * MAX_MESSAGE_CHARS + " " + TRUNCATION_NOTE
    assert clamped.endswith(TRUNCATION_NOTE)
    # the original content is capped at the limit (the note is the only extra)
    assert len(clamped) == MAX_MESSAGE_CHARS + 1 + len(TRUNCATION_NOTE)


def test_chat_rate_is_twenty_per_minute():
    from app import main

    assert main._chat_rate.amount == 20
    assert main._chat_rate.GRANULARITY.seconds == 60


def test_rate_limit_returns_429_after_the_cap(client, conversation_id, monkeypatch):
    """The (N+1)th message from one conversation_id is rejected with 429, no model call."""
    monkeypatch.setattr("app.main._chat_rate", parse("3/minute"))

    body = {"conversation_id": conversation_id, "message": "Q2", "visitor_name": "RL"}
    for _ in range(3):
        assert client.post("/api/chat", json=body).status_code == 200  # instant, no LLM

    blocked = client.post("/api/chat", json=body)
    assert blocked.status_code == 429
    assert "slow down" in blocked.json()["detail"].lower()


def test_rate_limit_is_per_conversation(client, monkeypatch):
    """A different conversation_id has its own independent budget."""
    monkeypatch.setattr("app.main._chat_rate", parse("1/minute"))
    import uuid

    cids = [str(uuid.uuid4()), str(uuid.uuid4())]
    try:
        for cid in cids:
            body = {"conversation_id": cid, "message": "Q2", "visitor_name": "RL"}
            assert client.post("/api/chat", json=body).status_code == 200  # first is fine
            assert client.post("/api/chat", json=body).status_code == 429  # second over cap
    finally:
        from app import db

        for cid in cids:
            db.get_client().table(db.TABLE).delete().eq("conversation_id", cid).execute()
