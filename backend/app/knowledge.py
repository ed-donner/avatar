"""Knowledge sources: the owner profile, response style, and the numbered FAQ.

Provides the system-prompt building blocks plus the instant-answer (Qn)
shortcut that bypasses the language model.
"""

import re
from functools import lru_cache

from app import db
from app.config import get_settings

INSTANT_RE = re.compile(r"^q(\d{1,3})$", re.IGNORECASE)  # Q1..Q999 (ids can grow via the editor)


@lru_cache
def knowledge_text() -> str:
    """The owner profile (knowledge.md), included in the system prompt."""
    return (get_settings().knowledge_dir / "knowledge.md").read_text(encoding="utf-8")


@lru_cache
def style_text() -> str:
    """The response style, voice and safety guidance (style.md)."""
    return (get_settings().knowledge_dir / "style.md").read_text(encoding="utf-8")


@lru_cache
def _load_faqs() -> tuple[list[dict], dict[int, dict]]:
    """Load FAQs from the Supabase faq table (the source of truth).

    Table columns id/concise are mapped to the module's established faq/query
    keys so the rest of the code is unchanged. Cached for the hot path; call
    reload_faqs() after the admin edits the FAQ so the next access re-reads.
    """
    faqs = [
        {"faq": row["id"], "question": row["question"], "answer": row["answer"], "query": row["concise"]}
        for row in db.list_faqs()
    ]
    by_number = {faq["faq"]: faq for faq in faqs}
    return faqs, by_number


def reload_faqs() -> None:
    """Drop the cached FAQs so the next access re-reads the table."""
    _load_faqs.cache_clear()


def faqs() -> list[dict]:
    """All FAQ entries as dicts with keys faq, question, answer."""
    return _load_faqs()[0]


def faq_by_number() -> dict[int, dict]:
    """FAQ entries keyed by their number."""
    return _load_faqs()[1]


def faq_list_text() -> str:
    """Numbered list of concise FAQ queries (routing phrasings) for the system prompt.

    The list uses the short ``query`` of each entry so the model can match a
    visitor's question to a number; ``faq_tool`` then returns the full original
    question and answer.
    """
    return "\n".join(f"{faq['faq']}. {faq['query']}" for faq in faqs())


def find_faq(number: int) -> str:
    """Render a full FAQ entry, or a not-found message for an unknown number."""
    faq = faq_by_number().get(number)
    if not faq:
        return "That question number was not found in the FAQ."
    return f"### Question {number}\n{faq['question']}\n### Answer\n{faq['answer']}"


def instant_faq_number(message: str) -> int | None:
    """Return the FAQ number for a bare 'Qn' message, else None."""
    match = INSTANT_RE.match(message.strip())
    return int(match.group(1)) if match else None


def get_instant_answer(number: int) -> str:
    """The visitor-facing reply for a 'Qn' shortcut.

    Restates the question (so the terse 'Qn' has context) and then gives the
    answer, e.g. '**Q3:** ...question...\\n\\n...answer...'.
    """
    faq = faq_by_number().get(number)
    if not faq:
        return "That question number was not found in the FAQ."
    return f"**Q{number}:** {faq['question']}\n\n{faq['answer']}"
