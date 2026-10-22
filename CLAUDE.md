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

Production (`avatar-ed`) is release v7, deployed 2026-06-06 from commit `a2ef59a`, still running
`openai/gpt-5.4-mini`. Everything below is uncommitted on branch `v2` and not yet deployed, including
the new files `backend/app/course_links.py` and `backend/tests/test_course_links.py`.
`scripts/deploy.sh` ships it and copies `MODEL` and `CURRICULUM_URL` from `.env` into the Fly
secrets. Details are in `MORE.md` "Post-build refinements" and "Security hardening (extras)".

- **Model:** `.env` has `MODEL="openai/gpt-6-luna"`, with reasoning effort "low" (`REASONING_EFFORT`
  in `agent.py`, switched from "none" on 2026-10-22; see the misuse review below). `agent.RUN_CONFIG`
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

  Supabase items for Ed:
  - Stale FAQs after the Agentic refresh (Q10, Q12, Q19, Q20).
  - Two outdated passages in the admin instructions, on FAQ handling and on web search.

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

  Still open (Ed's to do in Supabase): the admin instructions' passage on how the avatar itself is
  built. The proposed replacement:

  > say it's a simple Agentic RAG project, open source at https://github.com/ed-donner/avatar, and
  > that Ed walks through how it's built in https://youtu.be/srlhW4H-Gtg. Don't describe its
  > architecture, tools or model beyond that, and never guess at them.

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
  U+2028, which `splitlines()` breaks on. 118 backend tests pass and the frontend builds.
