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

After the phased build (Phases 0-9), two refinements were made to the system prompt:

- **`rules.md` split + heading convention.** The owner knowledge in `knowledge/` is now three files, each with one job: `knowledge.md` (facts about the owner, incl. the jobs/courses guidance and course-resource links), `style.md` (the owner's unique voice and formatting), and `rules.md` (owner-agnostic operating rules: safety, escalation, answer length). Every knowledge file starts its headings at `##` so they nest under the prompt's `#` sections, keeping the assembled prompt's hierarchy consistent.
- **Hard output cap + cache-friendly ordering.** `build_agent` sets `ModelSettings(max_tokens=2000)` as a hard per-reply ceiling (with a graceful "kept it brief" note appended on the rare truncation, detected via the last response's own token usage). The admin's additional-instructions block is placed LAST in the system prompt: prompt caching is prefix-based, so the editable, per-turn block sits after the long static prefix it would otherwise invalidate (and gains recency emphasis).

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

Deliberately left as-is (low real risk here): visitor access by unguessable UUID `conversation_id`
(non-sensitive content); the conversation-id-keyed chat limiter (the spend cap is the real ceiling);
Pushover quota (OpenRouter caps spend first). Noted as future best practices: a real auth provider
(Supabase/Clerk) with MFA on admin, and multi-instance + a periodic DR test.
