"""Tests for the admin FAQ CRUD endpoints (faq table).

Every test creates throwaway rows (id = max+1, so >= 62) and deletes them on
teardown, so the real seeded FAQ rows (1..61) are never modified or removed.
"""

import pytest

from app import db, knowledge


@pytest.fixture
def faq_cleanup():
    created_ids: list[int] = []
    yield created_ids
    for fid in created_ids:
        db.delete_faq(fid)
    knowledge.reload_faqs()


def test_faq_list_requires_admin(client):
    assert client.get("/admin/faq").status_code == 401


def test_faq_create_requires_admin(client):
    body = {"concise": "x", "question": "x", "answer": "x"}
    assert client.post("/admin/faq", json=body).status_code == 401


def test_faq_update_requires_admin(client):
    body = {"concise": "x", "question": "x", "answer": "x"}
    assert client.put("/admin/faq/1", json=body).status_code == 401


def test_faq_delete_requires_admin(client):
    assert client.delete("/admin/faq/1").status_code == 401


def test_faq_crud_roundtrip(admin_client, faq_cleanup):
    body = {"concise": "pytest routing phrase", "question": "Pytest Q?", "answer": "Pytest A."}
    created = admin_client.post("/admin/faq", json=body)
    assert created.status_code == 200
    faq = created.json()
    faq_cleanup.append(faq["id"])
    assert faq["id"] >= 62  # after the seeded 1..61
    assert faq["concise"] == body["concise"]

    # appears in the listing
    listing = admin_client.get("/admin/faq").json()
    assert any(f["id"] == faq["id"] for f in listing)

    # reflected in the knowledge layer (reload_faqs invalidated the cache)
    assert knowledge.faq_by_number()[faq["id"]]["query"] == body["concise"]

    # update
    upd = admin_client.put(
        f"/admin/faq/{faq['id']}",
        json={"concise": "updated phrase", "question": "Pytest Q2?", "answer": "Pytest A2."},
    )
    assert upd.status_code == 200
    assert upd.json()["concise"] == "updated phrase"
    assert knowledge.faq_by_number()[faq["id"]]["query"] == "updated phrase"

    # delete
    assert admin_client.delete(f"/admin/faq/{faq['id']}").status_code == 200
    after = admin_client.get("/admin/faq").json()
    assert not any(f["id"] == faq["id"] for f in after)


def test_faq_update_missing_returns_404(admin_client):
    body = {"concise": "x", "question": "x", "answer": "x"}
    assert admin_client.put("/admin/faq/999999", json=body).status_code == 404


def test_faq_create_rejects_blank_fields(admin_client):
    blank = {"concise": "  ", "question": "", "answer": "\n"}
    assert admin_client.post("/admin/faq", json=blank).status_code == 422
