"""Pydantic request/response models for the API contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Role = Literal["visitor", "avatar", "human"]

# A required, non-blank text field (trimmed; rejects empty/whitespace-only with 422).
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


class InstructionsBody(BaseModel):
    """The admin's additional system-prompt instructions (Markdown)."""

    instructions: str


class FaqInput(BaseModel):
    """FAQ fields the admin edits; the id is assigned by the server.

    All three are required and non-blank so a stray/empty row can't pollute the
    prompt routing list or consume a Qn number.
    """

    concise: NonBlank
    question: NonBlank
    answer: NonBlank


class FaqItem(FaqInput):
    """A stored FAQ row (id doubles as the public Qn / ?q=N number)."""

    id: int
