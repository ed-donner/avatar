"""Pydantic request/response models for the API contract."""

from typing import Literal

from pydantic import BaseModel

Role = Literal["visitor", "avatar", "human"]


class Message(BaseModel):
    """A single stored conversation row."""

    id: int
    conversation_id: str
    conversation_name: str | None = None
    role: Role
    content: str
    tool_calls: list | None = None
    needs_attention: bool = False
    read: bool = False
    created_at: str


class ChatRequest(BaseModel):
    """Visitor chat submission."""

    conversation_id: str
    message: str
    visitor_name: str | None = None


class LoginRequest(BaseModel):
    """Admin login payload."""

    password: str


class HumanMessageRequest(BaseModel):
    """A message posted by the human owner from the admin panel."""

    content: str


class ConversationThread(BaseModel):
    """A full conversation with all of its messages."""

    conversation_id: str
    conversation_name: str | None = None
    messages: list[Message]


class ConversationSummary(BaseModel):
    """Inbox row summarising one conversation."""

    conversation_id: str
    conversation_name: str | None = None
    preview: str
    last_created_at: str
    last_id: int
    message_count: int
    unread: bool
    needs_attention: bool


class ConfigResponse(BaseModel):
    """Public configuration surfaced to the frontend."""

    owner_name: str
