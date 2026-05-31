# End-to-End Test Plan

## Test Results

Method: built and ran the real Docker container. `docker build -t avatar .` succeeded (multi-stage:
node:24 builds the frontend with tsc+vite, python:3.12 + `uv sync --frozen --no-dev`, copies
dist + knowledge, `.env` not baked). `scripts/start_mac.sh` and `scripts/stop_mac.sh` verified
working; container run with `--env-file .env`. Exercised routing, two independent visitors, the
admin guard + login, the full three-way conversation, and look/feel; cleaned up afterwards.

Outcome: static serving + routing (/, /admin, /api/config, /icons.svg, /avatar-human.png,
/assets/*.js all 200), visitor-1 model stream, visitor-2 Q3 instant, two independent conversations,
admin 401-before / 200-after login, human reply (role=human) producing the visitor thread
[visitor, avatar, human], and fresh visitor UI all verified. A Docker `--env-file` quote bug was
found (MODEL arrived as `"\"openai/gpt-5.4-nano\""` -> "Unknown prefix") and FIXED via config
`_env()` quote stripping; rebuilt and re-verified chat works. Cleanup done: all test threads
deleted (messages table verified empty, 0 rows), screenshots deleted, container stopped+removed.
Left unchecked: items not exercised in this run (PowerShell scripts on Windows, some discrete
screenshot states, the contact/email push UI flow against the container, container-restart
persistence, and a couple of nice-to-have variants) — noted inline.

---

Build the single Docker container via the provided scripts and run the whole platform end to end:
multiple visitors with different `conversation_id`s, the full three-way conversation (visitor +
avatar + human via `/admin`), and the push-notification path. Use `MODEL=openai/gpt-5.4-nano` to
keep costs low (SPEC Testing note). Capture multiple screenshots, then clean up screenshots and all
test conversation threads in Supabase.

Sources: SPEC.md Testing + Success Criteria + Setup/Validation, BUILD-SPEC §14/§15 (Docker +
scripts), §9 API contract, ux-flows A-G, SKILL §9.

---

## 0. Pre-flight (SPEC Setup & Validation)

- [x] `.env` has all required keys: `OPENROUTER_API_KEY`, `MODEL`, `OWNER_NAME`, `ADMIN_PASSWORD`,
      `PUSHOVER_USER`, `PUSHOVER_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`.
- [x] `MODEL=openai/gpt-5.4-nano` for the e2e run (cost control).
- [x] Supabase connectivity gate passes: `cd backend && uv run pytest tests/test_supabase_connection.py -v`.
- [x] Docker daemon is running.

---

## 1. Container build via scripts (BUILD-SPEC §14/§15)

- [x] `scripts/start_mac.sh` is executable and resolves the repo root from its own location.
- [x] Running `scripts/start_mac.sh` stops+removes any existing `avatar` container, then
      `docker build -t avatar .` succeeds (multi-stage: node:24 builds frontend, python:3.12 runs backend).
- [x] Frontend build stage runs `npm ci && npm run build` with no type errors (`tsc` clean).
- [x] Backend stage runs `uv sync --project backend --frozen --no-dev` successfully.
- [x] `knowledge/` is copied into the image; `FRONTEND_DIST`/`KNOWLEDGE_DIR`/`PORT` env set. (dist + knowledge copied; assets/config served)
- [x] `.env` is NOT baked into the image (`.dockerignore` excludes it); container is run with
      `--env-file .env`.
- [x] `docker run -d --name avatar --env-file .env -p 8000:8000 avatar` starts; script prints
      `http://localhost:8000`.
- [x] Container logs show clean startup (OpenRouter configured, no tracebacks, no emoji in logs). (lifespan configure_openrouter)
- [x] `stop_mac.sh` stops + removes the container cleanly.
- [ ] PowerShell equivalents `start_pc.ps1` / `stop_pc.ps1` exist and mirror the bash behaviour
      (review/verify on Windows if available; otherwise inspect for parity). (not verified on Windows)

---

## 2. Static serving & routing (BUILD-SPEC §9 routing order, §1)

- [x] `GET http://localhost:8000/` serves the visitor page (index).
- [x] `GET http://localhost:8000/admin` serves the admin page.
- [ ] Public assets load: `/icons.svg`, `/avatar-robot-round.png`, `/avatar-human.png`,
      `/avatar-robot.png`, `/favicon.svg`. (/icons.svg + /avatar-human.png verified 200; the other PNGs/favicon not separately requested)
- [x] `/assets/*` (Vite-hashed JS/CSS) load with 200.
- [x] `/api/config` returns `{owner_name}` from `OWNER_NAME` (same-origin, no CORS needed). (200, "Ed Donner" no quotes after env-quote fix)
- [x] `/api` and `/admin` routes are NOT shadowed by the final `/` static mount.

---

## 3. Visitor flow against the container (ux-flows A-D)

- [x] Visitor page autofocuses composer on load; brand subtitle shows `{owner_name} · digital twin`.
- [x] Visitor 1 (cid-A) sends a real question -> avatar reply streams token-by-token over SSE. (Alice: streamed tokens + done in-container)
- [ ] `[screenshot]` e2e-visitor1-streaming.png and e2e-visitor1-complete.png. (streaming verified; named screenshot pair not separately captured)
- [x] A `Qn` instant question (e.g. "Q2") returns the FAQ answer with `instant · Q2` tag and no
      model call. (Bob: Q3 instant + done in-container)
- [ ] `[screenshot]` e2e-visitor1-instant.png. (instant behavior verified; named screenshot not separately captured)
- [x] Composer re-focuses after each send.
- [ ] Thread persists across reload (Keep-chat cookie restores cid-A's history). (cookie persistence verified + backend restore covered; visual container reload-restore not separately verified)

---

## 4. Multiple visitors, different conversation_ids (SPEC Success Criteria)

- [x] Open a second browser context as Visitor 2 (distinct cid-B); send a different message. (Bob, distinct id)
- [x] cid-A and cid-B threads are independent (no cross-talk; each only sees its own messages). (distinct ids, names, message counts)
- [ ] `[screenshot]` e2e-visitor2.png showing Visitor 2's separate thread. (named screenshot not separately captured)
- [x] Both conversations appear as separate rows in `/admin` inbox, most-recent first.

---

## 5. Admin + three-way conversation (ux-flows F/G, SPEC Success Criteria)

- [x] `/admin` shows the login gate; correct `ADMIN_PASSWORD` logs in (httpOnly cookie). (401 before, 200 after)
- [x] `[screenshot]` e2e-admin-gate.png and e2e-admin-dashboard.png. (gate + dashboard captured dark + light)
- [x] Wrong password is rejected with an inline error.
- [x] Inbox shows cid-A and cid-B; unread states correct.
- [x] Selecting cid-A loads the full thread and clears its unread (and attention) flags.
- [x] Human posts a reply on cid-A from admin (role=human). Avatar does NOT react/auto-reply.
- [x] `[screenshot]` e2e-admin-human-reply.png. (admin-side "YOU · SENT TO VISITOR" captured)
- [x] Back on Visitor 1, polling surfaces the human bubble: photo + yellow ring + glow +
      `{owner_name} · live` tag (owner_name from /api/config). (exact tag "Ed Donner · live")
- [x] `[screenshot]` e2e-visitor1-human-bubble.png (dark) and light variant.
- [ ] Visitor 1 sends another message; the avatar's next reply has the human's message in its
      transcript context (continues naturally, does not contradict or impersonate the human). (in-container [visitor, avatar, human] thread built; a follow-up continuation reply not separately verified)
- [x] ↑/↓ arrow keys navigate between cid-A and cid-B in admin.

---

## 6. Push notification path (ux-flows F, SPEC Q&A #10)

- [ ] Visitor expresses contact intent ("I'd like to get in touch") -> avatar asks for email. (push mechanism covered by backend test_chat_contact_triggers_push; contact UI flow not exercised in-container)
- [ ] Visitor provides an email -> avatar calls `push_tool` and tells the visitor it notified the owner. (push_tool + needs_attention covered by backend; in-container UI flow not exercised)
- [x] A real Pushover notification is delivered (allowed in testing per SPEC). (real Pushover fired in backend test_chat_contact_triggers_push)
- [x] That avatar message row is flagged `needs_attention=true`, `read=false`. (verified in backend push test)
- [ ] `/admin` inbox shows the conversation with yellow glow + "Needs you" badge. (covered in frontend run; not separately captured against the container)
- [ ] `[screenshot]` e2e-admin-needs-you.png. (not separately captured)
- [x] Opening the thread clears `needs_attention`; the badge/glow disappears. (opening clears unread+attention verified server-side + row state)
- [ ] Alternatively, "Mark resolved" clears attention without replying. (backend resolve verified; in-container UI action not separately verified)
- [ ] Unanswerable-question path: avatar that cannot answer calls `push_tool`, tells the visitor it
      flagged it for the owner, and the row is marked needs_attention. (not separately verified)

---

## 7. Look & feel under the container (SKILL §8)

- [x] Both screens match the mockups in dark (default) and light; theme persists via localStorage.
- [x] `[screenshot]` e2e-visitor-dark.png, e2e-visitor-light.png, e2e-admin-dark.png,
      e2e-admin-light.png. (dark + light captured for both screens)
- [ ] No gradients in chrome, no purple wash, no left-edge accent bars on panels, no emoji. (no purple wash + no emoji verified; gradients/left-edge-panel-bars not separately audited)
- [x] Icons come from `/icons.svg`.

---

## 8. Resilience / sanity

- [ ] Restarting the container preserves conversations (state is in Supabase, not the container). (state is in Supabase; an explicit restart-persistence check was not separately performed)
- [x] `COOKIE_SECURE` unset works over http://localhost (admin login succeeds without HTTPS). (admin login succeeded in-container over http)
- [x] No unhandled exceptions in container logs across the full run. (clean startup, no tracebacks)

---

## 9. Cleanup (mandated by SPEC Testing + Success Criteria)

- [x] Delete ALL screenshots captured during e2e testing.
- [x] Delete every test conversation thread created (cid-A, cid-B, push-test cids, and any others)
      from the Supabase `messages` table.
- [x] Verify the Supabase `messages` table has no leftover test rows. (verified empty, 0 rows)
- [x] Stop and remove the test container (`scripts/stop_mac.sh`).
- [x] Restore `MODEL` to the intended default if it was changed only for testing (per .env policy). (MODEL stays openai/gpt-5.4-nano per SPEC Q&A #2; no change needed)
