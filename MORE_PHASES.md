# MORE.md - Implementation Phases

Incremental plan for the enhancements in [MORE.md](MORE.md). Each phase is independently
testable; validate before moving on. Work on the `more` branch, commit per phase, never deploy
(local Docker only). See the MORE.md "Questions and Answers" section for the agreed decisions.

**Dependencies:** Phase 0 gates all database-backed work (the owner must run the new README
DDL after step 0.2). Phase 1 (visitor-only wins + OG image) is independent. Phase 3 (admin nav)
precedes the Instructions / FAQ-editor / Archive admin UI.

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

- [ ] 3.1 Add `Conversations | Archive | Instructions | FAQ` tab strip to the appbar + view
      switching; Conversations = existing dashboard; placeholders for the rest; responsive.
- [ ] 3.2 Add needed SVG icons (archive, download, add, delete, save, fetch/globe).

## Phase 4 - Additional instructions

- [ ] 4.1 Backend `GET/PUT /admin/instructions` (singleton `app_settings`); inject into the
      prompt immediately after the style section (fresh read per turn).
- [ ] 4.2 Instructions tab: textarea editor + save + load existing.
- [ ] 4.3 Tests.

## Phase 5 - FAQ editor (admin)

- [ ] 5.1 Backend FAQ CRUD endpoints (admin-guarded).
- [ ] 5.2 FAQ tab: list rows (id/concise/question/answer) with add / edit / delete.
- [ ] 5.3 Tests.

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
