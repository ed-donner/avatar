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
