"""Supabase access layer: the only module that talks to the database."""

from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings

TABLE = "messages"
FAQ_TABLE = "faq"
SETTINGS_TABLE = "app_settings"


PAGE = 1000  # PostgREST's default (and max) rows per request


@lru_cache
def get_client() -> Client:
    """Cached Supabase client."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def _all_rows(table: str) -> list[dict]:
    """Every row of a table ordered by id, paging past PostgREST's row cap."""
    client = get_client()
    rows: list[dict] = []
    start = 0
    while True:
        batch = client.table(table).select("*").order("id").range(start, start + PAGE - 1).execute().data
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows
        start += PAGE


def insert_message(
    conversation_id: str,
    role: str,
    content: str,
    *,
    conversation_name: str | None = None,
    tool_calls: list | None = None,
    needs_attention: bool = False,
    read: bool = False,
) -> dict:
    """Insert one message row and return it."""
    row = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "conversation_name": conversation_name,
        "tool_calls": tool_calls,
        "needs_attention": needs_attention,
        "read": read,
    }
    result = get_client().table(TABLE).insert(row).execute()
    return result.data[0]


def get_messages(conversation_id: str, after_id: int | None = None) -> list[dict]:
    """All rows of a conversation ordered by id ascending, optionally after an id."""
    query = get_client().table(TABLE).select("*").eq("conversation_id", conversation_id)
    if after_id is not None:
        query = query.gt("id", after_id)
    return query.order("id").execute().data


def list_conversations() -> list[dict]:
    """One summary per conversation, most recent first."""
    rows = _all_rows(TABLE)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["conversation_id"], []).append(row)

    summaries = []
    for conversation_id, group in grouped.items():
        last = group[-1]
        name = next((r["conversation_name"] for r in reversed(group) if r["conversation_name"]), None)
        summaries.append(
            {
                "conversation_id": conversation_id,
                "conversation_name": name,
                "preview": (last["content"] or "")[:120],
                "last_created_at": last["created_at"],
                "last_id": last["id"],
                "message_count": len(group),
                "unread": any(not r["read"] and r["role"] != "human" for r in group),
                "needs_attention": any(r["needs_attention"] for r in group),
            }
        )
    summaries.sort(key=lambda s: s["last_created_at"], reverse=True)
    return summaries


def open_conversation(conversation_id: str) -> list[dict]:
    """Open a thread in ONE round-trip: mark every row read + clear attention and
    return the updated rows (PostgREST returns the representation). Rows come back
    unordered, so sort by id ascending.
    """
    result = (
        get_client()
        .table(TABLE)
        .update({"read": True, "needs_attention": False})
        .eq("conversation_id", conversation_id)
        .execute()
    )
    return sorted(result.data, key=lambda row: row["id"])


def clear_attention(conversation_id: str) -> None:
    """Clear the needs-attention flag across a conversation."""
    get_client().table(TABLE).update({"needs_attention": False}).eq(
        "conversation_id", conversation_id
    ).execute()


def latest_name(rows: list[dict]) -> str | None:
    """Latest non-null conversation_name among already-fetched rows (no query)."""
    return next((r["conversation_name"] for r in reversed(rows) if r["conversation_name"]), None)


def list_faqs() -> list[dict]:
    """All FAQ rows (id, concise, question, answer) ordered by id."""
    return get_client().table(FAQ_TABLE).select("*").order("id").execute().data


def create_faq(concise: str, question: str, answer: str) -> dict:
    """Insert a new FAQ with the next id (max existing id + 1) and return it.

    The id doubles as the public Qn / ?q=N number, so it is assigned explicitly
    rather than relying on a database sequence.
    """
    last = get_client().table(FAQ_TABLE).select("id").order("id", desc=True).limit(1).execute().data
    next_id = (last[0]["id"] + 1) if last else 1
    record = {"id": next_id, "concise": concise, "question": question, "answer": answer}
    return get_client().table(FAQ_TABLE).insert(record).execute().data[0]


def update_faq(faq_id: int, concise: str, question: str, answer: str) -> dict | None:
    """Update a FAQ's text fields by id; return the updated row, or None if absent."""
    result = (
        get_client()
        .table(FAQ_TABLE)
        .update({"concise": concise, "question": question, "answer": answer})
        .eq("id", faq_id)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_faq(faq_id: int) -> None:
    """Delete a FAQ by id."""
    get_client().table(FAQ_TABLE).delete().eq("id", faq_id).execute()


def get_instructions() -> str:
    """The admin's additional system-prompt instructions (singleton row id=1)."""
    rows = get_client().table(SETTINGS_TABLE).select("instructions").eq("id", 1).execute().data
    return rows[0]["instructions"] if rows else ""


def set_instructions(text: str) -> None:
    """Store the additional instructions on the singleton settings row."""
    now = datetime.now(timezone.utc).isoformat()
    get_client().table(SETTINGS_TABLE).upsert(
        {"id": 1, "instructions": text, "updated_at": now}
    ).execute()
