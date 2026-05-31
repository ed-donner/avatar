"""Tests for system-prompt assembly (no model call)."""

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
