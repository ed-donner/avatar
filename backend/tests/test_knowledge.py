"""Tests for the knowledge module: FAQ loading, lookup, and instant answers."""

from app import knowledge


def test_faqs_load():
    faqs = knowledge.faqs()
    assert len(faqs) > 0
    first = faqs[0]
    assert {"faq", "question", "answer"} <= set(first)


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
