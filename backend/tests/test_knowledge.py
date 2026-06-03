"""Tests for the knowledge module: FAQ loading, lookup, and instant answers.

FAQ now comes from the Supabase faq table (seeded via scripts.seed_faq), so
these tests require the table to be populated.
"""

from app import db, knowledge


def test_knowledge_text_loads():
    text = knowledge.knowledge_text()
    assert text.strip()
    assert "Ed Donner" in text


def test_style_text_loads():
    text = knowledge.style_text()
    assert text.strip()


def test_faqs_load():
    faqs = knowledge.faqs()
    assert len(faqs) > 0
    first = faqs[0]
    assert {"faq", "question", "answer", "query"} <= set(first)


def test_faqs_come_from_db_table():
    """knowledge.faqs() reflects the faq table, with id->faq and concise->query."""
    rows = db.list_faqs()
    assert len(rows) == len(knowledge.faqs())
    by_number = knowledge.faq_by_number()
    first_row = rows[0]
    mapped = by_number[first_row["id"]]
    assert mapped["query"] == first_row["concise"]
    assert mapped["question"] == first_row["question"]


def test_reload_faqs_refreshes_cache():
    """reload_faqs() clears the cache so a later edit would be picked up."""
    knowledge.faqs()  # warm the cache
    knowledge.reload_faqs()
    assert knowledge.faqs()  # re-reads without error


def test_faq_by_number():
    by_number = knowledge.faq_by_number()
    assert 1 in by_number
    assert by_number[1]["faq"] == 1


def test_find_faq_known():
    text = knowledge.find_faq(1)
    assert "### Question 1" in text
    assert "### Answer" in text


def test_find_faq_unknown():
    assert "not found" in knowledge.find_faq(9999).lower()


def test_instant_faq_number_matches():
    assert knowledge.instant_faq_number("Q2") == 2
    assert knowledge.instant_faq_number("q12") == 12
    assert knowledge.instant_faq_number("  Q3  ") == 3


def test_instant_faq_number_non_matches():
    assert knowledge.instant_faq_number("question") is None
    assert knowledge.instant_faq_number("Q123") is None
    assert knowledge.instant_faq_number("hello Q2") is None


def test_get_instant_answer_restates_question_and_answer():
    faq = knowledge.faq_by_number()[2]
    reply = knowledge.get_instant_answer(2)
    assert reply.startswith(f"**Q2:** {faq['question']}")
    assert faq["answer"] in reply


def test_get_instant_answer_unknown():
    assert "not found" in knowledge.get_instant_answer(9999).lower()


def test_faq_list_text_non_empty():
    text = knowledge.faq_list_text()
    assert text
    assert "1." in text


def test_every_faq_has_a_query():
    assert all(faq.get("query") for faq in knowledge.faqs())


def test_faq_list_uses_query_not_full_question():
    by_number = knowledge.faq_by_number()
    text = knowledge.faq_list_text()
    one = by_number[1]
    assert f"1. {one['query']}" in text
    # the long original question is NOT dumped into the routing list
    assert one["question"] not in text


def test_find_faq_returns_original_question_and_answer():
    by_number = knowledge.faq_by_number()
    one = by_number[1]
    rendered = knowledge.find_faq(1)
    assert one["question"] in rendered
    assert one["answer"] in rendered
