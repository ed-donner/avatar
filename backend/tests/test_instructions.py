"""Tests for the additional-instructions feature (app_settings singleton).

The instructions live on a single shared row that feeds the live system prompt,
so every test that writes them restores the original value on teardown.
"""

import pytest

from app import agent, db


@pytest.fixture
def preserve_instructions():
    original = db.get_instructions()
    yield
    db.set_instructions(original)
    # Fail loudly if the live singleton wasn't restored (it feeds the real prompt).
    assert db.get_instructions() == original


def test_get_instructions_requires_admin(client):
    assert client.get("/admin/instructions").status_code == 401


def test_put_instructions_requires_admin(client):
    assert client.put("/admin/instructions", json={"instructions": "x"}).status_code == 401


def test_instructions_roundtrip(admin_client, preserve_instructions):
    text = "Pytest: emphasise the new Agentic AI course this week."
    put = admin_client.put("/admin/instructions", json={"instructions": text})
    assert put.status_code == 200
    assert put.json()["instructions"] == text
    got = admin_client.get("/admin/instructions")
    assert got.status_code == 200
    assert got.json()["instructions"] == text


def test_instructions_injected_last_for_cache_friendliness(preserve_instructions):
    marker = "ZZZ_PYTEST_INSTRUCTION_MARKER"
    db.set_instructions(marker)
    prompt = agent.build_system_prompt()
    assert marker in prompt
    assert "# Additional instructions" in prompt
    # The (per-turn, editable) instructions block is placed LAST so editing it doesn't
    # invalidate the long static prompt prefix that precedes it (prefix-based caching).
    assert prompt.index("# Additional instructions") > prompt.index("# Output format")
    assert prompt.rstrip().endswith(marker)


def test_instructions_empty_omits_section(preserve_instructions):
    db.set_instructions("")
    prompt = agent.build_system_prompt()
    assert "# Additional instructions" not in prompt
