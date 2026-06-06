"""Tests for system-prompt assembly, the rules/style split, and the output cap."""

import asyncio

from app import agent, knowledge
from app.config import get_settings


def test_build_system_prompt_uses_knowledge_and_style():
    prompt = agent.build_system_prompt()
    owner = get_settings().owner_name
    assert owner in prompt
    assert "Nebula.io" in prompt  # from knowledge.md
    assert "self-deprecating" in prompt  # from style.md
    assert "faq_tool" in prompt  # FAQ section + tool usage


def test_old_sources_removed():
    """The LinkedIn PDF and summary loaders are gone; the prompt no longer references them."""
    assert not hasattr(knowledge, "linkedin_text")
    assert not hasattr(knowledge, "summary_text")
    assert "LinkedIn profile" not in agent.build_system_prompt()


def test_rules_separated_from_style():
    """Behaviour/safety rules live in rules.md; the code-coupled output contract stays in agent.py."""
    prompt = agent.build_system_prompt()
    assert "# Rules and guardrails" in prompt
    assert "Safety and security" in prompt  # from rules.md
    assert "Safety and security" not in knowledge.style_text()
    # the code-coupled output contract stays in agent.py, not in an owner-editable file
    assert "not code fences" in prompt
    assert "not code fences" not in knowledge.rules_text()


def test_knowledge_file_organization():
    """rules.md = owner-agnostic general rules; style.md = personal voice; knowledge.md = owner facts."""
    style, rules, know = knowledge.style_text(), knowledge.rules_text(), knowledge.knowledge_text()
    # answer length is a general rule any avatar would use -> rules.md
    assert "this is a chat not a lecture" in rules and "this is a chat not a lecture" not in style
    # the age-question deflection is personal voice -> style.md
    assert "how old is Ed Donner" in style and "how old is Ed Donner" not in rules
    # jobs/courses guidance is owner-specific content -> knowledge.md
    assert "take the courses in the order" in know and "take the courses in the order" not in rules
    # course-resource links are owner reference content -> knowledge.md, not style
    assert "ai-coder-vibe-coder-to-agentic-engineer" in know
    assert "ai-coder-vibe-coder-to-agentic-engineer" not in style
    # rules.md is owner-agnostic: no owner name leaks in
    assert "Ed Donner" not in rules


def test_knowledge_files_nest_under_prompt_headings():
    """knowledge/* files must top out at H2 so they nest under agent.py's H1 sections."""
    for text in (knowledge.knowledge_text(), knowledge.style_text(), knowledge.rules_text()):
        assert not text.lstrip().startswith("# ")  # no H1 at the top


def test_agent_has_output_token_cap():
    assert agent.build_agent().model_settings.max_tokens == agent.MAX_OUTPUT_TOKENS == 2000


# ---- Graceful handling of the hard output cap (no LLM call; Runner stubbed) ----


class _FakeServer:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _fake_result(turn_output_tokens: list[int]):
    """A streamed result with one raw_response per turn (each with its own usage).
    context_wrapper.usage is the cumulative total, mirroring the real SDK."""

    def _usage(ot):
        u = type("U", (), {})()
        u.output_tokens = ot
        return u

    responses = [type("R", (), {"usage": _usage(ot)})() for ot in turn_output_tokens]
    ctx = type("C", (), {"usage": _usage(sum(turn_output_tokens))})()

    class FakeResult:
        final_output = "A reply"
        raw_responses = responses
        context_wrapper = ctx

        async def stream_events(self):
            return
            yield  # makes this an async generator that yields nothing

    return FakeResult()


def _run_stream(monkeypatch, turn_output_tokens):
    monkeypatch.setattr(agent, "MCPServerStdio", _FakeServer)
    monkeypatch.setattr(agent.Runner, "run_streamed", lambda *a, **k: _fake_result(turn_output_tokens))

    async def collect():
        return [e async for e in agent.stream_agent("Visitor: hi\n\nReply as the Avatar:")]

    return asyncio.run(collect())


def test_output_cap_appends_note_when_truncated(monkeypatch):
    events = _run_stream(monkeypatch, [agent.MAX_OUTPUT_TOKENS])  # final response hit the ceiling
    final = events[-1]
    assert final["type"] == "_final"
    assert agent.LENGTH_NOTE in final["text"]  # stored row gets the note
    assert any(e["type"] == "token" and agent.LENGTH_NOTE in e["text"] for e in events)  # live too


def test_no_note_when_under_cap(monkeypatch):
    events = _run_stream(monkeypatch, [50])  # well under the cap
    assert events[-1]["text"] == "A reply"
    assert all(agent.LENGTH_NOTE not in e.get("text", "") for e in events)


def test_no_false_positive_note_on_multi_turn(monkeypatch):
    """A multi-turn browse can sum past the cap while the FINAL reply is short and complete -
    the note must key off the last response, not the cumulative total."""
    events = _run_stream(monkeypatch, [1500, 600])  # cumulative 2100 >= cap, last turn 600 < cap
    assert events[-1]["text"] == "A reply"
    assert all(agent.LENGTH_NOTE not in e.get("text", "") for e in events)
