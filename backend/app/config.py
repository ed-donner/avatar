"""Application settings loaded from the project-root .env file."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=True)


def _env(name: str, default: str = "") -> str:
    """Read an env var, stripping surrounding quotes.

    python-dotenv strips quotes from .env values, but Docker's --env-file keeps
    them, so the same .env must be normalised here to work both ways.
    """
    value = os.getenv(name, default)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


@dataclass(frozen=True)
class Settings:
    """Frozen view of the environment values the app needs."""

    openrouter_api_key: str
    model: str
    owner_name: str
    admin_password: str
    pushover_user: str
    pushover_token: str
    supabase_url: str
    supabase_key: str
    session_secret: str
    cookie_secure: bool
    frontend_dist: Path
    knowledge_dir: Path


@lru_cache
def get_settings() -> Settings:
    """Return cached settings read from the environment."""
    admin_password = _env("ADMIN_PASSWORD")
    if not admin_password:
        raise RuntimeError(
            "ADMIN_PASSWORD must be set. Without it the admin panel would accept an empty "
            "password and sign session cookies with a guessable default (fail-open)."
        )
    return Settings(
        openrouter_api_key=_env("OPENROUTER_API_KEY"),
        model=_env("MODEL", "openai/gpt-5.4-nano"),
        owner_name=_env("OWNER_NAME", "Ed Donner"),
        admin_password=admin_password,
        pushover_user=_env("PUSHOVER_USER"),
        pushover_token=_env("PUSHOVER_TOKEN"),
        supabase_url=_env("SUPABASE_URL"),
        supabase_key=_env("SUPABASE_KEY"),
        session_secret=_env("SESSION_SECRET") or f"avatar::{admin_password}",
        cookie_secure=_env("COOKIE_SECURE") == "1",
        frontend_dist=Path(_env("FRONTEND_DIST") or REPO_ROOT / "frontend" / "dist"),
        knowledge_dir=Path(_env("KNOWLEDGE_DIR") or REPO_ROOT / "knowledge"),
    )
