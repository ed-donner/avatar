# Avatar - Spec

## Introduction

Avatar is a new version of an online Digital Twin, with a twist.

It's a web application that allows visitors to a website to interact with a Digital Twin Avatar based on the human that runs the site.

The avatar is implemented using OpenAI Agents SDK, with tools to look up proprietary knowledge.

There's an added dimension: the human (who the twin is representing) can themselves join any of the conversations and weigh in. The conversations are 3-way: between the visitor, the Avatar, and the human.

## User Experiences

### The Interactive Chat Experience

A visitor comes to the web app. They are presented with a modern, sharp, fresh Avatar web app. At the top there is an optional field for them to enter their first name or initials. There's also a switch "Keep chat" that defaults to on.

The browser assigns a unique conversation_id to this chat. If the Keep chat is on, the browser checks cookies to see if this browser has used a unique conversation_id in the past, in which case it uses that (and also calls the server to obtain the chat so far).

There's also a Reset chat button, that clears the chat and assigns a new conversation_id.

The chat is presented as an instant message experience, but more refined that your typical Chatbot screen. The users message have their initials in a bubble. Responding to the user is either the digital twin, or in some cases the human may respond in addition to the Avatar.

The visitor chat is fully responsive and works great on mobile as well as desktop, in both dark and light mode. The intro screen offers a few example prompts; clicking one submits it immediately. Typing a bare `Qn` (e.g. `Q2`) is an instant-answer shortcut that returns that FAQ with no LLM call; the reply restates the question before the answer (e.g. "**Q2:** ...the question... / ...the answer..."). A deep link `?q=N` (e.g. `/?q=2`) opens the page and immediately submits that `Qn`, so a single shared link can answer a specific question on arrival; the parameter is then cleared from the URL.

### The Human Admin Experience

The human (the owner of this app) can bring up a browser at /admin and enter a password. They are then presented with a dashboard. The left hand sidebar contains a list of conversations (like an email inbox). Most recent on top. They are shown as initials, timestamp, and the beginning of what they said.

When the human clicks on a message in the left hand side bar, the main panel shows the complete interaction with that user and the avatar (and possibly the human). The human can choose to add a message.

It's clear in the Sidebar which messages haven't been read yet. If a message needs the Human's involvement (because the Push tool was used to notify the human) then this is clearly identified (until the human has read the message). Arrow keys can be used to efficiently move up and down the messages, and Enter sends a message (Shift+Enter for a multi-line message).

The admin dashboard is also usable on mobile, as a master/detail flow: the inbox fills the screen, tapping a conversation opens its full thread (scrolled to the latest message) with a back control to return to the inbox. The desktop side-by-side layout is unchanged.

## Implementation Decisions

- The conversations should be stored in a Supabase database, with conversation_id, timestamp, conversation_name (optional), role, content, and anything to track tool use (future expansion)
- The admin password to use is the environment variable ADMIN_PASSWORD. The backend should have security to ensure that only an authorized user can access other conversations
- The LLM call should use OpenAI Agents SDK. The instructions should explain the full situation. The user prompt (task) should summarize the full conversation so far (i.e. 1 user prompt to handle all roles, rather than user/assistant, because of the human)
- The frontend should poll the backend every 10 seconds for any updates from the human (slowing down to every minute after 5 mins have passed with no activity)
- There is an OpenRouter API key in the .env file. The model is read from `MODEL` in `.env`. `openai/gpt-5.4-nano` is the cheap default for development and testing (also the code default in `config.py`); the reference production deployment uses `openai/gpt-5.4-mini`. Each owner sets their own `MODEL` (an OpenRouter `openai/...` identifier; see Q&A #2).
- Conversation reads use a single Supabase round-trip. Opening a thread in admin marks every row read, clears the needs-attention flag, and returns the updated rows in one PostgREST "update ... returning" call; the public conversation fetch derives the conversation name from the rows it already loaded (no extra query). The `messages` table is indexed on `conversation_id` and `created_at` (see the README), keeping these reads fast as volume grows.
- Abuse guards protect the API key (no configuration). Visitor input is clamped: a message longer than 20,000 characters is truncated to 20,000 and the note `[...message truncated as it's too long; ask the visitor to send something more concise]` is appended; the clamped text is what is stored AND what is sent to the LLM.
- Each `conversation_id` is rate-limited to 20 chat messages per minute (a moving-window limiter from the `limits` package, held in memory per process). Excess requests return HTTP 429 *before* any LLM call; the frontend shows a friendly "you're sending messages too quickly" message. In-memory state is sufficient because OpenRouter caps overall spend and a browser's requests stick to one machine. (See Q&A #12.)

### Use of OpenAI Agents SDK

Be absolutely sure to use current, idiomatic treatment of OpenAI Agents SDK. Use their recommended strategy for using OpenRouter instead of OpenAI, per their documentation. Always use idiomatic approaches.

### Tech stack decisions

- The frontend should be an HTML/TS/Vite static site in frontend/
- The backend should be FastAPI with a uv project in a folder backend/ and it should serve the static UI in / and /admin
- The platform should be build as a single Docker container. There should be a scripts/ folder that has a start_mac.sh and stop_mac.sh and start_pc.ps1 and stop_pc.ps1. The start scripts should stop the Docker container if running, then rebuild.
- The platform is deployed to fly.io as the single container the Dockerfile and `scripts/` build and run; the mechanics (app, region, secrets, custom domain, smoke tests) are documented in `DEPLOY.md`, driven by `scripts/fly.toml` and `scripts/deploy.sh`. The reference deployment runs as app `avatar-ed` in region `sjc` (the closest Fly region to its Supabase DB) - each owner picks their own globally-unique app name and a region near their own Supabase. Notes for embedding it in an existing site (e.g. a WordPress page) via an `<iframe>`:
  - The visitor page reads `?q=N` from its own URL, so the iframe's `src` can carry it. The host page copies its own `?q=` onto the iframe (server-side in a template/shortcode, or a few lines of JS) so that, e.g., `yourdomain.com/avatar?q=2` answers Q2 inside the iframe. A ready-to-paste embed snippet ships at `scripts/wordpress-embed.html` (full-bleed below the site nav, a content-column max-width override, an overflow-x guard, and the `?q=` passthrough); set its `BASE` constant to your app's subdomain and the iframe `title` to your own name.
  - The app sets no `X-Frame-Options`/CSP, so it can be framed. If security headers are added later, prefer `Content-Security-Policy: frame-ancestors <host>` over `X-Frame-Options: DENY`.
  - "Keep chat" relies on a `SameSite=Lax` cookie, which a browser treats as third-party inside a cross-site iframe (so persistence may not stick). To keep cookies first-party, serve the app from a subdomain of the host (e.g. `avatar.example.com`) via a fly.io custom domain and embed that. Map the subdomain with a **CNAME** to the Fly hashed target (e.g. `<hash>.<app>.fly.dev`), not A/AAAA records: the app's IPv4 is a *shared* Fly address and a CNAME auto-tracks Fly IP changes. Let's Encrypt then issues the cert. If the host domain is behind a Cloudflare proxy, the record must be DNS-only (grey cloud) plus a `_fly-ownership` TXT record. See `DEPLOY.md`.
- The folder `knowledge/` holds the owner knowledge factored into the system prompt: `knowledge.md` (a rich first-person profile), `style.md` (voice, formatting and safety rules), `faq.jsonl` (the numbered FAQ — each row has a concise `query` for routing plus the full original `question` and `answer`), and `pic.jpg` (the owner photo used for the avatars)

### The Reference Files

There are 3 reference files in the reference directory with code examples that you should use:  
1. context.py contains a prompt from a prior Digital Twin. This should be a useful inspiration. But the prompts for the new Avatar will need to be more sophisticated as its a multi-way conversation.
2. next_level.ipynb is a Jupyter Notebook with code to (a) make use of the json FAQ file for quick answers (b) support a shortcut way to ask for a question just by typing "Q2" that doesn't require an LLM call (c) streaming back, including the tool usage. I've not included the CSS but it showed tool use in a small font.
3. push.py shows how to make another tool which will call PushOver to send the Human a notification. This should be used if the visitor wants to get in touch or asks a question that needs a human involvement. If the Avatar can't answer a question, it should use the tool to tell the human and mention in the chat that it's done that.

## UI

The platform must look great in dark mode and light mode.
The palette is:
- Accent Yellow: `#ecad0a` - accent lines, highlights
- Blue Primary: `#209dd7` - links, key sections
- Purple Secondary: `#753991` - submit buttons, important actions
- Dark Navy: `#032147` - main headings
- Gray Text: `#888888` - supporting text, labels

IMPORTANT: Do not have classic LLM tells like gradients, overuse of purple, and the line on the left of panels.
Do not have a standard Chatbot style.
The look must be sharp, compelling, exciting, modern.
Vector symbols are great where useful; but strictly no emojis.

Both the visitor chat and the admin dashboard must look and work great on mobile as well as desktop (responsive layouts), in dark and light mode.

Ensure that the chat message field takes focus for the user when they bring up the page, and that it regains focus after sending a message (by clicking or by hitting enter).

The image in knowledge/pic.jpg should be used for the Avatar icon for the Human, and a robotic version of it should be used as the Avatar icon for the Avatar, looking like a Digital Twin of the human.

## Design System

A complete, build-ready visual and interaction system has been provided in the `design-system/` directory (produced by the sister product Claude Design). It pairs with this SPEC. The split is explicit: **SPEC.md governs behaviour and the backend; `design-system/` governs look and feel.** When the two disagree, SPEC wins on behaviour, the design system wins on appearance.

### Structure of `design-system/`

- **`Avatar Design System.html`** - the navigable design-system document (it dogfoods its own tokens). Open this rendered first.
- **`SKILL.md`** - the front-end build brief: how to turn the system into the real product UI, plus an acceptance checklist.
- **`README.md`** - overview and contents table.
- **`tokens.css`** - single source of truth: brand palette, type scale, spacing, radii, motion, and full **dark** (the hero) and **light** themes, switched via `[data-theme="dark"|"light"]` on `<html>`. Role colours are baked in: visitor = blue, avatar (twin) = cyan, human = yellow.
- **`components.css`** - build-ready component classes shared by the mockups and the doc: buttons, fields, the Keep-chat switch, badges, the three message bubbles, tool-status lines, the `Qn` instant-tag, the composer, inbox rows, and avatars. Depends on `tokens.css`.
- **`icons.svg`** - icon sprite, used as `<use href="icons.svg#i-...">`; icons inherit `currentColor`.
- **`doc.css`** - styles for the doc page only (NOT product code).
- **`assets/`** - `avatar-human.png` (the owner's real photo), `avatar-robot.png` (synthetic twin, square with HUD frame), `avatar-robot-round.png` (twin tuned for circular chat avatars).
- **`mockups/`** - hi-fi reference screens `Visitor Chat.html` and `Admin Dashboard.html` (both with a dark/light toggle). These are the literal build targets.
- **`docs/`** - `ux-flows.md` (every interaction contract plus a states matrix to design and test against), `components.md` (component-by-component class reference), `avatar-generation.md` (the recipe to produce the twin image from the owner's photo).

### Design language

Dark-first, navy-tinted surfaces; editorial serif **Newsreader** (display) + crisp grotesque **Hanken Grotesk** (UI) + **JetBrains Mono** (technical layer); **blue-led** identity with **yellow as the "spark" reserved for the human-in-the-loop**, and **purple locked to primary actions only**. No gradients in chrome, no purple wash, no left-edge accent bars, no emoji. This matches the SPEC palette and the "not a generic chatbot" mandate.

### How to use it in the build

The frontend is vanilla TypeScript + Vite (per SPEC). Copy `tokens.css`, `components.css`, `icons.svg` and `assets/` into the frontend; load order is `tokens.css` -> `components.css` -> page CSS; import the Google Fonts (Newsreader, Hanken Grotesk, JetBrains Mono). Build the two screens by composing the component classes and lifting the markup from the mockups, which are the tie-breaker for any ambiguity. Default theme is dark, persisted (the mockups use `localStorage['avatar-theme']`). Do not invent new colours - derive from tokens.

### Notes

- The design system says "no left-edge accent bars," yet `.convo-item.is-active::before` in `components.css` draws a small left bar on the *active admin inbox row*. This is acceptable: that rule is about message/content panels (and is honoured on the human bubble); the inbox bar is a selection indicator. Follow the mockups.
- Treat the shipped PNGs in `assets/` as the source of truth for the avatar images rather than re-deriving them. The `avatar-robot*.png` files resolve the earlier open question about providing the robotic icon.
- **Owner-specific regeneration:** these assets, copy, and identity are currently built for the default owner (Ed). If someone *other than Ed* stands up their own site, the build must be updated end to end for that person - including regenerating the Avatar images from their own `knowledge/pic.jpg` (per the recipe in `design-system/docs/avatar-generation.md`), and updating the human photo, brand subtitle, and any owner-specific copy. The owner's name comes from the `OWNER_NAME` env var and is shown in the UI (including the human bubble, e.g. "Ed Donner - live"); it must always be read from that config and never hardcoded (per Q&A #4 and #11).

## Testing

Testing is absolutely crucial for the success of this project.

1. Test the backend thoroughly with comprehensive unit tests, including tests to ensure that admin api routes are only available if logged in
2. Rigorously test the frontend. Use Playwright, take multiple screenshots. Ensure everything works in significant detail.
3. Build the Docker container and test everything end to end; very comprehensively

You should write comprehensive test plans for each of these, document the test plans in the test/ directory with checkboxes, and then check them off.

NOTE: It's good to use the model and pushover as part of your testing, but change the model to gpt-5.4-nano to reduce costs. Then it's fine to call the LLM for tests and to write test conversations in the Supabase database. There are sensible rate limits on the OpenRouter key; you can use it as much as you wish.

When you've completed testing, delete the screenshots and delete the test conversation threads in Supabase, and check off the items in your test plans.

## Setup and Validation

Before running or developing the app, the environment must be set up and validated:

1. **Follow the README setup instructions.** Anyone standing up their own site (their own Digital Twin) must follow the "Setup instructions" section in `README.md`. This covers obtaining an OpenRouter API key, creating the Supabase project and `messages` table, and putting all required keys into `.env` (`OPENROUTER_API_KEY`, `MODEL`, `OWNER_NAME`, `ADMIN_PASSWORD`, `PUSHOVER_USER`, `PUSHOVER_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`), plus the optional `SESSION_SECRET` (signs the admin session cookie; defaults to `avatar::<ADMIN_PASSWORD>` if unset, so set an explicit value for production) and `COOKIE_SECURE` (set to `1` in production so the session cookie is `Secure` over HTTPS; unset/0 for local http).

2. **Run the connectivity test to validate.** After the README steps are complete, run the Supabase connectivity test to confirm the credentials work and the `messages` table is reachable and writable:

   ```
   cd backend && uv run pytest tests/test_supabase_connection.py -v
   ```

   All tests must pass before proceeding. This validates that the `.env` values are correct and that the Data API, table, and grants are configured as expected.

## Success Criteria

The project is only successful when you can run the script to build the container, then run the application end-to-end, carry out full testing with the user, avatar and human participating (and multiple users with different conversation_ids). The tests should include multiple screenshots. The tests should be fully documented in the test/ folder. Only conclude the project when your extensive testing is completed and working well and looking great.

## Questions and Answers

Clarifications agreed before starting work:

1. **Supabase credentials.** Not yet in `.env`. Setting up the Supabase project (and adding `SUPABASE_URL` + service key) is the first task we do together, before building.

2. **Model.** The model name is read from the `MODEL` env var (OpenRouter `openai/...` prefix). `openai/gpt-5.4-nano` is the cheap default for development and testing (and the code default in `config.py`); the reference production deployment uses `openai/gpt-5.4-mini`. Each owner sets their own.

3. **Knowledge / RAG.** No vector DB. The system prompt is composed from `knowledge/knowledge.md` (a rich first-person profile of the owner) and `knowledge/style.md` (the owner's voice plus formatting and safety rules), together with the numbered `faq.jsonl`. Each FAQ row carries a concise `query` (these short phrasings are listed in the prompt so the model can route a visitor's question to a number) alongside the full original `question` and `answer`; both the `faq_tool` and the `Qn` instant-answer shortcut return the full original question and answer. (Earlier drafts inlined `summary.txt` and text extracted from `linkedin.pdf`; those have been superseded by `knowledge.md` + `style.md` and removed, and the `pypdf` dependency with them.)

4. **Human-in-the-loop semantics.** When the human posts from admin, the Avatar does NOT react to it. The human's message is inserted into the thread; the full conversation (including it) is provided to the Avatar the next time the visitor submits something. To the visitor, the human's message renders as a separate bubble using the profile pic, distinguished by image + yellow ring + tint + glow (per the design system).

   **Owner name (updated).** The owner's name comes from the `OWNER_NAME` env var (see #11) and IS shown in the UI, including on the human's bubble (e.g. "Ed Donner - live") to avoid an awkward anonymous bubble. The name must always be read from `OWNER_NAME` config and NEVER hardcoded, so students building their own site simply set their own value.

5. **Needs-human + read/unread state.** Persist these as fields on each message row in the conversation table: a `needs_attention` flag (set when `push_tool` fires) and an unread / read marker. Both cleared/updated when the human opens the thread in admin.

6. **Admin auth.** `POST /admin/login` with `ADMIN_PASSWORD` returns a signed session token (httpOnly cookie) guarding all `/admin/*` APIs. Visitors stay anonymous, addressed only by an unguessable `conversation_id` UUID held in their cookie (possession of the id = access to that thread).

7. **Avatar's robotic icon.** The human will provide the robotic version of `pic.jpg` separately. `pic.jpg` is the human icon; the robotic image is the Avatar icon.

8. **Frontend.** Vanilla TypeScript with Vite — no React/Vue framework.

9. **Streaming vs polling.** Stream the Avatar's reply to the active visitor via SSE (showing tool use in small font). The 10s/60s poll is only for picking up the human's async messages.

10. **Contact capture.** Keep the behavior from `context.py`: when a visitor wants to get in touch, the twin asks for their email and pushes it to the human via Pushover.

11. **Owner name configuration.** `OWNER_NAME` in `.env` holds the name of the person the twin represents. It is shown in the site header/subtitle, the page title, how the Avatar refers to itself, and on the human's messages when the owner joins from admin (e.g. "Ed Donner - live"). Always sourced from config, never hardcoded - each owner sets their own.

12. **Abuse guards.** Two cheap protections for the OpenRouter key are enforced in the backend, with no configuration: (a) a visitor message longer than 20,000 characters is truncated to 20,000 and a note is appended before it is stored or sent to the LLM; (b) each `conversation_id` is limited to 20 chat messages per minute (a moving-window limiter from the `limits` package, in-memory per process), returning HTTP 429 before any LLM call. No overall/global limit is added because OpenRouter already caps total spend.