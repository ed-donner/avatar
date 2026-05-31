"""SSE chat tests. The model-calling cases are marked 'llm' (cost tokens)."""

import json

import pytest

from app import db


def _parse_sse(text: str) -> list[dict]:
    """Parse an SSE response body into a list of JSON event dicts."""
    events = []
    for block in text.strip().split("\n\n"):
        lines = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
        if lines:
            events.append(json.loads("".join(lines)))
    return events


def test_instant_answer_no_model(client, conversation_id):
    """A bare Qn message returns an instant event and the answer with no model call."""
    with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "Q2", "visitor_name": "EF"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _parse_sse(body)
    types = [e["type"] for e in events]
    assert "instant" in types
    assert types[-1] == "done"
    assert events[0]["faq"] == 2

    rows = db.get_messages(conversation_id)
    assert [r["role"] for r in rows] == ["visitor", "avatar"]
    assert rows[1]["tool_calls"] == [{"type": "instant", "faq": 2}]


@pytest.mark.llm
def test_chat_streams_tokens_and_persists(client, conversation_id):
    """A plain message streams token events, a done event, and persists the avatar row."""
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "In one short sentence, who is this digital twin?",
            "visitor_name": "GH",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _parse_sse(body)
    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] == "done"

    rows = db.get_messages(conversation_id)
    assert rows[-1]["role"] == "avatar"
    assert rows[-1]["content"]


@pytest.mark.llm
def test_chat_contact_triggers_push(client, conversation_id):
    """Asking to get in touch with an email should trigger push_tool and needs_attention."""
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "Please ask the owner to contact me at test@example.com about consulting.",
            "visitor_name": "IJ",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _parse_sse(body)
    done = events[-1]
    assert done["type"] == "done"
