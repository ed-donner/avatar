"""Tests for the web-fetch MCP wiring (prompt + agent construction, no model call)."""

from app import agent, knowledge


def test_fetch_text_loads():
    text = knowledge.fetch_text()
    assert "edwarddonner.com/curriculum" in text
    assert "raw.githubusercontent.com" in text


def test_prompt_has_fetch_section_and_constraint():
    prompt = agent.build_system_prompt()
    assert "Web browsing (fetch tool)" in prompt
    assert "Never use it for general web browsing" in prompt  # the no-general-browsing constraint
    assert "raw.githubusercontent.com" in prompt  # the owner source list (fetch.md) is injected


def test_build_agent_attaches_mcp_servers():
    sentinel = object()
    assert agent.build_agent(mcp_servers=[sentinel]).mcp_servers == [sentinel]
    # default: no MCP servers when none are supplied
    assert agent.build_agent().mcp_servers == []


def test_fetch_params_use_preinstalled_binary():
    # Launched directly (uv tool install), not via uvx, so there's no per-request download.
    assert agent.FETCH_PARAMS["command"] == "mcp-server-fetch"


# ---- The allow-list enforced in code (OwnerSitesFetch), not just in the prompt ----

ALLOWED = [
    "https://edwarddonner.com/curriculum/",
    "https://www.edwarddonner.com/2026/10/14/ai-fde-the-forward-deployed-engineer-agentic-ai-architect/",
    "http://edwarddonner.com/",
    "https://raw.githubusercontent.com/ed-donner/llm_engineering/main/README.md",
    "https://api.github.com/repos/ed-donner/llm_engineering/git/trees/main?recursive=1",
    "https://github.com/ed-donner/avatar",
]

BLOCKED = [
    "https://example.com/",
    "https://edwarddonner.com.evil.example/",  # a look-alike host
    "https://evil.example/edwarddonner.com/",
    "https://edwarddonner.com@evil.example/",  # a login part hiding the real host
    "https://raw.githubusercontent.com/someone-else/repo/main/x.py",
    "https://github.com/ed-donnerx/repo",  # a longer owner name
    "https://raw.githubusercontent.com/ed-donner/../someone-else/main/x.py",  # climbing out of the prefix
    "https://raw.githubusercontent.com/ed-donner/%2e%2e/someone-else/main/x.py",
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://localhost:8000/api/admin/conversations",
    "https://edwarddonner.com:8443/",
    "file:///etc/passwd",
    "",
]


def test_fetch_allowed_prefixes_come_from_fetch_md():
    assert "https://edwarddonner.com/" in knowledge.fetch_allowed_prefixes()
    assert "https://raw.githubusercontent.com/ed-donner/" in knowledge.fetch_allowed_prefixes()


def test_fetch_allows_only_the_owner_sites():
    assert [u for u in ALLOWED if not agent.fetch_allowed(u)] == []
    assert [u for u in BLOCKED if agent.fetch_allowed(u)] == []


def test_blocked_fetch_never_reaches_the_server():
    """A blocked URL gets an error result back without the server being started; an allowed URL is
    passed on to the real call_tool (which fails here only because the server isn't connected)."""
    import asyncio

    import pytest
    from agents.exceptions import UserError

    server = agent.OwnerSitesFetch(agent.FETCH_PARAMS)
    result = asyncio.run(server.call_tool("fetch", {"url": "http://169.254.169.254/latest/meta-data/"}))
    assert result.isError and result.content[0].text.startswith("Blocked")
    with pytest.raises(UserError, match="not initialized"):
        asyncio.run(server.call_tool("fetch", {"url": "https://edwarddonner.com/curriculum/"}))
