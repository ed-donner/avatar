"""Tests for the admin API: listing, opening, posting, and resolving."""

from app import db
from tests.conftest import make_conversation


def test_admin_routes_guarded(client):
    assert client.get("/admin/conversations").status_code == 401
    assert client.get("/admin/conversations/abc").status_code == 401
    assert client.post("/admin/conversations/abc/messages", json={"content": "hi"}).status_code == 401
    assert client.post("/admin/conversations/abc/resolve").status_code == 401


def test_list_conversations_includes_thread(admin_client, conversation_id):
    make_conversation(
        conversation_id,
        [
            {"role": "visitor", "content": "need help", "conversation_name": "CD", "read": False},
            {"role": "avatar", "content": "flagging it", "needs_attention": True, "read": False},
        ],
    )
    summaries = admin_client.get("/admin/conversations").json()
    summary = next(s for s in summaries if s["conversation_id"] == conversation_id)
    assert summary["conversation_name"] == "CD"
    assert summary["message_count"] == 2
    assert summary["unread"] is True
    assert summary["needs_attention"] is True
    assert summary["preview"] == "flagging it"


def test_open_conversation_clears_unread_and_attention(admin_client, conversation_id):
    make_conversation(
        conversation_id,
        [
            {"role": "visitor", "content": "hi", "read": False},
            {"role": "avatar", "content": "flagged", "needs_attention": True, "read": False},
        ],
    )
    thread = admin_client.get(f"/admin/conversations/{conversation_id}").json()
    assert thread["conversation_id"] == conversation_id
    assert len(thread["messages"]) == 2

    rows = db.get_messages(conversation_id)
    assert all(r["read"] for r in rows)
    assert all(not r["needs_attention"] for r in rows)


def test_post_human_message(admin_client, conversation_id):
    make_conversation(conversation_id, [{"role": "visitor", "content": "hello"}])
    response = admin_client.post(
        f"/admin/conversations/{conversation_id}/messages",
        json={"content": "I am here, the human"},
    )
    assert response.status_code == 200
    message = response.json()
    assert message["role"] == "human"
    assert message["content"] == "I am here, the human"
    assert message["read"] is True
    assert message["needs_attention"] is False


def test_resolve_clears_attention(admin_client, conversation_id):
    make_conversation(
        conversation_id,
        [{"role": "avatar", "content": "flagged", "needs_attention": True}],
    )
    response = admin_client.post(f"/admin/conversations/{conversation_id}/resolve")
    assert response.status_code == 200
    rows = db.get_messages(conversation_id)
    assert all(not r["needs_attention"] for r in rows)
