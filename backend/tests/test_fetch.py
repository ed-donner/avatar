"""Tests for the web-fetch wiring: prompt, agent construction, and the URL allow-list."""

import asyncio

import pytest

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


def test_build_agent_includes_extra_tools():
    sentinel = object()
    tools = agent.build_agent(extra_tools=[sentinel]).tools
    assert sentinel in tools
    assert agent.faq_tool in tools and agent.push_tool in tools
    # default: just the two function tools, no extras
    assert sentinel not in agent.build_agent().tools


def test_fetch_params_use_preinstalled_binary():
    # Launched directly (uv tool install), not via uvx, so there's no per-request download.
    assert agent.FETCH_PARAMS["command"] == "mcp-server-fetch"


@pytest.mark.parametrize(
    "url",
    [
        "https://edwarddonner.com/curriculum",
        "https://www.edwarddonner.com/2026/02/17/ai-coder-vibe-coder-to-agentic-engineer/",
        "https://raw.githubusercontent.com/ed-donner/llm_engineering/main/README.md",
        "https://api.github.com/repos/ed-donner/agents/git/trees/main?recursive=1",
        "https://github.com/ed-donner/production",
    ],
)
def test_fetch_allowed_owner_sources(url):
    assert agent._fetch_allowed(url) is True


def test_stream_agent_degrades_when_mcp_unavailable(monkeypatch):
    """If the fetch MCP server can't start, the turn still produces a reply (no fetch tool)."""

    class BoomServer:
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self):
            raise RuntimeError("mcp-server-fetch not available")

        async def cleanup(self):
            pass

    monkeypatch.setattr(agent, "MCPServerStdio", BoomServer)

    seen = {}

    async def fake_run(transcript, fetch_tool):
        seen["fetch_tool"] = fetch_tool
        yield {"type": "_final", "text": "ok", "tool_calls": []}

    monkeypatch.setattr(agent, "_stream_run", fake_run)

    async def collect():
        return [e async for e in agent.stream_agent("Visitor: hi\n\nReply as the Avatar:")]

    events = asyncio.run(collect())
    assert seen["fetch_tool"] is None  # degraded: ran without the fetch tool
    assert events[-1] == {"type": "_final", "text": "ok", "tool_calls": []}


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://127.0.0.1:8000/admin",  # loopback
        "http://10.0.0.5/",  # private range
        "http://localhost/",  # internal hostname
        "https://evil.com/",  # arbitrary host
        "https://raw.githubusercontent.com@evil.com/x",  # userinfo trick -> host is evil.com
        "https://raw.githubusercontent.com/someone-else/repo/main/x",  # wrong github owner
        "https://github.com/microsoft/vscode",  # wrong github owner
        "file:///etc/passwd",  # non-http scheme
        "gopher://edwarddonner.com/",  # non-http scheme
        "not a url",
    ],
)
def test_fetch_allowed_blocks_everything_else(url):
    assert agent._fetch_allowed(url) is False
