"""Tests for admin authentication and route guarding."""

import os

from app.auth import COOKIE_NAME

GUARDED = "/admin/conversations"


def test_no_cookie_rejected(client):
    assert client.get(GUARDED).status_code == 401


def test_me_unauthenticated(client):
    assert client.get("/admin/me").status_code == 401


def test_wrong_password_rejected(client):
    response = client.post("/admin/login", json={"password": "definitely-wrong"})
    assert response.status_code == 401


def test_correct_password_grants_access(client):
    password = os.environ["ADMIN_PASSWORD"]
    login = client.post("/admin/login", json={"password": password})
    assert login.status_code == 200
    assert client.get("/admin/me").status_code == 200
    assert client.get(GUARDED).status_code == 200


def test_tampered_cookie_rejected(client):
    password = os.environ["ADMIN_PASSWORD"]
    client.post("/admin/login", json={"password": password})
    client.cookies.set(COOKIE_NAME, "tampered.token.value")
    assert client.get(GUARDED).status_code == 401


def test_logout_revokes_access(client):
    password = os.environ["ADMIN_PASSWORD"]
    client.post("/admin/login", json={"password": password})
    assert client.get(GUARDED).status_code == 200
    client.post("/admin/logout")
    assert client.get(GUARDED).status_code == 401
