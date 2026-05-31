"""FastAPI app: public + admin APIs, SSE chat, and static frontend serving."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse
from fastapi.staticfiles import StaticFiles

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
    HumanMessageRequest,
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
    db.insert_message(
        request.conversation_id,
        "visitor",
        request.message,
        conversation_name=request.visitor_name,
        read=False,
    )

    instant = knowledge.instant_faq_number(request.message)
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


@api.post("/chat", response_class=EventSourceResponse)
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
