"""Tests for the public API: config and conversation retrieval."""

import os

from tests.conftest import make_conversation


def test_config_returns_owner_name(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["owner_name"] == os.environ.get("OWNER_NAME", "Ed Donner")


def test_get_conversation_returns_messages(client, conversation_id):
    make_conversation(
        conversation_id,
        [
            {"role": "visitor", "content": "hello there", "conversation_name": "AB"},
            {"role": "avatar", "content": "hi, how can I help"},
        ],
    )
    response = client.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert body["conversation_name"] == "AB"
    assert [m["role"] for m in body["messages"]] == ["visitor", "avatar"]
    assert body["messages"][0]["content"] == "hello there"


def test_get_conversation_after_filter(client, conversation_id):
    rows = make_conversation(
        conversation_id,
        [
            {"role": "visitor", "content": "first"},
            {"role": "avatar", "content": "second"},
            {"role": "visitor", "content": "third"},
        ],
    )
    first_id = rows[0]["id"]
    response = client.get(f"/api/conversations/{conversation_id}?after={first_id}")
    contents = [m["content"] for m in response.json()["messages"]]
    assert contents == ["second", "third"]
