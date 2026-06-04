# MORE.md - Implementation Phases

Incremental plan for the enhancements in [MORE.md](MORE.md). Each phase is independently
testable; validate before moving on. Work on the **`more-build`** branch, commit per phase, never
deploy (the owner deploys; local Docker only). See the MORE.md "Questions and Answers" section for
the agreed decisions.

**Dependencies:** Phase 0 gates all database-backed work (the owner must run the new README
DDL after step 0.2). Phase 1 (visitor-only wins + OG image) is independent. Phase 3 (admin nav)
precedes the Instructions / FAQ-editor / Archive admin UI.

---

## Project Status & Handoff Record  (Phases 0-5 complete; 6-9 remaining)

> Written as a restart/handoff record. If resuming cold, read this whole section first.

### Snapshot
- **Branch:** `more-build` (NOT `more`; base branch is `main`). Working tree clean.
- **Done:** Phases 0,1,2,3,4,5. **Remaining:** Phases 6 (Archive), 7 (Download+Total),
  8 (Web Fetch MCP), 9 (Full E2E & Docker).
- **Next action:** Phase 6 (Archive) - was about to start; paused here on request to write this record.

### Commits (one per phase, on `more-build`)
- `a4a5f68` "Fixed doc" - the OWNER's edits to MORE.md (`?m=` query string, Q54 fix) before work began
- `1fec261` Phase 0 - safety backup, MORE table DDL + connectivity tests
- `5bdfb92` Phase 1 - polling ladder, ?m= deep link, OG social image
- `c787659` Phase 2 - move FAQ to Supabase + fix conversation list pagination
- `b5e9936` Phase 3 - admin main nav scaffolding + fix app-wide icon rendering
- `da5eea4` Phase 4 - admin-editable additional instructions
- `1d734fb` Phase 5 - admin FAQ editor (CRUD over the faq table)  **<- current HEAD**

### Deployment state  (IMPORTANT)
- Production = fly.io app `avatar-ed` (region `sjc`), public at `avatar.edwarddonner.com`
  (WordPress iframe) and `avatar-ed.fly.dev`. Deploy is owner-driven via `./scripts/deploy.sh`
  (builds the current checkout, pushes `.env` as Fly secrets, sets `COOKIE_SECURE=1`). **I never deploy.**
- The owner deployed **once, after Phase 2**, so **production runs Phase 0-2 code** (`c787659`).
  LIVE today: the conversation-pagination fix, FAQ-served-from-Supabase, the 4-tier visitor polling,
  the `?m=` deep link, and the OG image.
- **Phases 3, 4, 5 are committed locally but NOT deployed.** So the live site does NOT yet have:
  the **icon-rendering fix** (live icons still render as solid silhouettes - see bug #2 below),
  the admin 4-tab nav, additional-instructions, or the FAQ editor. The owner can deploy whenever;
  the icon fix + admin features all ship together on the next deploy.

### Environment & key facts
- **Single Supabase DB (`vsdbgmlilyduqkybcltg`) IS production** - shared by local dev, the test
  suite, and the live app. Treat ALL data as real; only ever touch throwaway rows you create.
- Tables: `messages` (original) + `archive`, `app_settings`, `faq` (the owner created these from the
  README "Setup for MORE requirements" DDL in Phase 0). `archive` mirrors `messages` with an explicit
  (non-identity) `id` so restores round-trip ids/timestamps. It is currently UNUSED (Phase 6 builds it).
- `faq`: **61 rows, ids 1-61**, seeded from `knowledge/faq.jsonl` (kept as seed/backup). Source of truth
  is now the DB; `knowledge.py` reads it cached with `reload_faqs()` invalidation.
- `app_settings` singleton (`id=1`): `instructions` is currently **empty** ('') - the live prompt is
  unchanged. (Only Phase 4 code reads it, and Phase 4 isn't deployed.)
- `.env`: `MODEL=openai/gpt-5.4-mini`, `OWNER_NAME="Ed Donner"`, `ADMIN_PASSWORD` set, Supabase keys set.
- Conversations backup (Phase 0): `backups/conversations-20260603T222806Z.jsonl`
  (1150 messages / 139 conversations), gitignored. Re-dump anytime via
  `uv run --directory backend python -m scripts.backup_conversations`.

### Local run / test gotchas
- `./scripts/start_mac.sh` builds+runs the container on :8000, BUT the owner's unrelated `tradewars`
  container occupies :8000. Run avatar on another port instead:
  `docker run -d --name avatar --env-file .env -p 8001:8000 avatar` (image built by start_mac.sh).
- For admin E2E without Docker: `cd frontend && npm run build`, then
  `uv run --directory backend uvicorn app.main:app --port 8010 --app-dir .` (serves built `dist/`,
  including `/admin`). NOTE: `/admin` is NOT served by the Vite dev server.
- Container entrypoint runs `uv sync` on boot (first request waits a few seconds).
- Playwright MCP: `file://` is blocked (serve over http). Native `confirm()` in a page is auto-dismissed
  by Playwright; to test the FAQ delete, override `window.confirm = () => true` in the page first.

### Problems discovered & fixed (beyond the planned MORE features)
1. **Conversation-list pagination (Phase 2.5) - pre-existing prod bug, NOW LIVE-FIXED.**
   `db.list_conversations()` did one unbounded `select` -> PostgREST caps responses at 1000 rows ->
   once `messages` exceeded 1000 (it's at ~1723), the ~28 newest conversations were invisible in admin
   (showed 111 of 139). Fixed with `db._all_rows()` pagination (reused later by archive/export).
   Root cause proven before fixing; shipped in the Phase 2 deploy.
2. **Icon sprite rendering (Phase 3.3) - pre-existing app-wide bug, FIX NOT YET DEPLOYED.**
   `frontend/public/icons.svg` shipped with an empty `<defs>`, missing the painting `<style>` that the
   design-system mockups inline. Every `<use>` icon (visitor + admin) rendered as a solid black
   silhouette instead of line-art (e.g. the live "Reset" control shows a black dot). Restored the
   scoped `symbol{fill:none;stroke:currentColor;...} symbol .fill{...}` block in the sprite; verified
   in Chromium that external `<use>` honours it and that the inline-attr brand logos (LinkedIn/YouTube)
   are unaffected. Ships on the next deploy.
3. **Adversarial-review findings, fixed per phase** (each phase ran a multi-agent review workflow):
   - Phase 3.4: polling re-fetch + desktop auto-select were marking threads read while on a non-
     conversations section -> gated both on `section==='conversations'`.
   - Phase 4.4: **HIGH** unsaved additional-instructions were clobbered on tab round-trip -> dirty-guard;
     **MEDIUM** Cmd/Ctrl+S only worked with the textarea focused -> document-level handler.
   - Phase 5.5: **MEDIUM** blank FAQ fields accepted by the API -> server-side `min_length` validation;
     **MEDIUM** edit dialog could clip Save/Cancel on short viewports -> `max-height` + body scroll;
     **MEDIUM** `Qn`/`?q=N` capped at 2 digits while the editor grows ids past 99 -> widened to 3 digits.

### Testing completed
- **Backend pytest: 63 passing** (`cd backend && uv run pytest -q`). Tests hit the real Supabase and the
  LLM (mini) - allowed/cheap per SPEC. Files added/changed: `test_supabase_connection.py` (new-table
  column checks), `test_instructions.py`, `test_faq_admin.py`, `test_knowledge.py`, `test_agent.py`.
- **Per-phase Playwright E2E on the real served app** (not just mocks): P1 `?m=`/`?q=`; P2 the actual
  Docker container - visitor chat SSE stream, `Qn`-from-DB rendering, admin inbox showing all 139; P3
  nav switching/persistence/mobile/icons; P4 instructions load/save/persist + clobber-guard; P5 FAQ
  create/edit/delete.
- **Adversarial review workflows** for Phases 3, 4, 5; findings triaged, fixed, re-verified.
- **Data-safety, verified after every phase:** all test/E2E data uses throwaway `conversation_id`s /
  FAQ ids; the `app_settings` singleton is restored to empty; confirmed messages test-rows deleted,
  `faq` back to 61, `instructions` == ''. Screenshots/artifacts deleted each phase. Only `og-avatar.png`
  remains in the repo root by design.

### Conventions for resuming (per-phase loop)
implement incrementally -> `npm run build` (tsc) + `uv run pytest -q` -> Playwright E2E on the real
served app -> adversarial review workflow (ultracode is ON) -> fix findings + re-verify -> clean up
test data/screenshots -> tick the boxes in this file -> commit once for the phase (with a
`Co-Authored-By: Claude Opus 4.8 (1M context)` trailer). Never deploy.

### Notes for the remaining phases
- **Phase 6 (Archive) is the most destructive** - it deletes rows from `messages` into `archive`.
  Extra care: only archive throwaway conversations you create; never a real user thread. The 72h
  bulk-archive must be exercised only against self-created rows. `conftest` cleanup must also purge the
  `archive` table for test ids. The `archive` table already exists and preserves ids/timestamps.
- **Known accepted edge (not a bug):** new FAQ ids are `max(id)+1` in app code (fine for a single
  admin); deleting the highest-numbered FAQ frees that number for reuse, so a previously-shared `?q=N`
  link could later resolve to different content. Left as-is, flagged to the owner.

---

## Phase 0 - Safety & schema groundwork

- [x] 0.1 Backup script that dumps every message row to a local, gitignored
      `backups/conversations-<stamp>.jsonl`; run it before any archive/delete work.
      (`backend/scripts/backup_conversations.py`; ran it - 1150 messages / 139 conversations.)
- [x] 0.2 README "Setup for MORE requirements" section with DDL for the three new tables
      (`archive`, `app_settings`, `faq`) for the owner to run in the Supabase SQL editor.
- [x] 0.3 Extend `test_supabase_connection.py` to validate the three new tables' columns so the
      setup-validation gate includes them. (3 new-table tests fail until 0.4 is done - expected.)
- [ ] 0.4 Owner runs the DDL in Supabase; connectivity test passes (green light for DB phases).

## Phase 1 - Quick visitor-only wins (no DB)

- [x] 1.1 Polling: replace the 2-tier (10s/60s) loop with the 4-tier ladder
      (10s / 30s@2min / 2min@10min / 5min@1hr); idle resets on received human messages too.
      (`pollDelay()` ladder in `visitor/main.ts`; timing E2E deferred to Phase 9.)
- [x] 1.2 `?m=` param: handle in `boot()` alongside `?q=N` (parse -> `replaceState` -> `send()`);
      `q` wins if both present. (Verified live: `?m=` decodes+submits, `?q=N`->"QN", q beats m.)
- [x] 1.3 OG image: generate `og-avatar.png` (1200x630) in the project root from avatar assets.
      (1200x630 PNG rendered from the HUD twin portrait with brand fonts/tokens.)

## Phase 2 - FAQ to Supabase (backend)

- [x] 2.1 Fix `faq.jsonl` content: backticked API-key identifiers (Q6/Q12/Q18), reworded Q6's
      bold-on-AI, removed Q54 & Q25 screenshot notes, fixed Q10 `3.1`1->`3.11`, Q11/Q60 typo,
      Q50 quadruple-star. (Reviewed and approved.)
- [x] 2.2 Seed script `scripts/seed_faq.py`: idempotent upsert jsonl -> `faq` table
      (`id`=faq, `concise`=query). Seeded 61 rows.
- [x] 2.3 Repoint `knowledge.py` to read FAQ from the DB via `db.list_faqs()` (cached with a
      `reload_faqs()` invalidation hook for the Phase 5 editor); jsonl kept as seed.
- [x] 2.4 Updated `test_knowledge.py` (FAQ-from-DB + reload hook). Full suite green (51 passed).
- [x] 2.5 Bugfix (discovered): `db.list_conversations()` hit PostgREST's 1000-row cap once the
      messages table exceeded 1000 rows, hiding the newest conversations from admin. Added
      `db._all_rows()` pagination. Conversations visible went 111 -> 139.

## Phase 3 - Admin main nav scaffolding

- [x] 3.1 Added `Conversations | Archive | Instructions | FAQ` tab strip in the appbar + section
      switching (`setSection`/`wireNav`, persisted to localStorage, aria-controls); Conversations =
      existing dashboard; placeholder panels for the rest; responsive (icon-only nav on mobile).
- [x] 3.2 Added SVG icons: archive, download, plus, trash, save, globe, help.
- [x] 3.3 Bugfix (discovered): `frontend/public/icons.svg` shipped without the painting `<style>`,
      so ALL icons (visitor + admin) rendered as solid silhouettes instead of line-art. Restored
      the scoped `symbol{fill:none;stroke:currentColor;...}` block; verified brand logos unaffected.
- [x] 3.4 Review fixes (adversarial workflow): guarded polling re-fetch and desktop auto-select on
      `section==='conversations'` so a restored/active panel never silently marks a thread read.

## Phase 4 - Additional instructions

- [x] 4.1 Backend `GET/PUT /admin/instructions` (singleton `app_settings` via
      `db.get_instructions`/`set_instructions`); injected into the prompt immediately after the
      style section, read fresh per turn (uncached) so edits apply without a restart.
- [x] 4.2 Instructions tab: monospace Markdown editor + Save (purple primary) + status; loads the
      saved value on open; Cmd/Ctrl+S to save; dirty-guard so a tab round-trip never loses edits.
- [x] 4.3 Tests: `test_instructions.py` (401 guards, PUT/GET roundtrip, prompt-injection-after-style,
      empty-omits-section; a preserve fixture restores + asserts the live singleton). Full suite 56 passed.
- [x] 4.4 Review fixes (adversarial workflow): HIGH unsaved-edits clobber -> dirty-guard;
      MEDIUM Cmd+S only-when-textarea-focused -> document-level handler gated to the section;
      LOWs (case-insensitive shortcut, in-flight save guard, fixture restore assertion).

## Phase 5 - FAQ editor (admin)

- [x] 5.1 Backend FAQ CRUD: `db.create_faq`/`update_faq`/`delete_faq`; admin-guarded
      GET/POST/PUT/DELETE `/admin/faq`; each write calls `knowledge.reload_faqs()`. New rows get
      id = max+1; `FaqInput` rejects blank/whitespace fields (422).
- [x] 5.2 FAQ tab: count + "Add FAQ"; scrollable cards (Q-number, concise, question, edit/delete);
      native `<dialog>` editor (concise/question/answer) for add + edit; delete behind a confirm.
- [x] 5.3 Tests: `test_faq_admin.py` (401 guards x4, CRUD roundtrip, 404-on-missing, 422-on-blank;
      cleanup fixture keeps the live table at 61). Full suite 63 passed; E2E create/edit/delete verified.
- [x] 5.4 Widened the `Qn` / `?q=N` cap from 2 to 3 digits (Q1..Q999) since the editor lets ids
      grow past 99 (backend `INSTANT_RE` + visitor `?q` parser + tests).
- [x] 5.5 Review fixes (adversarial workflow): MEDIUM blank-input validation + Qn>99 cap;
      MEDIUM dialog max-height/scroll + mobile width; LOWs (reset edit-id on dialog close,
      double-delete guard, focus first empty field on validation error).

## Phase 6 - Archive

- [ ] 6.1 Backend: `archive` model + db functions - archive a conversation (copy rows to
      `archive`, delete from `messages`), restore (reverse), list archive, archive-inactive-72h
      (max `created_at` per conversation < cutoff, bulk, returns count). Preserve ids/timestamps.
- [ ] 6.2 Admin: thread-level Archive button (by "Mark resolved"); Archive tab list + Restore;
      "Archive all inactive 72h" button with a confirm step.
- [ ] 6.3 `conftest` cleanup also purges `archive` for test ids; tests.

## Phase 7 - Download + Total

- [ ] 7.1 Backend export endpoints (jsonl, one object per message row) for conversations + archive.
- [ ] 7.2 Admin: Download button + total count near the top of both pages.
- [ ] 7.3 Tests.

## Phase 8 - Web Fetch MCP

- [ ] 8.1 Wire `MCPServerStdio('mcp-server-fetch')` per chat turn into `stream_agent`; merge the
      reference INSTRUCTIONS into the prompt; reconcile faq -> fetch -> push ordering.
- [ ] 8.2 Dockerfile: `uv tool install mcp-server-fetch` so no first-request download.
- [ ] 8.3 UI: friendly label + icon for the fetch tool (visitor + admin). Tests.

## Phase 9 - Full E2E & Docker

- [ ] 9.1 Build container via `start_mac.sh`; comprehensive Playwright E2E across all features
      with screenshots; multi-party (visitor/avatar/human) + multiple `conversation_id`s.
- [ ] 9.2 Update the `test/` plans with new checkboxes.
- [ ] 9.3 Delete all test data + screenshots.
