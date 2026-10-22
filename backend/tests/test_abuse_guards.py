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


def test_malformed_requests_get_422_without_alerting(client, monkeypatch):
    """Hand-made bad ids and bodies are rejected before the database, so they don't page the owner."""
    alerts = []
    monkeypatch.setattr("app.push.notify_error", lambda summary, **kwargs: alerts.append(summary))
    cid = "88ae83e8-5046-4e7d-a8a8-a1f1a5f8bcb6"
    responses = [
        client.get("/api/conversations/not-a-uuid"),
        client.get(f"/api/conversations/{cid}?after=99999999999999999999"),  # beyond a Postgres bigint
        client.post("/api/chat", json={"conversation_id": "not-a-uuid", "message": "hi"}),
        client.post("/api/chat", content=b""),
        client.post("/api/chat", json=[1, 2]),
    ]
    assert [r.status_code for r in responses] == [422] * 5
    assert alerts == []


def test_admin_routes_check_auth_before_the_id(client):
    """An unauthenticated caller gets 401 whatever the id, and learns nothing from validation errors."""
    assert client.get("/admin/conversations/not-a-uuid").status_code == 401
    assert client.post("/admin/archive/not-a-uuid/restore").status_code == 401


def test_chat_error_hides_internal_details(client, conversation_id, monkeypatch):
    """A failed turn shows the visitor a generic message; the details go only to the owner's alert."""
    from app.main import CHAT_ERROR_MESSAGE

    alerts = []
    monkeypatch.setattr("app.push.notify_error", lambda summary, **kwargs: alerts.append(summary))

    async def failing_stream(transcript):
        raise RuntimeError("internal database detail")
        yield  # makes this an async generator

    monkeypatch.setattr("app.agent.stream_agent", failing_stream)
    response = client.post("/api/chat", json={"conversation_id": conversation_id, "message": "hello"})
    assert CHAT_ERROR_MESSAGE in response.text
    assert "internal database detail" not in response.text
    assert any("internal database detail" in alert for alert in alerts)
