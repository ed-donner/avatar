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


def test_failed_logins_throttled_per_ip(client, monkeypatch):
    """5 failed attempts/IP each alert the owner; the 6th is 429'd (brute-force speed bump)."""
    alerts = []
    monkeypatch.setattr("app.push.notify_error", lambda *a, **k: alerts.append((a, k)))
    headers = {"Fly-Client-IP": "203.0.113.7"}  # a dedicated IP isolates this test's bucket
    for _ in range(5):
        assert client.post("/admin/login", json={"password": "wrong"}, headers=headers).status_code == 401
    assert client.post("/admin/login", json={"password": "wrong"}, headers=headers).status_code == 429
    assert len(alerts) == 5  # one alert per failed attempt (not the throttled 6th)


def test_successful_login_not_throttled(client):
    """Only failures count, so a correct password is never blocked (and one IP can't lock another)."""
    password = os.environ["ADMIN_PASSWORD"]
    other = {"Fly-Client-IP": "203.0.113.8"}
    for _ in range(5):  # exhaust a DIFFERENT IP's failed-attempt budget
        client.post("/admin/login", json={"password": "wrong"}, headers={"Fly-Client-IP": "203.0.113.9"})
    assert client.post("/admin/login", json={"password": password}, headers=other).status_code == 200
