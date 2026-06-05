"""Shared test fixtures: env setup, TestClient, and Supabase row cleanup."""

import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)
os.environ["COOKIE_SECURE"] = "0"

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """A FastAPI TestClient."""
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_client(client):
    """A TestClient logged in as admin (cookie set)."""
    password = os.environ["ADMIN_PASSWORD"]
    response = client.post("/admin/login", json={"password": password})
    assert response.status_code == 200
    return client


@pytest.fixture
def conversation_id():
    """A random conversation id whose rows are deleted after the test.
    Purges both messages and archive so archive tests leave nothing behind.
    """
    cid = str(uuid.uuid4())
    yield cid
    db.get_client().table(db.TABLE).delete().eq("conversation_id", cid).execute()
    db.get_client().table(db.ARCHIVE_TABLE).delete().eq("conversation_id", cid).execute()


def make_conversation(cid: str, messages: list[dict]) -> list[dict]:
    """Insert a list of message dicts under a conversation id; return the rows."""
    rows = []
    for msg in messages:
        rows.append(
            db.insert_message(
                cid,
                msg["role"],
                msg["content"],
                conversation_name=msg.get("conversation_name"),
                tool_calls=msg.get("tool_calls"),
                needs_attention=msg.get("needs_attention", False),
                read=msg.get("read", False),
            )
        )
    return rows
