"""Connectivity check for the Supabase messages table.

Verifies that the credentials in the project-root .env work and that the
expected table is reachable via the Data API using the secret key.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from supabase import Client, create_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

EXPECTED_COLUMNS = {
    "id",
    "conversation_id",
    "conversation_name",
    "role",
    "content",
    "tool_calls",
    "needs_attention",
    "read",
    "created_at",
}

# MORE.md tables (see README "Setup for MORE requirements"). archive mirrors messages.
ARCHIVE_COLUMNS = EXPECTED_COLUMNS
APP_SETTINGS_COLUMNS = {"id", "instructions", "updated_at"}
FAQ_COLUMNS = {"id", "concise", "question", "answer"}

ZERO_UUID = "00000000-0000-0000-0000-000000000000"
SENTINEL_ID = -1  # real rows use positive ids, so this never collides


@pytest.fixture(scope="module")
def client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def test_env_present():
    assert os.environ.get("SUPABASE_URL", "").startswith("https://")
    assert os.environ.get("SUPABASE_KEY", "").startswith("sb_secret_")


def test_messages_table_reachable(client: Client):
    """The table is queryable through the Data API with the secret key."""
    result = client.table("messages").select("*").limit(1).execute()
    assert isinstance(result.data, list)


def test_insert_and_delete_roundtrip(client: Client):
    """A full write/read/delete cycle works and stores the expected columns."""
    conversation_id = "00000000-0000-0000-0000-000000000000"
    inserted = (
        client.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": "visitor",
                "content": "connectivity test",
            }
        )
        .execute()
    )
    row = inserted.data[0]
    try:
        assert EXPECTED_COLUMNS.issubset(row.keys())
        assert row["role"] == "visitor"
        assert row["needs_attention"] is False
        assert row["read"] is False
    finally:
        client.table("messages").delete().eq("id", row["id"]).execute()


def test_archive_table_roundtrip(client: Client):
    """The archive table mirrors messages and accepts an explicit id (for restore)."""
    inserted = (
        client.table("archive")
        .insert(
            {
                "id": SENTINEL_ID,
                "conversation_id": ZERO_UUID,
                "role": "visitor",
                "content": "archive connectivity test",
            }
        )
        .execute()
    )
    row = inserted.data[0]
    try:
        assert ARCHIVE_COLUMNS.issubset(row.keys())
        assert row["id"] == SENTINEL_ID
    finally:
        client.table("archive").delete().eq("id", SENTINEL_ID).execute()


def test_app_settings_singleton(client: Client):
    """The app_settings singleton row (id=1) exists with the instructions column."""
    result = client.table("app_settings").select("*").eq("id", 1).execute()
    assert len(result.data) == 1, "expected the seeded app_settings row (id=1)"
    assert APP_SETTINGS_COLUMNS.issubset(result.data[0].keys())


def test_faq_table_roundtrip(client: Client):
    """The faq table has id/concise/question/answer and accepts an explicit id."""
    inserted = (
        client.table("faq")
        .insert(
            {
                "id": SENTINEL_ID,
                "concise": "connectivity test",
                "question": "connectivity test question",
                "answer": "connectivity test answer",
            }
        )
        .execute()
    )
    row = inserted.data[0]
    try:
        assert FAQ_COLUMNS.issubset(row.keys())
        assert row["id"] == SENTINEL_ID
    finally:
        client.table("faq").delete().eq("id", SENTINEL_ID).execute()
