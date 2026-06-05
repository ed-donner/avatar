"""Tests for the admin jsonl export endpoints (one JSON object per message row)."""

import json

from tests.conftest import make_conversation


def _parse_jsonl(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_export_routes_guarded(client):
    assert client.get("/admin/export/conversations").status_code == 401
    assert client.get("/admin/export/archive").status_code == 401


def test_export_conversations_jsonl(admin_client, conversation_id):
    make_conversation(
        conversation_id,
        [
            {"role": "visitor", "content": "export me", "conversation_name": "EX"},
            {"role": "avatar", "content": "exported reply"},
        ],
    )
    res = admin_client.get("/admin/export/conversations")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")
    assert 'filename="conversations-' in res.headers["content-disposition"]

    rows = _parse_jsonl(res.text)
    mine = [r for r in rows if r["conversation_id"] == conversation_id]
    assert [r["content"] for r in mine] == ["export me", "exported reply"]
    # one object per message row, mirroring the table columns
    assert {"id", "conversation_id", "role", "content", "created_at"} <= mine[0].keys()


def test_export_archive_jsonl(admin_client, conversation_id):
    make_conversation(conversation_id, [{"role": "visitor", "content": "to archive"}])
    admin_client.post(f"/admin/conversations/{conversation_id}/archive")

    res = admin_client.get("/admin/export/archive")
    assert res.status_code == 200
    assert 'filename="archive-' in res.headers["content-disposition"]

    rows = _parse_jsonl(res.text)
    mine = [r for r in rows if r["conversation_id"] == conversation_id]
    assert [r["content"] for r in mine] == ["to archive"]
