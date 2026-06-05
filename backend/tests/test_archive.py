"""Tests for the admin archive endpoints (archive table).

Every test creates throwaway conversations (random ids) and the archive_ids
fixture purges them from BOTH messages and archive on teardown, so no real user
conversation is ever touched. The destructive bulk endpoint is exercised only
with its selector monkeypatched to return a single throwaway id (see below).
"""

import uuid
from datetime import datetime, timezone

import pytest

from app import db
from tests.conftest import make_conversation


@pytest.fixture
def archive_ids():
    """Conversation ids to purge from messages AND archive after the test."""
    ids: list[str] = []
    yield ids
    for cid in ids:
        db.get_client().table(db.TABLE).delete().eq("conversation_id", cid).execute()
        db.get_client().table(db.ARCHIVE_TABLE).delete().eq("conversation_id", cid).execute()


def test_archive_routes_guarded(client):
    cid = str(uuid.uuid4())
    assert client.post(f"/admin/conversations/{cid}/archive").status_code == 401
    assert client.post("/admin/archive-inactive").status_code == 401
    assert client.get("/admin/archive").status_code == 401
    assert client.get(f"/admin/archive/{cid}").status_code == 401
    assert client.post(f"/admin/archive/{cid}/restore").status_code == 401


def test_archive_moves_conversation_out_of_inbox(admin_client, archive_ids):
    cid = str(uuid.uuid4())
    archive_ids.append(cid)
    make_conversation(
        cid,
        [
            {"role": "visitor", "content": "hello", "conversation_name": "AZ"},
            {"role": "avatar", "content": "hi there"},
        ],
    )

    res = admin_client.post(f"/admin/conversations/{cid}/archive")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "messages": 2}

    # gone from the live inbox, present in the archive list
    assert db.get_messages(cid) == []
    archived = admin_client.get("/admin/archive").json()
    summary = next(s for s in archived if s["conversation_id"] == cid)
    assert summary["conversation_name"] == "AZ"
    assert summary["message_count"] == 2

    # readable read-only without changing anything
    thread = admin_client.get(f"/admin/archive/{cid}").json()
    assert [m["content"] for m in thread["messages"]] == ["hello", "hi there"]
    assert len(db.get_archived_messages(cid)) == 2


def test_restore_reassigns_ids_preserves_content(admin_client, archive_ids):
    cid = str(uuid.uuid4())
    archive_ids.append(cid)
    rows = make_conversation(
        cid,
        [
            {"role": "visitor", "content": "a", "read": True},
            {"role": "avatar", "content": "b", "read": False, "needs_attention": True},
            {"role": "human", "content": "c", "read": True},
        ],
    )
    orig_ids = [r["id"] for r in rows]
    orig_created = [r["created_at"] for r in rows]

    admin_client.post(f"/admin/conversations/{cid}/archive")
    # archive preserves the original ids and timestamps
    archived = db.get_archived_messages(cid)
    assert [r["id"] for r in archived] == orig_ids
    assert [r["created_at"] for r in archived] == orig_created

    res = admin_client.post(f"/admin/archive/{cid}/restore")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "messages": 3}

    back = db.get_messages(cid)
    assert db.get_archived_messages(cid) == []
    assert [r["content"] for r in back] == ["a", "b", "c"]  # order preserved
    assert [r["created_at"] for r in back] == orig_created  # timestamps preserved
    assert [r["read"] for r in back] == [True, False, True]  # read state preserved
    assert [r["needs_attention"] for r in back] == [False, True, False]  # attention preserved
    assert [r["id"] for r in back] != orig_ids  # ids reassigned (messages.id is identity)


def test_archive_is_idempotent_after_partial_failure(admin_client, archive_ids):
    """Simulate an insert-succeeded/delete-failed state (rows in BOTH tables) and
    confirm a re-archive converges instead of crashing on the archive primary key."""
    cid = str(uuid.uuid4())
    archive_ids.append(cid)
    rows = make_conversation(cid, [{"role": "visitor", "content": "dup"}, {"role": "avatar", "content": "dup2"}])
    # Pre-seed the archive with the same rows (ids included) - the half-finished state.
    db.get_client().table(db.ARCHIVE_TABLE).insert(rows).execute()

    res = admin_client.post(f"/admin/conversations/{cid}/archive")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "messages": 2}
    assert db.get_messages(cid) == []
    assert len(db.get_archived_messages(cid)) == 2  # converged: not duplicated, not a crash


def test_archive_of_missing_conversation_is_noop(admin_client):
    cid = str(uuid.uuid4())
    assert admin_client.post(f"/admin/conversations/{cid}/archive").json() == {"ok": True, "messages": 0}


def test_inactive_conversation_ids_selects_only_old(archive_ids):
    """Read-only: an old throwaway convo is selected, a fresh one is not."""
    old_cid, new_cid = str(uuid.uuid4()), str(uuid.uuid4())
    archive_ids.extend([old_cid, new_cid])
    client = db.get_client()
    client.table(db.TABLE).insert(
        {"conversation_id": old_cid, "role": "visitor", "content": "old",
         "created_at": "2020-01-01T00:00:00+00:00"}
    ).execute()
    client.table(db.TABLE).insert(
        {"conversation_id": new_cid, "role": "visitor", "content": "new"}
    ).execute()

    cutoff = datetime(2021, 1, 1, tzinfo=timezone.utc)
    ids = db.inactive_conversation_ids(cutoff)
    assert old_cid in ids
    assert new_cid not in ids


def test_archive_inactive_archives_only_selected(admin_client, archive_ids, monkeypatch):
    """The destructive bulk path, made safe by stubbing the selector to one id."""
    cid = str(uuid.uuid4())
    archive_ids.append(cid)
    make_conversation(cid, [{"role": "visitor", "content": "x"}, {"role": "avatar", "content": "y"}])

    monkeypatch.setattr(db, "inactive_conversation_ids", lambda cutoff: [cid])
    res = admin_client.post("/admin/archive-inactive")
    assert res.status_code == 200
    assert res.json() == {"conversations": 1, "messages": 2}

    assert db.get_messages(cid) == []
    assert len(db.get_archived_messages(cid)) == 2
