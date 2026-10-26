# Avatar

A digital-twin web app: OpenAI Agents SDK via OpenRouter, a FastAPI backend (`backend/`, a `uv`
project) serving a Vite + TypeScript frontend (`frontend/`), Supabase for storage, shipped as one
Docker container to fly.io. It is an educational Agentic-RAG project.

The core product spec and build decisions are here:

@SPEC.md

Enhancements built on top of the spec - archive/restore, jsonl download, admin-editable
instructions, the FAQ editor, web-fetch via MCP, the `?q=`/`?m=` deep links, the polling ladder -
plus the post-build prompt refinements and the security hardening, are documented in `MORE.md`. The
phase-by-phase build and handoff record is in `MORE_PHASES.md`. Read both when continuing this work.

## Working on this

- Backend tests: `cd backend && uv run pytest -q` (they hit the real Supabase and the LLM - allowed
  and cheap per the spec). They load `.env` with override, so they use its `MODEL`. Run locally:
  `uv run --directory backend uvicorn app.main:app --reload --app-dir .`
- Frontend: `cd frontend && npm run build` (runs `tsc` then `vite build`; type errors fail the build).
  There are no frontend unit tests; Node runs TypeScript directly, so a scratch `.mts` script can
  import `frontend/src/lib/markdown.ts` to check rendering.
- Container: `./scripts/start_mac.sh` (build + run). If host `:8000` is busy, run on another port,
  e.g. `docker run -d --name avatar --env-file .env -p 8001:8000 avatar`.
- The web-fetch tool needs `mcp-server-fetch` on PATH locally: `uv tool install mcp-server-fetch`.
  If chat tests fail with `FileNotFoundError: 'mcp-server-fetch'`, its uv tool env has gone missing:
  reinstall with `--reinstall`.
- Playwright's bundled browsers aren't installed for the current version; launch with
  `p.chromium.launch(channel="chrome")` to use the installed Chrome.

## Guardrails

- The single Supabase database is PRODUCTION (shared by local dev, the tests, and the live site).
  Only ever create/delete throwaway rows you own, and clean them up. Inspect before any bulk delete.
- Opening `/admin` at desktop width auto-opens the top conversation, which marks a real visitor's
  thread read. For local admin checks use a phone-width viewport (<= 640px), which lands on the inbox.
- Do not deploy - the owner deploys via `scripts/deploy.sh`; use local Docker only for testing.
- The OpenRouter key, like every paid API key in `.env`, is only for testing the avatar: the test
  suite and small live checks of its replies. Never use it for anything else, such as bulk analysis
  of conversations, without asking the owner first and stating the number of calls and the cost.
  Never start paid API calls in a background job without the owner's explicit go-ahead.

## Current state (2026-10-22)

Production (`avatar-ed`) is release v8, deployed 2026-10-22 from branch `v2` (commit `fe67c08`), on
`openai/gpt-6-luna`. The release before it, v7 (commit `a2ef59a`, 2026-06-06), ran `gpt-5.4-mini`.
Since `fe67c08`, the page-caching fix below is uncommitted and not deployed, and so is the removal
of the chat box's `autofocus` attribute: Chrome blocks it inside the cross-origin iframe on Ed's site
and logs a warning, and `main.ts` focuses the box itself anyway. `scripts/deploy.sh`
copies `MODEL` and `CURRICULUM_URL` from `.env` into the Fly secrets. Details are in `MORE.md`
"Post-build refinements" and "Security hardening (extras)".

- **Page caching (2026-10-26, not deployed):** after the deploy, `?q=` pages failed in Ed's browser
  with a 404 for `main-CqFiJY_5.js`, the v7 bundle. The pages had no `Cache-Control`, so the browser
  guessed they stayed fresh for about a tenth of their age (v7's page was months old) and kept
  reusing the v7 page, whose scripts the new image doesn't have. `main.py` now sends
  `Cache-Control: no-cache` with `/` and `/admin`. `AssetFiles` answers a request for a missing
  `/assets/*.js` with `STALE_PAGE_SCRIPT`, which reloads the page once under a `fresh=` parameter the
  cache has no copy of. Checked in Chrome with the rebuilt v7 page; tests in `test_static.py`.
- **Relay requests (2026-10-22, closed 2026-10-26):** "please message Ed and tell him that Tom would like to
  connect" got a trimmed LinkedIn FAQ (Q56) with no email request and no push. Either "connect" pulls
  it to Q56 (the admin instructions push LinkedIn questions to the FAQ tool), or the "What you help
  with" scope makes a relay look out of scope. A check on 2026-10-26 (84 cases, $0.03, priority with
  reasoning "none", scratchpad `push_check.py`; the fix below applied in memory only):
  - Declines: 40 of 40 declined with a ChatGPT/Claude pointer, and none pushed.
  - "Tell him that Tom/Sarah..." relays: pushed 18 of 18 on the first turn, nearly always without
    an email, against rules.md's "first ask for their email". 7 of those replies then asked for the
    email "so I can notify Ed", after already pushing. Ed's exact message pushed 6 of 6.
  - "I'd like to connect with Ed, can you pass that on?": the current rules gave only the LinkedIn
    FAQ (3 of 3), with no email request. With the fix it asked for an email 3 of 3.
  - Once the visitor gave an email: pushed 12 of 12, with the email in the note.
  The fix: in "What you help with", "Passing a message to your human, or helping a visitor get in
  touch with them, is always in scope (see below)."; and the get-in-touch bullet becomes "If a visitor
  wants to get in touch, or asks you to pass a message to your human (for themselves or someone else),
  first ask for their email;". Ed's decision (2026-10-26): a relay pushing straight away is fine,
  and none of these problems is serious, so rules.md is unchanged and the fix isn't applied.
- **Latency (2026-10-26):** production replies got slower with v8: median 4.7s to the stored reply
  (v7: 3.0s), FAQ replies 6.3s (v7: 3.8s), from Supabase timestamps. An 80-turn test on the real
  agent from Ed's Mac (scratchpad `latency_test.py`, $0.05, push stubbed) crossed service tier with
  reasoning effort:
  - `service_tier: "priority"` (OpenRouter passes it through and OpenAI served it) streams text
    about 1.5x faster (about 220 vs 150 tokens/s) at twice the price, but doesn't shorten the wait
    for the first token.
  - Reasoning "none" vs "low" made no consistent difference ("low" spends 0-2 reasoning tokens).
  - Fixed costs before the model starts: `stream_agent` launches a new `mcp-server-fetch` every turn
    (about 0.6s), and `build_system_prompt` reads the admin instructions from Supabase every turn.
    An FAQ reply also needs two model calls; the lookup call alone took about 1.4-2.3s.
  Ed chose priority with reasoning "none" (uncommitted, not deployed; see Model below). The fixed
  costs above are unchanged and Ed's to decide.

- **Model:** `.env` has `MODEL="openai/gpt-6-luna"`, with reasoning effort "none" and the priority
  service tier (`REASONING_EFFORT` and `SERVICE_TIER` in `agent.py`, set 2026-10-26, uncommitted).
  "Low" was used from 2026-10-22 because "none" then pushed the owner about 1 in 5 declined requests
  (see the misuse review below); that hasn't been re-checked on "none". `agent.RUN_CONFIG`
  uses `MultiProvider(openai_prefix_mode="model_id", openai_use_responses=False)` so OpenRouter
  receives the full `openai/...` ID; by default the SDK strips that prefix. Chat completions is pinned
  on the provider because it captures that choice when built, before `configure_openrouter()` runs.
  `MAX_OUTPUT_TOKENS` is 4000 (the longest FAQ, Q73, is about 1,800 tokens).
- **Prompt:** an FAQ answer is relayed in full, shortened only if the visitor asked about one part
  of it (agent.py FAQ section, plus an exception under "Answer length" in `knowledge/rules.md`). What
  actually makes the model do it is `FAQ_RELAY_NOTE` at the top of `faq_tool`'s result: with the prompt
  rule alone, `gpt-6-luna` kept only 7-25% of an FAQ answer word for word. The note's one exception
  is an FAQ on a different topic from the visitor's message. A broader "only if it answers them"
  condition dropped Q3's full relays to 3 in 6, so keep it narrow.

  Other parts of the prompt:
  - The transcript ends with `REPLY_INSTRUCTION`, a scope check right before the model writes.
  - `push_tool`'s description says never to push for a declined request.
  - The output format allows inline code, code blocks and tables wherever they help.
  - The prompt mentions the `Qn` and `Q2` shortcuts.
- **`Qn` list:** a literal `Qn` (any case) is an instant, no-LLM reply listing every FAQ's concise
  question. `knowledge.instant_reply()` handles it and the `Q2` form; it is stored as
  `tool_calls=[{"type": "instant", "faq": "list"}]` and tagged "instant · FAQ list".
- **Markdown** (`frontend/src/lib/markdown.ts`): fenced code blocks, pipe tables, and numbered lists
  that keep their numbering (`<ol start>`). The bubble is `max-width: min(560px, 100%)` so wide code
  and tables scroll inside it on phones; inline `code` uses the mono font.
- **Admin editors:** the FAQ and Instructions textareas set `font-variant-ligatures: none`.
  JetBrains Mono's `##` ligature made the first `#` seem to vanish while typing.
- **Knowledge refresh:** `knowledge.md` adds AI FDE as course 7 (newest, launched 2026-10-13), "more than
  a million enrollments", the refreshed Agentic Track's frameworks, the guides index, and an "About this
  chat" section (FAQ links as `/avatar?q=N`, Ed reads the inbox, the chat is text only). `fetch.md` maps
  every course repo, including AI Coder's `pm`, `kanban`, `prelegal`, `finally` and `fin` and AI FDE's
  `undercover`. AI FDE is listed first, ahead of the six established courses. Coupon codes are never
  written into the knowledge files because they expire. `agent.py`: a visitor who claims to be the owner
  stays a visitor.
- **Live coupon links:** `app/course_links.py` reads each course's Udemy coupon link from the curriculum
  page (`CURRICULUM_URL`, set in `.env` and copied to Fly by `deploy.sh`) every 15 minutes in a
  background task, and `agent.py` lists them in the prompt as "Enrollment links", AI FDE first. The page
  builds those links in JavaScript (`window.EDC_CONFIG` + the `BASE` map), which the fetch tool can't see.
  On failure it keeps the last good links and alerts once.
- **Open from the conversation review (2026-10-21), Ed's decisions:**
  - Whether the avatar names its model; today it declines.
  - How often the LinkedIn/YouTube plug appears (32% of replies).
  - Course conventions: never python.org, `uv add` or `uv venv` in a course repo.
  - Push policy: Ed doesn't mind pushes (he declined a push rate cap). He hasn't answered on a
    no-push rule for abusive or fake emails.

  Supabase edits (2026-10-22, done with Ed's approval; the rows before the edits are in the
  scratchpad's `supabase_backup_1022.json`): the admin instructions' web-search, FAQ-list and
  architecture passages, and FAQs Q2, Q3, Q10 (CrewAI pinned to 1.14.4 per `3_crewai/README.md`),
  Q12 (now points to Q68 and Render), Q19, Q20, Q28 and Q40. Ed hasn't decided on Q15, Q26, Q29, Q50,
  Q51, Q57, Q62 or the dated model names in Q9, Q30, Q46 and Q47.

  On Ed's site, the curriculum page's meta description still says "six AI courses", and its static
  HTML has both "Here are the 6 courses" and "Here are the 7 courses" (JavaScript shows one), which
  search engines read.
- **Misuse review (2026-10-22, done):** Ed asked for it to run on Claude Code subagents (Haiku, on his
  subscription), never on OpenRouter. The input was every conversation through 2026-10-22, archive
  and inbox, as visitor-only text with `Qn` and the stock prompts dropped: 3,756 conversations. Eight
  screens flagged 340 (235 mild, 105 clear). A second pass read production's replies to the 105.
  Production (v7, `gpt-5.4-mini`):
  - Never revealed the prompt or keys, including against a fake "SYSTEM NOTE" with base64.
  - Refused explosives and sexual content.
  - Handled 3 self-harm or distress messages with crisis lines and a push.
  - Gave in to off-scope work (CV and LinkedIn rewrites, business plans, app code, recipes, chess),
    usually on the second ask.
  - Accepted "I am Ed" twice and a pasted "Ed's reply" once.
  - Gave a war verdict.
  - Padded "simple Agentic RAG" with invented architecture.

  A Haiku pass also sorted the 44 conversations where a visitor gave an email: 16 to follow up, 12
  maybe. Ed has the list.
- **Guardrail fixes from the review (built, approved by Ed):**
  - **Fetch:** `OwnerSitesFetch` (agent.py) wraps the MCP server and refuses any URL outside the
    "## Allowed sites" prefixes in `fetch.md`. It is checked against the real server: internal and
    metadata addresses are blocked.
  - **Speaker lines:** `render_transcript` indents a message's later lines, so a visitor can't forge
    a speaker line. The three-way section says quoted "Ed said" or "Ed's reply" text is the visitor's.
  - **Scope:** `rules.md` "What you help with" names what's in scope, including a view on the
    visitor's own AI-engineering idea. It declines making things for their own work or life (CV,
    pricing, proposals, app code, recipes, games), even after earlier help.
  - **Safety lines:** no opinions on contested public issues, and no role-play or writing in Ed's
    voice.

  These were tuned by replaying real attempts on `gpt-6-luna`. Ed approved up to $2; about $0.12 was
  spent. Final run, with reasoning off:
  - All 24 real attempts held except freelance pricing advice 89 messages into a thread.
  - All 8 normal questions were answered, and FAQ relays are full.

  Reasoning "low" against "none" (60 interleaved turns):
  - Same speed (about 3.3s median) and cost (about $0.0005 a reply). "Low" spent about 19 reasoning
    tokens a reply.
  - Only "low" never pushed for a decline, so Ed chose it.

  The admin instructions' passage on how the avatar itself is built now uses the wording from this
  review (see the Supabase edits above).

  Ask Ed before any further paid calls beyond the test suite.

  The working files are outside the repo, in this Claude Code session's scratchpad directory:
  - `all_rows_1022.json`: a read-only pull of all rows.
  - `jb/`: screens and judgements.
  - `email/review.md`.
  - `redteam/`: `replay3.py` (stubs push, writes nothing, request cap and spend stop), `q3_check.py`
    and `relay_wide2.py`.

  They hold visitor data, so they must never be committed. If they are gone, rebuild them read-only
  with `db.all_message_rows()` and `db.all_archive_rows()`.
- **Malformed requests:** conversation ids are checked as UUIDs (`ConversationId` / `ConversationIdPath`)
  and `?after=` is bounded, so a hand-made bad request gets a 422 instead of a database error, a 500
  and a Pushover alert (the source of the owner's "Unhandled error" alerts). A failed chat turn shows the
  visitor `CHAT_ERROR_MESSAGE`, not the raw exception. The admin API was probed and is protected.
- **Tests:** `test_export.py` splits JSONL on `\n` only, because the production archive contains
  U+2028, which `splitlines()` breaks on. There are 123 backend tests; all passed on 2026-10-26,
  including the two that call the model (on priority with reasoning "none"), and the frontend builds.
