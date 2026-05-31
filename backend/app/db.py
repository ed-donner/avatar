"""Supabase access layer: the only module that talks to the database."""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings

TABLE = "messages"


@lru_cache
def get_client() -> Client:
    """Cached Supabase client."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


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
    rows = get_client().table(TABLE).select("*").order("id").execute().data
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


def mark_conversation_read(conversation_id: str) -> None:
    """Mark every row in a conversation as read."""
    get_client().table(TABLE).update({"read": True}).eq("conversation_id", conversation_id).execute()


def clear_attention(conversation_id: str) -> None:
    """Clear the needs-attention flag across a conversation."""
    get_client().table(TABLE).update({"needs_attention": False}).eq(
        "conversation_id", conversation_id
    ).execute()


def set_attention(message_id: int) -> None:
    """Flag one row as needing attention and unread."""
    get_client().table(TABLE).update({"needs_attention": True, "read": False}).eq(
        "id", message_id
    ).execute()


def conversation_name_for(conversation_id: str) -> str | None:
    """Latest non-null conversation_name for a conversation."""
    rows = get_messages(conversation_id)
    return next((r["conversation_name"] for r in reversed(rows) if r["conversation_name"]), None)
