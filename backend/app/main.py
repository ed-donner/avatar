"""FastAPI app: public + admin APIs, SSE chat, and static frontend serving."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app import agent, db, knowledge
from app.auth import (
    clear_session_cookie,
    is_authenticated,
    require_admin,
    set_session_cookie,
    verify_password,
)
from app.config import get_settings
from app.models import (
    ChatRequest,
    ConfigResponse,
    ConversationSummary,
    ConversationThread,
    FaqInput,
    FaqItem,
    HumanMessageRequest,
    InstructionsBody,
    LoginRequest,
    Message,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire up OpenRouter once at startup."""
    agent.configure_openrouter()
    yield


app = FastAPI(title="Avatar", lifespan=lifespan)

api = APIRouter(prefix="/api")
admin = APIRouter(prefix="/admin")


# ---- Abuse guards (cheap protection for the API key) ----

MAX_MESSAGE_CHARS = 20_000
TRUNCATION_NOTE = (
    "[...message truncated as it's too long; ask the visitor to send something more concise]"
)

# At most 20 messages/minute per conversation_id. In-memory (per process) is enough:
# OpenRouter caps overall spend, and a browser's requests stick to one machine.
_rate_limiter = MovingWindowRateLimiter(MemoryStorage())
_chat_rate = parse("20/minute")


def clamp_message(text: str) -> str:
    """Cap over-long visitor input so a single paste can't run up LLM token spend."""
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return text[:MAX_MESSAGE_CHARS] + " " + TRUNCATION_NOTE


async def enforce_chat_rate_limit(request: Request) -> None:
    """Reject more than 20 chat messages per minute from one conversation_id."""
    body = await request.json()
    if not _rate_limiter.hit(_chat_rate, str(body.get("conversation_id", ""))):
        raise HTTPException(status_code=429, detail="Too many messages; please slow down.")


# ---- Public API ----


@api.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Owner name and other public config."""
    return ConfigResponse(owner_name=get_settings().owner_name)


@api.get("/conversations/{conversation_id}", response_model=ConversationThread)
def get_conversation(conversation_id: str, after: int | None = None) -> ConversationThread:
    """Full thread (all roles) for restore-from-cookie and visitor polling."""
    rows = db.get_messages(conversation_id, after_id=after)
    return ConversationThread(
        conversation_id=conversation_id,
        conversation_name=db.latest_name(rows),
        messages=[Message(**row) for row in rows],
    )


async def _chat_events(request: ChatRequest) -> AsyncIterator[dict]:
    """Drive a chat turn and yield wire events for the SSE stream."""
    settings = get_settings()
    message = clamp_message(request.message)
    db.insert_message(
        request.conversation_id,
        "visitor",
        message,
        conversation_name=request.visitor_name,
        read=False,
    )

    instant = knowledge.instant_faq_number(message)
    if instant is not None:
        answer = knowledge.get_instant_answer(instant)
        row = db.insert_message(
            request.conversation_id,
            "avatar",
            answer,
            tool_calls=[{"type": "instant", "faq": instant}],
        )
        yield {"type": "instant", "faq": instant}
        yield {"type": "token", "text": answer}
        yield {"type": "done", "message_id": row["id"], "needs_attention": False}
        return

    rows = [Message(**r) for r in db.get_messages(request.conversation_id)]
    transcript = agent.render_transcript(rows, settings.owner_name)
    async for event in agent.stream_agent(transcript):
        if event["type"] == "_final":
            tool_names = [tc["tool"] for tc in event["tool_calls"]]
            needs_attention = "push_tool" in tool_names
            row = db.insert_message(
                request.conversation_id,
                "avatar",
                event["text"],
                tool_calls=event["tool_calls"] or None,
                needs_attention=needs_attention,
                read=not needs_attention,
            )
            yield {"type": "done", "message_id": row["id"], "needs_attention": needs_attention}
        else:
            yield event


@api.post("/chat", response_class=EventSourceResponse, dependencies=[Depends(enforce_chat_rate_limit)])
async def chat(request: ChatRequest) -> AsyncIterator[dict]:
    """Stream the Avatar's reply as Server-Sent Events."""
    try:
        async for event in _chat_events(request):
            yield event
    except Exception as exc:  # noqa: BLE001 - surface failures to the client
        yield {"type": "error", "message": str(exc)}


# ---- Admin API ----


@admin.post("/login")
def login(request: LoginRequest, response: Response) -> dict:
    """Validate the admin password and set a session cookie."""
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    set_session_cookie(response)
    return {"ok": True}


@admin.post("/logout")
def logout(response: Response) -> dict:
    """Clear the admin session cookie."""
    clear_session_cookie(response)
    return {"ok": True}


@admin.get("/me")
def me(avatar_admin: str | None = Cookie(default=None)) -> dict:
    """Login-gate probe: 200 when authenticated, else 401."""
    if not is_authenticated(avatar_admin):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"authenticated": True}


@admin.get("/conversations", response_model=list[ConversationSummary], dependencies=[Depends(require_admin)])
def admin_list_conversations() -> list[ConversationSummary]:
    """Inbox summaries, most recent first."""
    return [ConversationSummary(**s) for s in db.list_conversations()]


@admin.get(
    "/conversations/{conversation_id}",
    response_model=ConversationThread,
    dependencies=[Depends(require_admin)],
)
def admin_get_conversation(conversation_id: str) -> ConversationThread:
    """Open a thread in one round-trip: mark read + clear attention and return the rows."""
    rows = db.open_conversation(conversation_id)
    return ConversationThread(
        conversation_id=conversation_id,
        conversation_name=db.latest_name(rows),
        messages=[Message(**row) for row in rows],
    )


@admin.post(
    "/conversations/{conversation_id}/messages",
    response_model=Message,
    dependencies=[Depends(require_admin)],
)
def admin_post_message(conversation_id: str, request: HumanMessageRequest) -> Message:
    """Insert a human message (the Avatar does not react to it)."""
    row = db.insert_message(
        conversation_id,
        "human",
        request.content,
        read=True,
        needs_attention=False,
    )
    return Message(**row)


@admin.post("/conversations/{conversation_id}/resolve", dependencies=[Depends(require_admin)])
def admin_resolve(conversation_id: str) -> dict:
    """Clear the needs-attention flag for a conversation."""
    db.clear_attention(conversation_id)
    return {"ok": True}


@admin.get("/instructions", response_model=InstructionsBody, dependencies=[Depends(require_admin)])
def admin_get_instructions() -> InstructionsBody:
    """The current additional system-prompt instructions."""
    return InstructionsBody(instructions=db.get_instructions())


@admin.put("/instructions", response_model=InstructionsBody, dependencies=[Depends(require_admin)])
def admin_set_instructions(body: InstructionsBody) -> InstructionsBody:
    """Save the additional system-prompt instructions (appended after the style section)."""
    db.set_instructions(body.instructions)
    return InstructionsBody(instructions=body.instructions)


@admin.get("/faq", response_model=list[FaqItem], dependencies=[Depends(require_admin)])
def admin_list_faqs() -> list[FaqItem]:
    """All FAQ rows, ordered by id."""
    return [FaqItem(**row) for row in db.list_faqs()]


@admin.post("/faq", response_model=FaqItem, dependencies=[Depends(require_admin)])
def admin_create_faq(body: FaqInput) -> FaqItem:
    """Add a FAQ (id assigned as max+1) and refresh the prompt cache."""
    row = db.create_faq(body.concise, body.question, body.answer)
    knowledge.reload_faqs()
    return FaqItem(**row)


@admin.put("/faq/{faq_id}", response_model=FaqItem, dependencies=[Depends(require_admin)])
def admin_update_faq(faq_id: int, body: FaqInput) -> FaqItem:
    """Update a FAQ by id and refresh the prompt cache."""
    row = db.update_faq(faq_id, body.concise, body.question, body.answer)
    if row is None:
        raise HTTPException(status_code=404, detail="FAQ not found")
    knowledge.reload_faqs()
    return FaqItem(**row)


@admin.delete("/faq/{faq_id}", dependencies=[Depends(require_admin)])
def admin_delete_faq(faq_id: int) -> dict:
    """Delete a FAQ by id and refresh the prompt cache."""
    db.delete_faq(faq_id)
    knowledge.reload_faqs()
    return {"ok": True}


app.include_router(api)
app.include_router(admin)


# ---- Static frontend ----

settings = get_settings()
DIST = settings.frontend_dist


@app.get("/")
def index() -> FileResponse:
    """Serve the visitor page."""
    target = DIST / "index.html"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    return FileResponse(target)


@app.get("/admin")
def admin_page() -> FileResponse:
    """Serve the admin page."""
    target = DIST / "admin.html"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    return FileResponse(target)


if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST), name="static")
