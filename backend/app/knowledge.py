"""Knowledge sources: owner summary, LinkedIn text, and the numbered FAQ.

Provides the system-prompt building blocks plus the instant-answer (Qn)
shortcut that bypasses the language model.
"""

import json
import re
from functools import lru_cache

from pypdf import PdfReader

from app.config import get_settings

INSTANT_RE = re.compile(r"^q(\d{1,2})$", re.IGNORECASE)


@lru_cache
def summary_text() -> str:
    """The owner summary blurb."""
    path = get_settings().knowledge_dir / "summary.txt"
    return path.read_text(encoding="utf-8")


@lru_cache
def linkedin_text() -> str:
    """Extracted text of the owner's LinkedIn PDF."""
    path = get_settings().knowledge_dir / "linkedin.pdf"
    reader = PdfReader(str(path))
    parts = [page.extract_text() for page in reader.pages]
    return "".join(part for part in parts if part)


@lru_cache
def _load_faqs() -> tuple[list[dict], dict[int, dict]]:
    path = get_settings().knowledge_dir / "faq.jsonl"
    faqs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_number = {faq["faq"]: faq for faq in faqs}
    return faqs, by_number


def faqs() -> list[dict]:
    """All FAQ entries as dicts with keys faq, question, answer."""
    return _load_faqs()[0]


def faq_by_number() -> dict[int, dict]:
    """FAQ entries keyed by their number."""
    return _load_faqs()[1]


def faq_list_text() -> str:
    """Numbered list of FAQ questions for the system prompt."""
    return "\n".join(f"{faq['faq']}. {faq['question']}" for faq in faqs())


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
    """The raw answer markdown for a FAQ number, for direct display."""
    faq = faq_by_number().get(number)
    if not faq:
        return "That question number was not found in the FAQ."
    return faq["answer"]
