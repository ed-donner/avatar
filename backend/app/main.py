"""FastAPI app: public + admin APIs, SSE chat, and static frontend serving."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app import agent, db, knowledge, push
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


@app.exception_handler(Exception)
async def _on_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Alert the owner about any otherwise-unhandled backend error, and return a generic 500
    (without leaking the exception detail to the caller)."""
    push.notify_error(f"Unhandled error on {request.method} {request.url.path}: {exc!r}", category="server")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---- Abuse guards (cheap protection for the API key) ----

MAX_MESSAGE_CHARS = 20_000
TRUNCATION_NOTE = (
    "[...message truncated as it's too long; ask the visitor to send something more concise]"
)

# At most 20 messages/minute per conversation_id. In-memory (per process) is enough:
# OpenRouter caps overall spend, and a browser's requests stick to one machine.
_rate_storage = MemoryStorage()  # exposed so tests can reset between cases
_rate_limiter = MovingWindowRateLimiter(_rate_storage)
_chat_rate = parse("20/minute")
# Failed admin logins, per client IP. A speed bump against naive brute force (a strong
# ADMIN_PASSWORD is the real control); per-IP so an attacker only locks their own IP.
_login_rate = parse("5/minute")


def _client_ip(request: Request) -> str:
    """Best-effort client IP. Fly sets Fly-Client-IP; fall back to XFF, then the socket peer."""
    return (
        request.headers.get("fly-client-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


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
        push.notify_error(f"Chat turn failed: {exc}", category="chat")
        yield {"type": "error", "message": str(exc)}


# ---- Admin API ----


@admin.post("/login")
def login(credentials: LoginRequest, request: Request, response: Response) -> dict:
    """Validate the admin password and set a session cookie.

    Failed attempts are rate-limited per client IP to blunt online brute force;
    a successful login is never throttled.
    """
    ip = _client_ip(request)
    if not _rate_limiter.test(_login_rate, "login", ip):
        push.notify_error(f"Admin login throttled after repeated failed attempts from {ip}.", category="login")
        raise HTTPException(status_code=429, detail="Too many login attempts; please wait a minute.")
    if not verify_password(credentials.password):
        _rate_limiter.hit(_login_rate, "login", ip)  # only failures count toward the limit
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


# ---- Archive ----


@admin.post("/conversations/{conversation_id}/archive", dependencies=[Depends(require_admin)])
def admin_archive_conversation(conversation_id: str) -> dict:
    """Move a whole conversation from the inbox into the archive."""
    return {"ok": True, "messages": db.archive_conversation(conversation_id)}


@admin.post("/archive-inactive", dependencies=[Depends(require_admin)])
def admin_archive_inactive() -> dict:
    """Archive every conversation with no activity in the last 72 hours."""
    return db.archive_inactive()


@admin.get("/archive", response_model=list[ConversationSummary], dependencies=[Depends(require_admin)])
def admin_list_archive() -> list[ConversationSummary]:
    """Archived conversation summaries, most recent first."""
    return [ConversationSummary(**s) for s in db.list_archived_conversations()]


@admin.get(
    "/archive/{conversation_id}",
    response_model=ConversationThread,
    dependencies=[Depends(require_admin)],
)
def admin_get_archived(conversation_id: str) -> ConversationThread:
    """Read-only view of an archived conversation (does not change any state)."""
    rows = db.get_archived_messages(conversation_id)
    return ConversationThread(
        conversation_id=conversation_id,
        conversation_name=db.latest_name(rows),
        messages=[Message(**row) for row in rows],
    )


@admin.post("/archive/{conversation_id}/restore", dependencies=[Depends(require_admin)])
def admin_restore_conversation(conversation_id: str) -> dict:
    """Move a whole conversation from the archive back into the inbox."""
    return {"ok": True, "messages": db.restore_conversation(conversation_id)}


# ---- Export (one JSON object per message row) ----


def _jsonl_response(rows: list[dict], prefix: str) -> Response:
    """A downloadable jsonl file: one JSON object per row, timestamped filename."""
    body = "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        content=body,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{prefix}-{stamp}.jsonl"'},
    )


@admin.get("/export/conversations", dependencies=[Depends(require_admin)])
def admin_export_conversations() -> Response:
    """Download every live message row as jsonl."""
    return _jsonl_response(db.all_message_rows(), "conversations")


@admin.get("/export/archive", dependencies=[Depends(require_admin)])
def admin_export_archive() -> Response:
    """Download every archived message row as jsonl."""
    return _jsonl_response(db.all_archive_rows(), "archive")


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
