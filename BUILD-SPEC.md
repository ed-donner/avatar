# Avatar — BUILD SPEC (internal build contract)

This is the single source of truth for implementation. It operationalises `SPEC.md` (behaviour),
the `design-system/` (look & feel), and the verified library idioms. **Read `SPEC.md` and
`design-system/SKILL.md` first.** Where this file gives exact signatures/contracts, follow them
verbatim so independently-built modules compose.

Conventions: simple, incremental, no overengineering, no defensive programming, latest APIs, `uv`
for Python, no emojis in code/logs. Short modules/functions, clear names. Docstrings over comments.

---

## 0. Verified library idioms (do NOT deviate)

### OpenAI Agents SDK 0.17.4 + OpenRouter (openai 2.38)
At startup, ONCE:
```python
from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api, set_tracing_disabled
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
set_default_openai_client(client)
set_default_openai_api("chat_completions")   # default "responses" FAILS on OpenRouter
set_tracing_disabled(True)
```
Then `Agent(name="Avatar", instructions=SYSTEM_PROMPT, model=MODEL, tools=[faq_tool, push_tool])`
where `MODEL` is the plain string from env (e.g. `openai/gpt-5.4-nano`).
`@function_tool` derives: tool name = function name, description = docstring summary, arg docs =
`Args:` lines. Stream:
```python
from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent
result = Runner.run_streamed(agent, transcript_str)   # str input, NO Session
async for event in result.stream_events():
    if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
        if event.data.delta:                  # skip empty deltas
            ... yield token ...
    elif event.type == "run_item_stream_event":
        if event.name == "tool_called":
            ... event.item.tool_name ...       # e.g. "faq_tool"
        elif event.name == "tool_output":
            ... event.item.output ...
# result.final_output valid only AFTER the loop completes. Tool events precede text deltas.
```

### FastAPI 0.136 / Starlette 1.2
- SSE is built in: `from fastapi.sse import EventSourceResponse`. Route uses
  `response_class=EventSourceResponse` and the handler returns/`yield`s an async iterable of plain
  dicts; FastAPI encodes each as `data: {json}\n\n` and sets headers + 15s keepalive. Do NOT add
  sse-starlette and do NOT hand-format SSE frames.
- Static serving: `app.mount("/assets", StaticFiles(directory=DIST/"assets"))`, `FileResponse` for
  `GET /` and `GET /admin`; mount `/` (whole dist) LAST for public assets (icons.svg, PNGs).
  Register ALL `/api` and `/admin` routes and the `/`,`/admin` page routes BEFORE the final `/`
  mount so it cannot shadow them.
- Auth: `itsdangerous.URLSafeTimedSerializer`, `secrets.compare_digest`, httpOnly + SameSite=Lax
  cookie, `Depends(require_admin)`. `COOKIE_SECURE` from env: default OFF so admin works on
  http://localhost; set 1 in production (HTTPS).

### Vite 8 / Node 24
- `build.rollupOptions.input = { main: 'index.html', admin: 'admin.html' }`. `public/` copied to
  dist root, referenced by absolute path (`/icons.svg`, `/avatar-robot-round.png`). Import CSS from
  TS. Dev proxy `/api` → `http://localhost:8000`; prod same-origin (no CORS). `npm run build` =
  `tsc && vite build` (type errors fail the build — keep TS clean).

---

## 1. Directory layout

```
backend/
  pyproject.toml            # extend deps (below)
  app/
    __init__.py
    config.py               # env settings (cached)
    knowledge.py            # summary + linkedin pdf + faq.jsonl; prompt list; Qn; faq lookup
    push.py                 # pushover send
    agent.py                # configure_openrouter, tools, build_agent, SYSTEM_PROMPT, stream + transcript
    db.py                   # supabase client + MessageRepo (all DB access)
    models.py               # pydantic request/response/event models
    auth.py                 # login/logout/require_admin (itsdangerous cookie)
    main.py                 # FastAPI app: routes, SSE, static serving, startup
  tests/
    conftest.py
    test_supabase_connection.py   # EXISTS, keep
    test_knowledge.py
    test_auth.py
    test_api_public.py
    test_api_admin.py
    test_chat_stream.py     # calls model (gpt-5.4-nano) — marked "llm"
frontend/
  index.html                # visitor, loads /src/visitor/main.ts
  admin.html                # admin, loads /src/admin/main.ts
  package.json  package-lock.json  tsconfig.json  vite.config.ts
  public/                   # icons.svg, avatar-human.png, avatar-robot.png, avatar-robot-round.png, favicon.svg
  src/
    vite-env.d.ts
    styles/ tokens.css  components.css  visitor.css  admin.css
    lib/ types.ts  api.ts  theme.ts  markdown.ts  dom.ts  time.ts
    visitor/ main.ts
    admin/ main.ts
Dockerfile  .dockerignore
scripts/ start_mac.sh  stop_mac.sh  start_pc.ps1  stop_pc.ps1
test/ backend-test-plan.md  frontend-test-plan.md  e2e-test-plan.md
```

`backend/app/main.py` is at depth `backend/app/` → repo root = `Path(__file__).resolve().parents[2]`.

---

## 2. Backend dependencies (extend backend/pyproject.toml)

Add to `dependencies`: `fastapi>=0.136.3`, `uvicorn[standard]>=0.48.0`, `itsdangerous>=2.2.0`,
`pypdf>=4` (linkedin extraction). Keep existing `openai-agents>=0.17.4`, `pydantic`, `python-dotenv`,
`requests`, `supabase`. Add `openai>=2.38.0` explicitly.
Add to `[dependency-groups] dev`: `httpx` (TestClient needs it; already transitive via supabase —
make explicit). Keep `pytest`. Register a pytest marker `llm` for model-calling tests.
After editing, run `uv sync` from `backend/`.

---

## 3. config.py

`load_dotenv(REPO_ROOT / ".env", override=True)` at import (REPO_ROOT = parents[2]).
Expose a cached `get_settings()` returning a frozen dataclass `Settings` with:
`openrouter_api_key, model, owner_name, admin_password, pushover_user, pushover_token,
supabase_url, supabase_key, session_secret (env SESSION_SECRET or derived "avatar::"+admin_password),
cookie_secure (env COOKIE_SECURE == "1", default False), frontend_dist (env FRONTEND_DIST or
REPO_ROOT/frontend/dist), knowledge_dir (env KNOWLEDGE_DIR or REPO_ROOT/knowledge)`.
No validation theatre; just read env. `owner_name` default "Ed Donner" if unset is fine.

---

## 4. knowledge.py

- Load `knowledge/summary.txt` (text).
- Extract `knowledge/linkedin.pdf` text via pypdf at import/first use (cache in a module global).
- Load `knowledge/faq.jsonl` → `FAQS: list[dict]` (keys: `faq`,`question`,`answer`) and
  `FAQ_BY_NUMBER: dict[int, dict]`.
- `faq_list_text() -> str`: numbered list of questions for the system prompt.
- `find_faq(number: int) -> str`: returns `"### Question {n}\n{question}\n### Answer\n{answer}"` or a
  not-found string (mirror reference next_level.ipynb `find_faq`).
- `INSTANT_RE = re.compile(r"^q(\d{1,2})$", re.IGNORECASE)`.
  `instant_faq_number(message) -> int | None` (trim+match). `get_instant_answer(n) -> str` = the FAQ
  answer text (the `answer` field only, rendered as-is markdown) for direct display.
- Resolve the knowledge dir from `get_settings().knowledge_dir`.

---

## 5. push.py

Mirror `reference/push.py`. `def push(message: str) -> str` POSTs to
`https://api.pushover.net/1/messages.json` with user/token from settings; return status string.
Used by the `push_tool`. Keep it tiny.

---

## 6. agent.py

- `configure_openrouter()` — the startup block in §0; call from main startup.
- Tools (names MUST match the UI tool-status labels):
  - `@function_tool def faq_tool(number: int) -> str:` docstring "Look up the answer to a frequently
    asked question by its number." Args: number. Returns `knowledge.find_faq(number)`.
  - `@function_tool def push_tool(message: str) -> str:` docstring "Send a push notification to the
    human owner (your human twin) so they can follow up." Args: message. Returns `push(message)`.
- `SYSTEM_PROMPT` (build at runtime with owner_name, summary, linkedin, faq list). It MUST cover the
  full multi-way situation (more sophisticated than reference/context.py):
  - You are the **digital twin of {OWNER_NAME}**, chatting with visitors on {OWNER_NAME}'s website.
    You are an AI; say so if asked. Represent {OWNER_NAME} professionally (potential client/employer).
  - **Three-way conversation.** The transcript may contain three speakers: `Visitor` (the guest),
    `Avatar` (you), and `{OWNER_NAME}` (the real human, who can join live from an admin panel). When
    {OWNER_NAME} (the human) has posted, treat their words as authoritative and final — never
    contradict, never impersonate them, never pretend to be the human. Continue the conversation
    naturally; do not repeat what the human said. You only ever speak as the Avatar.
  - Answer questions about {OWNER_NAME}'s career, background, skills, experience, and courses. Use
    the FAQ tool for the listed questions (retrieve the original answer; preserve its markdown
    links). Steer politely back to professional topics if asked something unrelated.
  - **Contact capture:** if the visitor wants to get in touch, ask for their email, then call
    `push_tool` with their email + context, and tell the visitor you have notified {OWNER_NAME}.
  - **Can't answer:** if you do not know, call `push_tool` to record the question for {OWNER_NAME},
    then tell the visitor you do not know and have flagged it. Never invent answers.
  - Style: engaging markdown (bold, links, short lists), NO code blocks, concise.
  - Output ONLY the Avatar's next reply text — do not prefix it with "Avatar:".
  - Include the summary, the LinkedIn text, and the numbered FAQ list (from `faq_list_text()`).
- `render_transcript(rows: list[Message], owner_name) -> str`: render prior messages as lines —
  `Visitor: ...`, `Avatar: ...`, `{owner_name} (the human): ...`. The final line is the newest
  visitor message. End with an instruction line like `\n\nReply as the Avatar:`.
- `async def stream_agent(transcript: str) -> AsyncIterator[StreamEvent-dict]`: builds the agent,
  runs `Runner.run_streamed`, yields dicts per the SSE schema (§9) for tokens and tool calls, and
  finally yields the assembled final text + collected tool_calls so the caller can persist. Concretely
  yield `{"type":"tool","phase":"called","tool":name}`, `{"type":"token","text":delta}`, and a final
  `{"type":"_final","text":final_output,"tool_calls":[...]}` (internal; the route converts this to the
  wire `done` event after persisting). Skip empty deltas.

---

## 7. db.py — Supabase access (the ONLY module that talks to the DB)

`get_client() -> Client` cached (`create_client(settings.supabase_url, settings.supabase_key)`).
Table `messages` (schema in README §Supabase). A `Message` is a row dict; convert to `models.Message`.

Repository functions (module-level, simple):
- `insert_message(conversation_id, role, content, *, conversation_name=None, tool_calls=None,
  needs_attention=False, read=False) -> dict` — returns inserted row.
- `get_messages(conversation_id, after_id: int | None = None) -> list[dict]` — ordered by id asc;
  if after_id, only id > after_id.
- `list_conversations() -> list[dict]` — one entry per conversation_id, each:
  `{conversation_id, conversation_name, preview (last message content, trimmed),
    last_created_at, last_id, message_count, unread (any row with read=false AND role!='human'),
    needs_attention (any row needs_attention=true)}`, sorted by last_created_at desc.
  Implement by fetching all rows ordered and grouping in Python (volume is small) — keep simple.
- `mark_conversation_read(conversation_id)` — set read=true for all rows in the conversation.
- `clear_attention(conversation_id)` — set needs_attention=false for all rows in the conversation.
- `set_attention(message_id)` — set needs_attention=true, read=false on one row.
- `conversation_name_for(conversation_id) -> str | None` — latest non-null conversation_name.

Note supabase-py is sync; calling it from async routes is acceptable here (small/fast). Do not
overengineer with async wrappers.

---

## 8. models.py (pydantic v2)

- `Role = Literal["visitor","avatar","human"]`
- `Message`: `id:int, conversation_id:str, conversation_name:str|None, role:Role, content:str,
  tool_calls:list|None, needs_attention:bool, read:bool, created_at:str`.
- `ChatRequest`: `conversation_id:str, message:str, visitor_name:str|None=None`.
- `LoginRequest`: `password:str`.
- `HumanMessageRequest`: `content:str`.
- `ConversationThread`: `conversation_id:str, conversation_name:str|None, messages:list[Message]`.
- `ConversationSummary`: `conversation_id, conversation_name, preview, last_created_at, last_id,
  message_count, unread:bool, needs_attention:bool`.
- `ConfigResponse`: `owner_name:str`.

---

## 9. API contract (frontend & backend MUST agree)

Base: same origin. All JSON unless noted.

Public:
- `GET /api/config` → `ConfigResponse` `{owner_name}`.
- `GET /api/conversations/{conversation_id}?after={id?}` → `ConversationThread` (all roles, id asc).
  Used for restore-from-cookie and for visitor polling (with `after` = last seen id).
- `POST /api/chat` → **SSE** (`EventSourceResponse`). Body `ChatRequest`. Server sequence:
  1. Insert the visitor row (role=visitor, content=message, conversation_name=visitor_name, read=false).
  2. If `instant_faq_number(message)` is not None → instant path: answer = `get_instant_answer(n)`;
     insert avatar row (content=answer, tool_calls=[{"type":"instant","faq":n}]); emit
     `{"type":"instant","faq":n}` then `{"type":"token","text":answer}` then
     `{"type":"done","message_id":<avatar id>,"needs_attention":false}`.
  3. Else: `transcript = render_transcript(all rows incl. the new visitor msg, owner_name)`; stream
     the agent (§6). Forward `tool` and `token` events. On `_final`: insert avatar row
     (content=final text, tool_calls=collected); if any tool_call name == "push_tool", also
     `set_attention(avatar_row_id)` and needs_attention=true. Emit
     `{"type":"done","message_id":<avatar id>,"needs_attention":<bool>}`.
  On exception, emit `{"type":"error","message":"..."}` then stop.

Wire event types (each a JSON object on one `data:` line):
```
{"type":"tool","phase":"called","tool":"faq_tool"|"push_tool"}
{"type":"token","text":"..."}
{"type":"instant","faq":2}
{"type":"done","message_id":123,"needs_attention":false}
{"type":"error","message":"..."}
```

Admin (cookie via itsdangerous; all but login/logout/me guarded by `Depends(require_admin)`):
- `POST /admin/login` body `LoginRequest` → set cookie; `{"ok":true}`. 401 on wrong password
  (constant-time compare).
- `POST /admin/logout` → clear cookie; `{"ok":true}`.
- `GET /admin/me` → `{"authenticated":true}` if cookie valid, else 401 (frontend uses this to decide
  login gate vs dashboard).
- `GET /admin/conversations` → `list[ConversationSummary]` (recent first).
- `GET /admin/conversations/{id}` → `ConversationThread`; **side effect: mark_conversation_read +
  clear_attention** for that conversation, then return the (post-clear) thread.
- `POST /admin/conversations/{id}/messages` body `HumanMessageRequest` → insert human row
  (role=human, read=true, needs_attention=false); return the created `Message`. Avatar does NOT react.
- `POST /admin/conversations/{id}/resolve` → `clear_attention(id)`; `{"ok":true}`.

Routing order in main.py: include api router, admin router, define `GET /` and `GET /admin`
FileResponse routes, mount `/assets`, then mount `/` (whole dist) LAST.

---

## 10. Frontend — shared lib (precise API so pages compose)

`src/lib/types.ts` — mirror §8/§9: `Role`, `Message`, `ConversationThread`, `ConversationSummary`,
`ChatEvent` (union of the wire events), `Config`.

`src/lib/api.ts` — relative `/api` and `/admin` URLs (same-origin):
- `getConfig(): Promise<Config>`
- `getConversation(id: string, after?: number): Promise<ConversationThread>`
- `streamChat(body: {conversation_id; message; visitor_name?}, handlers: {onTool, onToken,
  onInstant, onDone, onError}): Promise<void>` — uses `fetch('/api/chat', {method:'POST', headers
  {'Content-Type':'application/json'}, body: JSON.stringify(body)})`, reads `res.body` via
  `getReader()` + `TextDecoder`, buffers and splits on `\n\n`, strips leading `data:` per line, JSON
  parses, dispatches by `type`. (EventSource is GET-only; we POST, so parse the stream manually.)
- Admin: `login(password)`, `logout()`, `me(): Promise<boolean>`, `listConversations()`,
  `getConversationAdmin(id)`, `postHumanMessage(id, content)`, `resolveConversation(id)`. All use
  `credentials:'same-origin'` (cookie). `login` returns ok/throws on 401.

`src/lib/theme.ts` — `initTheme()` (read `localStorage['avatar-theme']`, default 'dark', set
`data-theme` on `<html>`), `toggleTheme()`, `wireThemeToggle(btn)` syncing the moon/sun icons exactly
like the mockups.

`src/lib/markdown.ts` — `renderMarkdown(md: string): string` returning SAFE HTML. Escape ALL HTML
first, then convert a whitelist: `**bold**`→`<strong>`, `*italic*`/`_italic_`→`<em>`,
`` `code` ``→`<code>`, `[t](url)`→`<a href target=_blank rel=noopener>`, `### h`→`<h3>` etc.,
ordered/unordered lists, and paragraphs/line breaks. No raw HTML passthrough (prevents XSS from
model/visitor text). Visitor message text is rendered as ESCAPED PLAIN TEXT (no markdown).

`src/lib/dom.ts` — `el(tag, attrs?, children?)` helper, `escapeHtml(s)`, `icon(name, cls?)` →
`<svg class><use href="/icons.svg#i-NAME"/></svg>` string/element.

`src/lib/time.ts` — `formatTime(iso)` → "2:41 PM"; `formatShort(iso)` for inbox (time today, else
"Yest"/weekday/date).

Cookie helpers for conversation_id live in visitor/main.ts (not shared).

---

## 11. Frontend — Visitor page (`index.html` + `src/visitor/main.ts` + `styles/visitor.css`)

Build target = `design-system/mockups/Visitor Chat.html`. Lift its markup and top-bar/chat/composer
CSS into `index.html` + `visitor.css` (the component classes come from components.css; page-specific
layout CSS — `.topbar/.chat/.convo/.composer-dock/.intro/.day-sep/.typing` etc. — goes in
visitor.css, copied from the mockup `<style>`). Replace inline icon sprite by referencing
`/icons.svg` via `<use href="/icons.svg#i-...">` (public asset). Avatar images: use
`/avatar-robot-round.png` (twin) and `/avatar-human.png` (human) by absolute path.

Behaviour (per SPEC + ux-flows):
- On load: `initTheme()`; `getConfig()` → set brand subtitle `"{owner_name} · digital twin"`, page
  `<title>`, intro copy, and the human-bubble name. **Composer autofocuses on load.**
- conversation_id: cookie `avatar_cid` (+ `avatar_keep`). If Keep-chat on (default) and cookie has a
  cid → use it and `getConversation(cid)` to restore + render the thread, scroll to latest. Else mint
  `crypto.randomUUID()`. Persist cid to cookie when Keep-chat is on (1y expiry); when toggled off,
  delete the cookie. **Reset**: clear the visible thread, mint a new cid (persist if keep on).
- Name field: free text (first name/initials); used as `visitor_name` on send and to render the
  visitor's `.avatar-initials` token (derive initials from the name; fallback "?" / "You").
- Send (Enter, or click; Shift+Enter = newline): render optimistic `.msg--visitor` bubble (escaped
  text), clear textarea, **re-focus composer**. Call `streamChat`:
  - create an `.msg--avatar` row; on `onTool` add/curate a `.tool-status` line (e.g.
    `faq_tool`→"Looked up the FAQ · faq_tool", `push_tool`→"Notified {owner} · push_tool"); show a
    `.is-done` check when subsequent events arrive. On `onToken` append to the bubble, re-rendering
    markdown from the accumulated text. On `onInstant` add the `.instant-tag` ("instant · Q{n}").
    On `onDone` finalize, re-focus composer, update lastSeenId. On `onError` show a small error line.
  - Show the `.typing` indicator while awaiting first token; remove on first token/done.
- Polling (for async human messages): every 10s call `getConversation(cid, lastSeenId)`; append any
  new rows not already shown (esp. `human` → `.msg--human` bubble). After 5 min with no new activity,
  ease interval to 60s; reset to 10s whenever the visitor sends. Do not double-render messages we
  already have (track lastSeenId / a Set of ids). Don't poll-clobber an in-flight stream.
- **Human bubble** (`.msg--human`): photo + yellow ring + spark badge, tinted+glowing bubble; tag =
  `<icon i-live> {owner_name} · live` (owner_name from /api/config — NEVER hardcoded). See
  BUILD note: this overrides the design-system "name-free" guidance per SPEC Q&A #4.
- Suggestion chips fill the composer (and optionally send). Keep the intro until the first message.

## 12. Frontend — Admin page (`admin.html` + `src/admin/main.ts` + `styles/admin.css`)

Build target = `design-system/mockups/Admin Dashboard.html`, plus a login gate. Lift the appbar /
workspace / sidebar / thread / admin-composer layout CSS into admin.css.

Behaviour:
- On load: `initTheme()`; `me()` → if false render the **login gate** (centred `.card` with password
  `.input`, `.btn--primary` submit, `i-lock`/`i-shield` note; on submit `login(pw)`; on 401 show
  inline error; on success render dashboard). If true render dashboard.
- Dashboard:
  - Appbar: brand + "Admin" pill, secure-session note, theme toggle, owner chip (avatar-human).
  - Sidebar inbox: `listConversations()` → rows `.convo-item` with `.is-unread` (blue dot),
    `.is-attention` (yellow glow + "Needs you" badge), `.is-active`. Most-recent first. Name =
    conversation_name or initials/"Anonymous"; preview = last message; time = `formatShort`.
    A simple "All / Needs you / Unread" filter row is nice-to-have; All is required.
  - Selecting a row: `getConversationAdmin(id)` (clears unread + needs_attention server-side), render
    the full thread in the main panel (visitor/avatar/human bubbles; avatar tool-status from stored
    tool_calls; human bubble tag "You · sent to visitor"), thread header (initials, name,
    `conv_xxxx` short id in mono, started time, count, "Avatar asked for you" flag when attention +
    "Mark resolved"). Update the row to read state.
  - Admin composer: "posting as you" note (visitor sees photo, no name; Avatar won't reply). Enter
    sends `postHumanMessage(id, content)`, Shift+Enter newline; on send append the human bubble and
    clear+refocus. **↑/↓ move selection between conversations** (load on change). Mark resolved →
    `resolveConversation(id)` + clear the row's attention state.
  - Poll `listConversations()` every ~10s to surface new visitor messages / attention; if the open
    thread has new messages, refresh it (without re-clearing if already open is fine — opening already
    cleared). Keep it simple.
- Theme toggle persisted (shared with visitor via localStorage key `avatar-theme`).

Design guardrails (both pages): dark default & persisted; all colour/spacing/type from tokens; no
gradients in chrome, no purple except primary actions/send, no left-edge accent bars (the active
inbox row's selection bar is allowed per SKILL note), no emoji; icons only from icons.svg.

---

## 13. Vite config / html / tsconfig / package.json

Use the verified patterns: `vite.config.ts` with multi-page input + `server.proxy['/api'] ->
http://localhost:8000` (also proxy nothing else; admin.html is served at /admin.html in dev).
`index.html` (`data-theme="dark"`, Google fonts Newsreader+Hanken Grotesk+JetBrains Mono per mockup,
`<script type="module" src="/src/visitor/main.ts">`) and `admin.html`
(`/src/admin/main.ts`). `package.json` (vite ^8, typescript ~6, scripts dev/build/preview).
`tsconfig.json` (official vanilla-ts). `src/vite-env.d.ts` = `/// <reference types="vite/client" />`.
Copy design-system files in: `tokens.css`,`components.css` → `src/styles/`; `icons.svg`,
`assets/avatar-human.png`,`assets/avatar-robot.png`,`assets/avatar-robot-round.png` → `public/`.
Import order in each entry TS: `tokens.css` → `components.css` → page css. Commit a
`package-lock.json` (run `npm install` to generate) so Docker `npm ci` works.

---

## 14. Dockerfile + .dockerignore (project root)

Multi-stage per verified pattern: stage `node:24-slim` builds `frontend/` (`npm ci && npm run
build`); stage `python:3.12-slim` copies uv from `ghcr.io/astral-sh/uv:latest`, `uv sync --project
backend --frozen --no-dev`, copies `backend/`, copies built `frontend/dist` to `/app/frontend/dist`,
copies `knowledge/`, sets `FRONTEND_DIST=/app/frontend/dist KNOWLEDGE_DIR=/app/knowledge PORT=8000`,
`COOKIE_SECURE` left unset (defaults off → works on http), CMD
`uv run --project backend uvicorn app.main:app --host 0.0.0.0 --port 8000`. NOTE the app module is
`app.main:app` run with workdir `backend` (or `--app-dir backend`). Verify the module path matches
the layout (`backend/app/main.py`). `.env` never copied; run with `--env-file .env`. `.dockerignore`
excludes `.env*`, `**/node_modules`, `frontend/dist`, `**/.venv`, caches, `.git`, design-system
mockups/docs, `reference/`, `test/`.

## 15. scripts/ (idempotent; stop-then-rebuild-then-run)

`IMAGE=avatar`, `NAME=avatar`, port 8000, env-file = repo-root `.env`.
- `start_mac.sh` (bash): stop+rm container if running, `docker build -t avatar .`, `docker run -d
  --name avatar --env-file .env -p 8000:8000 avatar`, print URL `http://localhost:8000`.
- `stop_mac.sh`: stop + rm container.
- `start_pc.ps1` / `stop_pc.ps1`: PowerShell equivalents.
Make .sh executable (chmod +x). Scripts resolve repo root relative to script location.
The scripts agent ALSO updates README.md with a short "Running the app" section (Docker + local dev:
backend `uv run uvicorn app.main:app --reload --app-dir backend`, frontend `npm run dev`). README is
owned solely by the scripts agent to avoid write conflicts.

---

## 16. Tests (backend) — backend/tests

`conftest.py`: load .env; set `COOKIE_SECURE` off; `TestClient(app)` fixture; helpers to create &
clean up conversations (delete rows by conversation_id after each test). Use random UUID cids.
- `test_knowledge.py`: faq loads, find_faq known/unknown, Qn regex (Q2/q12/ not "question"),
  get_instant_answer, faq_list_text non-empty.
- `test_auth.py`: no cookie → 401 on guarded routes; wrong password → 401; correct → cookie + access;
  tampered cookie → 401; logout → 401. (COOKIE_SECURE off so TestClient resends over http.)
- `test_api_public.py`: /api/config returns owner_name; create messages via a helper, GET
  conversation returns them; `after` filter works.
- `test_api_admin.py`: list/get/post-human/resolve; opening clears unread+attention; human message
  inserted with role=human; resolve clears attention; all guarded.
- `test_chat_stream.py` (marker `llm`): POST /api/chat with a simple message, assert SSE yields token
  events and a done event and that an avatar row is persisted; a `Q2` returns an instant event +
  answer with no model call; (optionally) a "please contact Ed, email x@y.com" triggers push_tool →
  needs_attention true. Keep model calls minimal. Clean up rows.
Run: `uv run pytest -q` (and `-m "not llm"` for the no-cost subset).

## 17. Test plans (test/) — markdown with checkboxes

`backend-test-plan.md`, `frontend-test-plan.md`, `e2e-test-plan.md` enumerating every case from
ux-flows States matrix + SKILL acceptance checklist + SPEC success criteria, as `- [ ]` items, to be
checked off during the testing phase.

---

## 18. Owner-name rule (applies everywhere)

`OWNER_NAME` is read from config and surfaced in: page titles, brand subtitle, how the Avatar refers
to itself (system prompt), and the visitor-facing human bubble ("{owner} · live"). NEVER hardcode
"Ed Donner" in code — always from `/api/config` (frontend) or settings (backend). This is the one
place SPEC (Q&A #4, show the name) overrides the design-system "name-free" wording.
