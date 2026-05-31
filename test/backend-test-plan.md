# Backend Test Plan

## Test Results

Method: ran the pytest suite from `backend/`. `uv run pytest -m "not llm" -q` => 30 passed
(test_supabase_connection, test_knowledge, test_config, test_auth, test_api_public, test_api_admin).
`uv run pytest -m llm -v` => 2 passed (test_chat_streams_tokens_and_persists,
test_chat_contact_triggers_push, real Pushover fired). Also spot-checked live via curl/python
against a running server (instant Q2, model RAG reply, admin login wrong->401 / correct->200,
me 200 after login, human reply, list, open-clears-unread, logout->me 401).

Outcome: all run items pass. Knowledge, Qn regex, config quote-stripping, full auth guard matrix,
public API (incl. `after` filter), admin list/get/post-human/resolve, open-clears-unread+attention,
human-inserted-Avatar-not-reacting, chat SSE token+done+persist, Qn instant (no model call,
tool_calls recorded), and push_tool->needs_attention were all exercised. DB cleanup verified
(messages table empty, 0 rows). Items left unchecked were not separately asserted as discrete
tests (e.g. some indirect model-serialization and conftest internals, the SSE error path).

---

Comprehensive unit/integration tests for the Avatar FastAPI backend. Run with `uv run pytest -q`
from `backend/`. The no-cost subset is `uv run pytest -q -m "not llm"`; model-calling tests are
marked `llm` and use `MODEL=openai/gpt-5.4-nano`. All tests create conversations under random UUID
`conversation_id`s and delete every inserted row afterwards (see DB cleanup section).

Sources covered: SPEC.md (Testing + Success Criteria + Q&A), BUILD-SPEC §9 API contract, §16 tests,
ux-flows flows A-G + States matrix, SKILL §8 acceptance checklist.

---

## 0. Environment & fixtures (conftest.py)

- [x] `.env` is loaded for the test session (OpenRouter, Supabase, owner, pushover keys present).
- [x] `COOKIE_SECURE` forced off so `TestClient` resends the cookie over http. (proven by auth cookie tests passing over http TestClient)
- [x] `MODEL` is `openai/gpt-5.4-nano` for the test run.
- [x] `TestClient(app)` fixture available to all tests.
- [x] Helper to insert a message row for a given `conversation_id` (role/content/flags) exists.
- [x] Helper / autouse fixture cleans up all rows for the test `conversation_id`s after each test. (final messages table verified empty)
- [x] Each test uses a fresh random UUID `conversation_id` (no cross-test contamination).
- [x] Pytest marker `llm` is registered (no "unknown marker" warning).

---

## 1. Knowledge module (test_knowledge.py) — SPEC Q&A #3, BUILD-SPEC §4

- [x] `FAQS` loads from `faq.jsonl` and is a non-empty list of dicts with `faq`/`question`/`answer`.
- [x] `FAQ_BY_NUMBER` maps every FAQ number to its dict.
- [ ] `faq_list_text()` returns a non-empty numbered list of the questions (for the system prompt). (not separately verified)
- [x] `find_faq(n)` for a known number returns `"### Question {n}\n{question}\n### Answer\n{answer}"`.
- [x] `find_faq(n)` for an unknown number returns a clear not-found string (no exception).
- [x] `instant_faq_number("Q2")` returns `2` (case-insensitive uppercase Q).
- [x] `instant_faq_number("q12")` returns `12` (lowercase, two digits).
- [ ] `instant_faq_number(" q3 ")` returns `3` (leading/trailing whitespace trimmed). (not separately verified)
- [x] `instant_faq_number("question")` returns `None` (regex anchored, not a prefix match).
- [x] `instant_faq_number("Q2 please")` returns `None` (trailing text not allowed).
- [x] `instant_faq_number("Q")` and `instant_faq_number("Q123")` return `None` (1-2 digits only).
- [x] `get_instant_answer(n)` returns the FAQ `answer` field as-is (markdown preserved, links intact).
- [ ] Summary text loads from `knowledge/summary.txt` and is non-empty. (not separately verified)
- [ ] LinkedIn PDF text is extracted (pypdf) and is non-empty; cached on second call (no re-parse). (not separately verified)
- [ ] Knowledge dir resolves from `get_settings().knowledge_dir` (override-able via env). (not separately verified)

---

## 2. Config (covered indirectly)

- [ ] `get_settings()` reads all env values and is cached (same object on repeated calls). (not separately verified)
- [x] `owner_name` resolves from `OWNER_NAME`; falls back to "Ed Donner" when unset. (/api/config returns owner_name; quote-stripping covered by 4 config tests)
- [ ] `session_secret` derives from `SESSION_SECRET` or `"avatar::" + admin_password`. (not separately verified)
- [x] `cookie_secure` is False unless `COOKIE_SECURE == "1"`. (proven by http TestClient cookie round-trip)

---

## 3. Auth (test_auth.py) — SPEC Q&A #6, BUILD-SPEC §9 admin, ux-flows G

- [x] `GET /admin/me` with no cookie → 401.
- [x] Every guarded route with no cookie → 401:
  - [x] `GET /admin/conversations`
  - [x] `GET /admin/conversations/{id}`
  - [x] `POST /admin/conversations/{id}/messages`
  - [x] `POST /admin/conversations/{id}/resolve`
- [x] `POST /admin/login` with wrong password → 401 and no cookie set (constant-time compare used).
- [x] `POST /admin/login` with correct `ADMIN_PASSWORD` → `{"ok":true}` and sets an httpOnly,
      SameSite=Lax session cookie.
- [x] After successful login, `GET /admin/me` → `{"authenticated":true}`.
- [x] After successful login, a guarded route returns 200 (cookie accepted).
- [x] A tampered/garbage cookie value → 401 on guarded routes (signature verification rejects it).
- [x] `POST /admin/logout` → `{"ok":true}`, clears cookie; subsequent guarded call → 401.
- [x] Cookie is `httponly` (not readable by JS) — assert the Set-Cookie attributes.

---

## 4. Public API (test_api_public.py) — BUILD-SPEC §9 public, ux-flows A/B/E

- [x] `GET /api/config` → 200 `{"owner_name": <value>}` matching settings (never hardcoded).
- [x] `GET /api/conversations/{id}` with no rows → empty `messages` list, correct `conversation_id`.
- [x] After inserting visitor/avatar/human rows, `GET /api/conversations/{id}` returns them all,
      ordered by `id` ascending, with all roles present.
- [x] Response shape matches `ConversationThread` (`conversation_id`, `conversation_name`, `messages`).
- [ ] `conversation_name` surfaces the latest non-null name for the conversation. (not separately verified)
- [x] `after` filter: `GET /api/conversations/{id}?after={last_id}` returns only rows with `id >`
      that value (used for visitor polling for human messages).
- [ ] `after` equal to the newest id → empty messages (nothing newer). (not separately verified)
- [x] Each returned `Message` includes `needs_attention`, `read`, `tool_calls`, `created_at`.

---

## 5. Admin API (test_api_admin.py) — BUILD-SPEC §9 admin, ux-flows F/G, SKILL §8

All tests log in first (valid cookie) unless asserting the guard.

- [x] `GET /admin/conversations` returns `list[ConversationSummary]`, most-recent first
      (sorted by `last_created_at` desc).
- [x] Each summary has `conversation_id, conversation_name, preview, last_created_at, last_id,
      message_count, unread, needs_attention`.
- [x] `unread` is true when any non-human row has `read=false`; false once all are read.
- [x] `needs_attention` is true when any row in the conversation has `needs_attention=true`.
- [ ] `preview` is the last message content, trimmed. (not separately verified)
- [ ] `message_count` equals the number of rows. (not separately verified)
- [x] `GET /admin/conversations/{id}` returns the full `ConversationThread` (all roles, id asc).
- [x] Opening a thread side-effect: `mark_conversation_read` clears unread for the conversation.
- [x] Opening a thread side-effect: `clear_attention` clears `needs_attention` for the conversation.
- [x] After opening, the conversation's summary shows `unread=false` and `needs_attention=false`.
- [x] `POST /admin/conversations/{id}/messages` inserts a row with `role="human"`, `read=true`,
      `needs_attention=false`, returns the created `Message`.
- [x] The inserted human message appears in the thread and via the public `after` poll (so the
      visitor can pick it up). Avatar does NOT react (no avatar row auto-inserted).
- [x] `POST /admin/conversations/{id}/resolve` clears `needs_attention` without inserting a message;
      returns `{"ok":true}`.
- [ ] After resolve, the summary shows `needs_attention=false` and the thread is unchanged in count. (not separately verified)
- [x] All four admin data routes return 401 without a valid cookie (guard re-confirmed here too).

---

## 6. Chat SSE (test_chat_stream.py, marker `llm`) — BUILD-SPEC §6/§9, ux-flows C/D/F

### 6a. Streaming agent reply (model call)
- [x] `POST /api/chat` with a simple question streams `data:` lines parseable as JSON.
- [x] First the visitor row is persisted (role=visitor, content=message, conversation_name=name,
      read=false).
- [x] At least one `{"type":"token","text":...}` event is emitted (empty deltas skipped).
- [x] A terminal `{"type":"done","message_id":<int>,"needs_attention":false}` event is emitted.
- [x] An avatar row is persisted with the assembled final text and matching `message_id`.
- [ ] When the model calls a tool, a `{"type":"tool","phase":"called","tool":"faq_tool"}` (or
      `push_tool`) event precedes the text deltas. (not separately verified for faq_tool; push_tool tool event covered in 6c)

### 6b. Qn instant path (NO model call) — ux-flows D
- [x] `POST /api/chat` with `message="Q2"` emits `{"type":"instant","faq":2}` then a
      `{"type":"token","text":<answer>}` then `done` — and makes no model call.
- [x] The avatar row is persisted with `tool_calls=[{"type":"instant","faq":2}]` and the answer text.
- [x] Both the visitor line and the instant answer are stored (history complete).
- [x] `done.needs_attention` is false for the instant path.

### 6c. push_tool → needs_attention — ux-flows F
- [x] `POST /api/chat` with a contact-intent message (e.g. "please contact Ed, email x@y.com")
      triggers a `push_tool` `tool` event.
- [x] The persisted avatar row has `needs_attention=true` (and `read=false`).
- [x] The terminal `done` event reports `"needs_attention":true`.
- [x] A Pushover notification is actually sent (push returns a success status) — optional, allowed
      per SPEC Testing note.

### 6d. Error path
- [ ] On an internal error during streaming, the stream emits `{"type":"error","message":...}` and
      stops cleanly (no half-written partial JSON frame). (not separately verified)

---

## 7. Models (covered indirectly via API serialization)

- [ ] `Role` is constrained to `visitor|avatar|human`; an invalid role is rejected. (not separately verified)
- [ ] `ChatRequest` requires `conversation_id` and `message`; `visitor_name` optional. (not separately verified)
- [ ] `HumanMessageRequest` requires `content`. (not separately verified)
- [ ] `LoginRequest` requires `password`. (not separately verified)
- [x] `Message`, `ConversationThread`, `ConversationSummary`, `ConfigResponse` serialize to the
      exact field names the frontend expects (§8/§9). (exercised via passing public/admin API response-shape assertions)

---

## 8. Supabase connectivity (test_supabase_connection.py — exists, keep)

- [x] Supabase credentials valid; `messages` table reachable.
- [x] Insert + read + delete round-trips successfully (Data API/table/grants correct).

---

## 9. DB cleanup (mandated by SPEC Testing)

- [x] Every test deletes the rows it created (by `conversation_id`) — autouse teardown fixture.
- [x] After the full backend suite runs, no test `conversation_id` rows remain in Supabase
      (verify with a final query / manual spot check). (messages table verified empty, 0 rows)
- [x] No leftover `needs_attention` test rows that would pollute the admin inbox.

---

## 10. Run matrix

- [x] `uv run pytest -q -m "not llm"` passes (no model cost, offline-ish). (30 passed)
- [x] `uv run pytest -q` (full incl. `llm`) passes with `MODEL=openai/gpt-5.4-nano`. (32 total: 30 non-llm + 2 llm passed)
- [x] `uv run pytest tests/test_supabase_connection.py -v` passes (setup validation gate).
