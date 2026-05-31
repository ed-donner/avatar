"""Admin authentication: signed httpOnly cookie via itsdangerous."""

import secrets

from fastapi import Cookie, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

COOKIE_NAME = "avatar_admin"
MAX_AGE = 60 * 60 * 24 * 7  # one week


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="avatar-admin")


def verify_password(password: str) -> bool:
    """Constant-time comparison against the configured admin password."""
    return secrets.compare_digest(password, get_settings().admin_password)


def set_session_cookie(response: Response) -> None:
    """Issue a signed admin session cookie on the response."""
    token = _serializer().dumps("admin")
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the admin session cookie."""
    response.delete_cookie(COOKIE_NAME)


def is_authenticated(token: str | None) -> bool:
    """True when the cookie token is a valid, unexpired admin session."""
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_admin(avatar_admin: str | None = Cookie(default=None)) -> None:
    """FastAPI dependency that rejects requests without a valid admin cookie."""
    if not is_authenticated(avatar_admin):
        raise HTTPException(status_code=401, detail="Not authenticated")
