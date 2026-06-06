# MORE features — Test Plan & Results

Tests for the [MORE.md](../MORE.md) enhancements (Phases 0-9; see [MORE_PHASES.md](../MORE_PHASES.md)).
This complements the original [backend](backend-test-plan.md) / [frontend](frontend-test-plan.md) /
[e2e](e2e-test-plan.md) plans, which cover the base app.

## How this was tested

- **Backend:** `cd backend && uv run pytest -q` — **77 passing** against the real Supabase + LLM
  (OpenRouter `gpt-5.4-mini`, allowed per SPEC). New suites: `test_archive.py`, `test_export.py`,
  `test_fetch.py`, `test_instructions.py`, `test_faq_admin.py`, plus extended `test_knowledge.py` /
  `test_supabase_connection.py`.
- **Per-phase E2E** on the real served app (Playwright), plus a multi-agent adversarial review each phase.
- **Phase 9 — full Docker E2E:** built the image (`docker build -t avatar .`), ran the container
  (`-p 8001:8000`, `--env-file .env`; 8000 is taken locally), and exercised every MORE feature in the
  container, including the web-fetch tool. Screenshots captured then deleted; all test conversations
  deleted from Supabase (a **real in-flight visitor conversation was identified and deliberately left
  untouched** — the single Supabase DB is shared with the live site).

---

## Phase 1 — visitor quick wins

- [x] Polling ladder 10s -> 30s@2min -> 2min@10min -> 5min@1hr; idle resets on received human messages.
- [x] `?q=N` deep link opens the page, auto-submits `QN` (instant, no LLM), clears the param from the URL.
      (Container: `/?q=2` rendered Q2's full markdown answer with clickable links; URL became `/`.)
- [x] `?m=...` free-text deep link auto-submits to the LLM; `?q` wins if both present. (Verified Phase 1 live.)
- [x] OG social image `og-avatar.png` (1200x630) present in the project root.

## Phase 2 — FAQ in Supabase

- [x] FAQ served from the `faq` table (61 rows) via `knowledge.py` (cached + `reload_faqs()`).
- [x] `Qn` instant + `faq_tool` routing both return the full original question/answer.
- [x] Pre-existing pagination bug fixed: `db._all_rows()` pages past PostgREST's 1000-row cap, so the
      admin inbox shows ALL conversations (was 111/139).

## Phase 3 — admin main nav

- [x] `Conversations | Archive | Instructions | FAQ` tab strip; section switching persists (localStorage).
- [x] Pre-existing icon bug fixed: `icons.svg` `<style>` restored so all `<use>` icons render as line-art.
- [x] Responsive (icon-only nav on mobile). (Container: verified on a 390px viewport.)

## Phase 4 — additional instructions

- [x] `GET/PUT /admin/instructions` (admin-guarded singleton); injected after the style section, read
      fresh per turn. Markdown editor + Save + dirty-guard + Cmd/Ctrl+S.
- [x] Container: Instructions tab renders the editor. (NOTE: the live singleton currently holds an
      owner-entered test value — see "Known state" below.)

## Phase 5 — FAQ editor

- [x] Admin FAQ CRUD (`GET/POST/PUT/DELETE /admin/faq`); blank fields rejected (422); `reload_faqs()`
      after writes; new ids = max+1. `Qn` / `?q=N` widened to 3 digits.
- [x] Container: FAQ tab shows count (61), Add FAQ, scrollable cards with edit/delete, native dialog.

## Phase 6 — archive

- [x] Archive a whole conversation (copy to `archive`, delete from `messages`); restore (reverse).
      `messages.id` is `GENERATED ALWAYS` so restore reassigns ids; timestamps/content/order/read preserved.
- [x] Thread Archive button; Archive tab list + read-only view dialog + Restore (card + dialog).
- [x] "Archive inactive (72h)" button with a confirm step (selector tested read-only; bulk path via a
      monkeypatched selector so it never touches real data).
- [x] Container: archived my test thread -> appeared in Archive tab (count 1) -> restored -> count 0.

## Phase 7 — download + total

- [x] `GET /admin/export/conversations` + `/admin/export/archive` -> jsonl, one object per message row,
      timestamped `Content-Disposition` filename. Total shown by the count badges.
- [x] Container: Download button saved `conversations-<UTCstamp>.jsonl`; archive Download disabled when empty.

## Phase 8 — web fetch via MCP

- [x] `mcp-server-fetch` attached to the agent per turn via the context manager
      (`async with MCPServerStdio(...) as s: build_agent(mcp_servers=[s])`); `MAX_TURNS=30`.
- [x] Constraint is via the system prompt (owner's choice): fetch only the owner's site + course repos.
- [x] **Fetch works inside Docker** — `mcp-server-fetch` is on PATH (`/usr/local/bin`, via the Dockerfile
      `uv tool install`); a course question through the containerised SSE API fired a `fetch` event and
      answered accurately from the real README; a general question did NOT fetch.
- [x] Fetch tool shown in both UIs (visitor "Looked it up on the web . fetch"; admin "fetch . browsed the
      web") with the globe icon.

## Phase 9 — full Docker E2E (this run)

- [x] `docker build -t avatar .` succeeds (multi-stage; includes `uv tool install mcp-server-fetch`).
- [x] Container serves `/`, `/admin`, `/api/config` (all 200); clean startup logs, no tracebacks.
- [x] Visitor: intro + example prompts, `?q=2` deep link, streamed chat using `faq_tool` AND `fetch`,
      dark + light themes, mobile.
- [x] Admin: dashboard/inbox, open thread, **human reply (3-way)** -> visitor sees the human bubble with
      photo + yellow ring/glow + "Ed Donner . live" tag (owner name from `/api/config`).
- [x] Admin: archive -> Archive tab -> restore; Instructions tab; FAQ tab (61); Download; mobile.
- [x] Multiple `conversation_id`s independent in the inbox.

## Cleanup (SPEC mandate)

- [x] All screenshots deleted.
- [x] All test conversations I created deleted from `messages` + `archive` (verified 0 rows each).
- [x] `archive` table back to 0 rows total; `faq` unchanged (61).
- [x] A real in-flight visitor conversation (not mine) was identified and **left intact**.
- [x] Container left running locally for the owner; **never deployed**.

## Known state (for the owner)

- The `app_settings.instructions` singleton holds `"Extra detail about Ed: his favorite fruit is a
  banana"` — an owner-entered test value from trying the Instructions editor (not created by automated
  tests). It is harmless today (Phase 4 isn't deployed) but WILL be appended to the live prompt once
  deployed. Clear it in the Instructions tab (Save an empty box) if it shouldn't ship.
