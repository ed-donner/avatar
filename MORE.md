# Building Additional Functionality

For the next evolution of the Digital Twin, here are some enhancements.
Please note: you should never deploy to production; only ever work locally, deploying to the local docker.

IMPORTANT NOTE:

Also note: there only is one Supabase database, and it's production. Only archive messages that you create. Be very careful when you're testing so that you don't accidentally delete actual user conversations in flight. It would be worth saving all conversations so far locally just as a protection in case anything goes wrong.

After all changes are implemented, the Admin will have a main nav for 4 sections:

Conversations | Archive | Instructions | FAQ

## Archive functionality

There should be another database table called archive with the same structure as conversations.
The admin user should have an archive button on each message to click to archive it.
Archiving a conversation adds the conversation to the archive table, and then deletes it from the conversations table.
There should also be a button on the Admin screens "Archive all conversations with no activity in 72 hours".
The Admin screens should have a main nav with the ability to switch to the Archive Conversations. From there, you can see the entire list of Archived conversations. It should be possible to restore a conversation.
All these operations should apply to an entire conversation.

## Download button and Total

On both the "Conversations" page and the "Archive" page, there should also be a Download button, that downloads all the conversations / archive to a jsonl file locally. Also somewhere near the top each page should state the total number of conversations or archive conversations.

## Polling frequency

Check the current approach for the visitor screens polling. Make it so that:
It polls for Ed messages every 10 seconds after each message.
If no messages for 2 mins, it starts polling every 30 seconds.
If no messages for 10 mins, it starts polling every 2 mins.
If no messages for 1 hour, it starts polling every 5 mins.

That will reduce the level of activity on the server.

## Additional prompt instructions

The admin dashboard main nav, in addition to having Conversations and Archive, should also have a section for addiitonal instructions.
This should have a freeform field containing Markdown stored in the Supabase database.
The existing value should be shown to the admin, empty initially, and additional markdown can be added by the admin and saved.
This is appended to the prompt as part of the system prompt after the style section.

## Move FAQ to Supabase

The FAQ jsonl should be moved to be a Supabase table (with id, concise, question and answer as 4 columns).
There should be an editor in the UI to update, delete, add questions.
When uploading the FAQ to Supabase, note that there are some problems with it: there are cases where OPENAI_API_KEY needs to have markdown code blocks like `OPENAI_API_KEY` otherwise the underscores appear as emphasis highlights.
Also Q54 incorrectly references an image.
Check that the other questions are all appropriate for this purpose.

## Web Fetch with MCP for edwarddonner.com and for course repos

Use your openai-mcp skill to build this.
See the reference implementation in reference/fetch.ipynb.
Add this web server functionality to the Agent via the fetch MCP server, including something similar to the given INSTRUCTIONS in the reference. Ensure that the agent doesn't use this for generic web searching through prompting, just as described in the reference implementation.
Ensure that the use of fetch MCP tool is shown in the UI, along with the faq tool and push tool.

## Generate image for social icons, for when the Avatar link is pasted into LinkedIn / etc

I'd like to add og social icons to the Avatar webpage on my wordpress site. Please create an appropriately sized file and save it as og-avatar in the project root.

## Support another query parameter

It should be possible to pass in a question like this:

localhost:8000/?m=whats+the+price+of+sliced+bread

And that will be entered (and return key pressed) automatically as a message to the avatar.
If necessary, let me know if I need to change the snippet in Wordpress to support the passthrough, but this is what's there now and it looks good to me:

```
<div id="avatar-embed">
    <iframe id="avatar-frame" title="Ed Donner's Digital Twin" referrerpolicy="strict-origin-when-cross-origin"></iframe>
  </div>

  <style>
    html, body { overflow-x: hidden; }            /* nav can overflow sideways on small screens */
    #avatar-embed {
      position: fixed; left: 0;
      width: 100vw; max-width: none;              /* beat the theme's content-column max-width */
      margin: 0; padding: 0; z-index: 1;
      background: #032147;                        /* navy backdrop while the app loads */
    }
    #avatar-frame { width: 100%; height: 100%; border: 0; display: block; margin: 0; }
  </style>

  <script>
  (function () {
    var BASE = 'https://avatar.edwarddonner.com'; /* same-site as the host page -> first-party cookies */
    var box = document.getElementById('avatar-embed');
    var frame = document.getElementById('avatar-frame');

    frame.src = BASE + '/' + location.search;     /* passthrough: edwarddonner.com/avatar?q=2 */

    function fit() {
      var header = document.querySelector('header, .wp-site-blocks > header, .site-header');
      var top = header ? Math.max(0, Math.round(header.getBoundingClientRect().bottom)) : 0;
      box.style.top = top + 'px';
      box.style.height = 'calc(100dvh - ' + top + 'px)';
    }
    fit();
    addEventListener('resize', fit);
    addEventListener('orientationchange', fit);
  })();
  </script>
  ```

## Questions and Answers

Clarifications agreed before starting work (decisions for the items above):

1. **`m=` is a query string, not a path.** Implemented exactly like the existing `?q=N` deep link: read from `location.search`, cleared from the URL with `history.replaceState`, then auto-submitted through the normal send path. No WordPress snippet change is needed (it already forwards `location.search`). If both `?q=N` and `?m=...` are present, `?q` wins (instant FAQ, no LLM); `m=` is free text routed to the LLM with no validation beyond non-empty (the backend 20,000-char clamp still applies).

2. **The image-reference fix is Q54 (and Q25), not Q50.** Their trailing italic notes (e.g. `_(A screenshot illustrates clicking the 'Editor Window' option...)_`) describe screenshots that don't exist in a text FAQ; they are reworded/removed during the migration.

3. **Underscore/backtick fixes.** Identifiers such as `OPENAI_API_KEY` whose underscores render as emphasis are wrapped in inline backticks. Special case: Q6 deliberately writes `OPEN`**`AI`**`_API_KEY` to teach that "OPENAI" contains "AI" - since you can't bold inside inline code, that teaching point is reworded in plain prose with the identifiers in backticks (e.g. "it's `OPENAI_API_KEY` - note the AI - not `OPEN_API_KEY`"). Approach left to Claude's discretion.

4. **Archive is conversation/thread-level, not per-message.** A single Archive button at the thread level (next to "Mark resolved"); it archives the whole conversation. The same whole-conversation semantics apply to restore and the 72h bulk archive.

5. **Admin main nav** is a horizontal tab strip in the existing appbar: `Conversations | Archive | Instructions | FAQ`, responsive on mobile. All four tabs share the existing admin session.

6. **FAQ table columns** are `id`, `concise`, `question`, `answer`. `id` equals the existing FAQ number (preserved 1-61 so the `Qn` shortcut and `?q=N` deep link keep resolving; new rows get `max(id)+1`). `concise` is the old `query` routing phrase. The Supabase table becomes the source of truth; `knowledge/faq.jsonl` is kept as a seed/backup. The exact Supabase setup steps for the new tables are documented in a new README section at the end headed **"Setup for MORE requirements"** for the owner to run in the Supabase SQL editor.

7. **Download** exports **one JSON object per message row** (mirroring the table) via a backend export endpoint with `Content-Disposition`, on both the Conversations and Archive pages. The total conversation count is shown near the top of each page.

8. **Additional instructions** are stored in a single-row settings table, read fresh on every chat turn (not cached, so admin edits take effect immediately), and injected as their own section immediately after the style section of the system prompt. Empty initially.

9. **New tables** (`archive`, the settings table, `faq`) are documented in the README with the same DDL + `service_role` grant + "no RLS" pattern as `messages`, and are covered by the connectivity test so the setup-validation gate includes them.

10. **Web Fetch MCP** uses the reference pattern: `MCPServerStdio` running `mcp-server-fetch`, entered per chat turn, with the reference INSTRUCTIONS merged into the system prompt (prompt-only constraint to edwarddonner.com course pages + the `llm_engineering` / `agents` / `production` repos via `raw.githubusercontent.com` and `api.github.com`; no generic web browsing). `mcp-server-fetch` is pre-installed in the Dockerfile so the first request doesn't pay a download. Model stays `settings.model` (gpt-5.4-mini is available locally). Fetch tool-use is shown in the UI alongside the FAQ and push tools.

11. **OG image** is a standalone 1200x630 PNG `og-avatar.png` saved in the project root, derived from the avatar assets. It is not served by the app and no `og:image` meta tags are added (the owner uploads it to the WordPress site).

12. **Polling** - the new 4-tier ladder (10s / 30s after 2min / 2min after 10min / 5min after 1hr) fully replaces the old 10s/60s scheme; "idle" resets on received human messages as well as on sends.

13. **Safety on the production database.** Before any archive/delete work, all existing conversations are backed up to a local jsonl. All testing uses throwaway `conversation_id`s that are cleaned up afterwards; the 72h bulk-archive is exercised only against self-created rows. Never deploy - local Docker only.

## Post-build refinements

After the phased build (Phases 0-9), these refinements were made to the prompt and model wiring:

- **`rules.md` split + heading convention.** The owner knowledge in `knowledge/` is now three files, each with one job: `knowledge.md` (facts about the owner, incl. the jobs/courses guidance and course-resource links), `style.md` (the owner's unique voice and formatting), and `rules.md` (owner-agnostic operating rules: safety, escalation, answer length). Every knowledge file starts its headings at `##` so they nest under the prompt's `#` sections, keeping the assembled prompt's hierarchy consistent.
- **Hard output cap + cache-friendly ordering.** `build_agent` sets `ModelSettings(max_tokens=4000)` (raised from 2000 so the longest FAQ, ~1,800 tokens, can be relayed in full) as a hard per-reply ceiling (with a graceful "kept it brief" note appended on the rare truncation, detected via the last response's own token usage). The admin's additional-instructions block is placed LAST in the system prompt: prompt caching is prefix-based, so the editable, per-turn block sits after the long static prefix it would otherwise invalidate (and gains recency emphasis).
- **Model ID passed verbatim, low reasoning.** The Agents SDK's default `MultiProvider` treats an `openai/` prefix as a provider alias and strips it, so OpenRouter received `gpt-5.4-mini`. `agent.RUN_CONFIG` uses `MultiProvider(openai_prefix_mode="model_id", openai_use_responses=False)` so `MODEL` arrives exactly as written; chat completions is pinned on the provider because it captures that setting at construction, before `configure_openrouter()` runs. `ModelSettings` also sets the reasoning effort: "none" at first, then "low" (`REASONING_EFFORT`) after the comparison under "Scope rules from the misuse review". Production moved from `openai/gpt-5.4-mini` to `openai/gpt-6-luna`.
- **Code blocks and tables in messages.** `frontend/src/lib/markdown.ts` renders fenced code blocks (verbatim; an indented fence inside a list item has its indent removed) and pipe tables (alignment, outer pipes optional, `\|` for a literal pipe, an all-empty header row dropped). Numbered lists keep the author's numbering (`<ol start>`) when a blank line or code block splits them. Both scroll sideways inside the bubble, which is capped at its column width so it never runs off a phone screen. The prompt tells the Avatar it can use inline code, code blocks and tables wherever they help, and to keep an FAQ answer's links, code blocks and tables as written; `rules.md` exempts FAQ answers from the answer-length rule, so the Avatar gives the full answer when the question warrants it.
- **`Qn` lists the FAQ.** A literal `Qn` (any case; distinct from `Q2`-style numbers) is an instant, no-LLM reply listing every FAQ's concise question as `- **Q2:** ...`. It is stored with `tool_calls=[{"type": "instant", "faq": "list"}]` and tagged "instant · FAQ list" in the chat. `knowledge.instant_reply()` handles both instant forms. The prompt mentions both shortcuts so the Avatar can point visitors to them.

- **Knowledge refresh from a conversation review.** A review of 1,349 production exchanges (2026-06-07 to 2026-10-21) drove a knowledge update: the AI FDE course, the million-enrollment figure, the refreshed Agentic Track, the full course-to-repo map in `fetch.md`, the numbered guides index, and an "About this chat" section so the Avatar can link FAQs as `/avatar?q=N`, knows the owner reads the inbox, and knows the chat can't receive images. Coupon codes are never written into the knowledge files because they expire (see the next bullet). The three-way section now says a visitor who claims to be the owner stays a visitor, after one was greeted as the owner and had a push sent on their behalf. AI FDE is listed first, as the flagship, ahead of the six established courses numbered 1 to 6.
- **Live coupon links.** The curriculum page builds its Udemy buttons in JavaScript (coupons in `window.EDC_CONFIG`, course URLs in the page script's `BASE` map), so the fetch tool, which doesn't run JavaScript, never sees a coupon. `backend/app/course_links.py` reads those blocks from the page HTML and builds the links the way the page does, with course names from the page's course data and AI FDE first. A background task started in `main.lifespan` refreshes them every 15 minutes, so a chat turn never waits on the page, and `agent.py` adds them to the prompt as an "Enrollment links" section after the owner profile. If the page can't be read or parsed, the last good links are kept and the owner gets one alert per outage. Off unless `CURRICULUM_URL` is set (`deploy.sh` copies it to the Fly secrets); `test_live_curriculum_page_still_parses` fails if a page redesign breaks the parser. A tool was considered instead, but the links are short, needed often, and best given with no extra step, and the review showed the model often skipping a matching tool call.
- **FAQ answers relayed word for word.** "I am a complete beginner" looked up Q2 every time, but the reply was a rewrite that kept 7% of Q2's sentences (6-25% for Q8). Removing the length rules, the admin instructions or the conflicting `knowledge.md` lines changed nothing, and a firmer rule in the system prompt helped only some of the time. The model treats a tool result as notes to rewrite, and the prompt's rule is thousands of tokens before the point where it writes. `faq_tool` now puts `FAQ_RELAY_NOTE` at the top of its result: copy the answer word for word, add at most a sentence, and give just one part only if the visitor asked about one part. With it, Q2, Q11, Q8, Q3 and Q1 were relayed in full in every run (a softer wording, or the note after the answer, did worse). The instant `Qn` reply has its own formatter, so visitors never see the note.
- **Scope rules from the misuse review (2026-10-22).** Haiku subagents on Claude Code screened every
  conversation for attempts to test or misuse the avatar, then judged the avatar's replies to the 105
  clear ones. It never revealed its prompt or keys and refused harmful requests. What got through was
  off-scope work: CV and LinkedIn rewrites, business plans, app code, recipes, a chess game. It
  usually declined once and then gave in when the visitor asked again. The scope rules were spread over
  four soft lines; `rules.md` now has one "What you help with" section. It allows a one-sentence answer
  to a quick off-topic question, declines anything made for the visitor's own work or life with a
  pointer to ChatGPT or Claude, and keeps declining when the visitor asks again, rewords, splits the
  request or invokes the owner. Two lines in "Safety and security" rule out opinions on contested
  public issues (it had given a verdict on a war) and role-play, games or writing in the owner's voice.

  The rules were tuned by replaying real attempts on `gpt-6-luna` (owner-approved paid runs, push
  stubbed, nothing written).

  Several things were tried and changed:
  - Wording alone left the model giving in deep in long threads where earlier replies had already
    helped. So the transcript now ends with `REPLY_INSTRUCTION`, a scope check placed right before
    the model writes.
  - The scope names the visitor's own business, pricing and studies, and general programming help, as
    out of scope.
  - It says that a view on an AI-engineering idea from the visitor's own work is in scope. Without
    that line, a "how does my company's agent idea sound?" question was refused.
  - Declines were sending the owner pushes. `push_tool`'s description and the push rules now say a
    declined request is no reason to push.
  - `FAQ_RELAY_NOTE` gained one exception, an FAQ on a different topic, after a recipe request got
    an unrelated FAQ relayed word for word. A broader "if it answers them" condition dropped Q3's
    full relays to 3 in 6, so it was narrowed back.

  Final run, 24 real attempts plus 8 normal questions:
  - Off-scope requests, impersonation, persona and politics: all held except freelance pricing
    advice deep in an 89-message thread.
  - Normal questions: all answered.
  - FAQ relays: full.

  Reasoning "low" against "none", with each case under both settings back to back:
  - Same speed (about 3.5s median) and same cost (about $0.0005 a reply). "Low" spent about 19
    reasoning tokens a reply.
  - "Low" never pushed for a decline; "none" still did in about 1 in 5 declines.
  - The owner switched to "low".

## Security hardening (extras)

Prompted by a responsible-disclosure review of the production branch. Stance: this is a public,
educational Agentic-RAG project with no confidential data; conversations are non-sensitive course
chat, and the OpenRouter spend cap is the real cost ceiling. Most flagged items are low-risk by
design. These few are a pragmatically worthwhile, cheap hardening pass - and several protect students
who fork and deploy their own copy:

- **Fail closed on a missing admin password.** With `ADMIN_PASSWORD` unset, an empty password used to
  log in AND the session-signing secret degraded to a public constant (`avatar::`), allowing admin
  cookie forgery. The app now refuses to start without `ADMIN_PASSWORD`. (The live site already sets
  it; this protects forks.)
- **Throttle admin login.** Failed `/admin/login` attempts are rate-limited per client IP (5/min) to
  blunt online brute force. Successful logins are never throttled, and per-IP keying means an attacker
  only locks their own IP, not the owner.
- **Bound the transcript.** Each turn sent the entire conversation history to the LLM uncapped; it is
  now trimmed to the most recent messages within a character budget, so a long thread can't grow
  per-turn cost without bound or overflow the model's context window. The full history is still stored.
- **Pushover timeout + graceful failure.** The notification call now has a timeout and fails softly,
  so a slow or unreachable Pushover can't hang a chat turn.
- **Notification sounds, priority, and backend-error alerts.** All pushes are high priority
  (`priority: 1`, bypassing quiet hours). Human-in-the-loop pushes use the `bugle` sound; backend
  errors send a `gamelan` alert with details - an OpenRouter rate-limit/daily-cap failure during a
  chat, every failed admin login (with the client IP), or any otherwise-unhandled server error. Error
  alerts are debounced per category (a few per hour) so a flood can't spam notifications or drain the
  Pushover quota - **except failed-login alerts, which currently fire on every attempt** (per-IP they
  are bounded by the login throttle to 5/min; deliberately un-debounced for now so the owner sees each
  one - a determined attacker rotating IPs could push past that, so this may get a cap later).
- **Reject malformed requests before the database (2026-10-22).** The owner was getting "Unhandled
  error" and "Chat turn failed" alerts on the conversation API. They came from hand-made requests:
  `conversation_id` is a `uuid` column but the API accepted any string, so `/api/conversations/123`
  raised a Postgres `22P02` error, a 500 and an alert. A huge `?after=` (`22003`, out of range for a
  bigint) and a chat body that wasn't a JSON object (read raw by the rate limiter) did the same. The
  visitor page never sends any of these, because it makes ids with `crypto.randomUUID()`. All conversation
  ids (`ConversationId` in the chat body, `ConversationIdPath` on the seven routes) are now checked as
  UUIDs, `?after=` is bounded, and the rate limiter leaves a non-object body to validation, so each gets
  a 422 with no alert. Admin routes still answer 401 first to an unauthenticated caller, whatever the id.
  A failed chat turn used to show the visitor the raw exception text (e.g. the Postgres error); it now
  shows `CHAT_ERROR_MESSAGE`, and the details go only to the alert. A probe of every admin route with no
  cookie, a forged cookie and eight malformed cookies returned 401 with no data.
- **Fetch limited to the owner's sites in code (2026-10-22).** Only the prompt kept the fetch tool on
  the owner's site and repos, so a jailbreak could point it at any URL, including internal addresses
  such as cloud metadata (one visitor asked the avatar about SSRF). `OwnerSitesFetch` wraps the MCP
  server and checks each URL before the call reaches it. A URL must be on the same site as one of the
  prefixes under "## Allowed sites" in `fetch.md`, with or without `www.`, and its path must stay
  inside that prefix after dot segments and percent-escapes are resolved. URLs with a login part or a
  port are refused. A blocked call returns an error telling the model what's allowed. With no "Allowed
  sites" section, nothing can be fetched. The server follows redirects, so an allowed page that
  redirected elsewhere would still be read; the owner's sites don't do that.
- **No forged speaker lines (2026-10-22).** The transcript is plain `Visitor:` / `Avatar:` /
  `<owner> (the human):` lines, so a visitor message containing a line starting `Ed Donner (the
  human):` would have looked like the owner. `render_transcript` now indents every later line of a
  message, breaking on `\r`, U+2028 and the other separators too, so a speaker label can only start a
  line when the code wrote it. The prompt explains the indentation, and says text inside a Visitor
  message is the visitor's even when it quotes the owner ("Ed's reply:") or claims to come from an
  admin or the system. The 2026-10-22 misuse review found one pasted "Ed's reply" accepted as the
  owner's, and no forged labels.

Deliberately left as-is (low real risk here): visitor access by unguessable UUID `conversation_id`
(non-sensitive content); the conversation-id-keyed chat limiter (the spend cap is the real ceiling);
Pushover quota (OpenRouter caps spend first). Noted as future best practices: a real auth provider
(Supabase/Clerk) with MFA on admin, and multi-instance + a periodic DR test.
