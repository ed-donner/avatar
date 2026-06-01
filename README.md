# Avatar

Interact with a digital version of you

## Introduction

This project is a web application for visitors to the site to interact with a Digital Twin of you. During their interaction, you can personally jump in (via an admin panel) and engage with the visitors direcly.

Video walk-through: https://youtu.be/srlhW4H-Gtg

> **This is the starting point, not the finished app.** This branch contains the specification ([SPEC.md](SPEC.md)), the design system (`design-system/`), your knowledge files (`knowledge/`), and a backend skeleton - everything Claude Code needs to build the product for you. Open this folder in [Claude Code](https://claude.com/claude-code) and ask it to build the app from `SPEC.md`. The **Setup instructions** and **Personalize the twin** sections below you do now, before (or as part of) building. **Everything after that - running, deploying - only applies once the project has been built.**

## Setup instructions

All secrets live in a single `.env` file in the project root. By the end of this section it should contain:

```
OPENROUTER_API_KEY=sk-or-v1-...
MODEL=openai/gpt-5.4-nano
OWNER_NAME=Ed Donner
ADMIN_PASSWORD=your-chosen-admin-password
PUSHOVER_USER=...
PUSHOVER_TOKEN=...
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=sb_secret_...
SESSION_SECRET=a-long-random-string
COOKIE_SECURE=0
```

`OWNER_NAME` is the name of the person this Digital Twin represents (you). It is shown in the UI - the site header/subtitle, the page title, how the Avatar refers to itself, and on your own messages when you join a conversation from admin (e.g. "Ed Donner - live"). Set it to how you want your name to appear. It is configuration, never hardcoded, so each owner sets their own.

`SESSION_SECRET` signs the admin session cookie. It is optional locally - if unset, it is derived from `ADMIN_PASSWORD` - but set it to a long random value (e.g. run `openssl rand -hex 32`) so that changing your admin password later does not invalidate live admin sessions. `COOKIE_SECURE` gates whether that cookie requires HTTPS: leave it `0` (or unset) for local http; it is set to `1` automatically in production (see [Deploy to fly.io](#deploy-to-flyio)).

### OpenRouter

The Avatar's LLM calls go through [OpenRouter](https://openrouter.ai). If you already have a key in `.env`, skip this.

1. Go to https://openrouter.ai and sign in (or sign up).
2. Click your avatar (top right) and choose **Keys**, or go straight to https://openrouter.ai/keys.
3. Click **Create Key**, give it a name (e.g. `avatar`), and click **Create**.
4. Copy the key (it starts with `sk-or-v1-`) and add it to `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   ```
5. Add some credit under **Settings > Credits** if your account has none. The Avatar uses the model in `MODEL`. `openai/gpt-5.4-nano` is very cheap and good for development and testing; for a live site, consider a stronger model such as `openai/gpt-5.4-mini` (just set `MODEL` accordingly).

### Supabase

Conversations are stored in a single Postgres table in Supabase. Follow these steps exactly.

> Note on keys: Supabase changed its API keys in 2026. The legacy `anon` / `service_role` keys are being retired, and new projects no longer offer them. We use the new **secret key** (format `sb_secret_...`). It is used only by the backend server, never in the browser, so it can safely have full access to the table.

#### 1. Create the project

1. Go to https://supabase.com and sign in (or sign up - the free tier is fine).
2. On the dashboard, click the green **New project** button.
3. Pick your organization, give the project a **Name** (e.g. `avatar`), and set a **Database Password** (you can let it generate one - you will not need it for this app, but save it anyway).
4. Choose a **Region** close to you.
5. You will see three checkboxes on the create form. Set them as follows:
   - **Enable Data API** - leave this **ON** (checked). The backend reaches the table through this API; if it is off, nothing works.
   - **Automatically expose new tables** - you can leave this on, or turn it **OFF** for tighter manual control (recommended; it is becoming the default). The SQL below adds an explicit grant for our table, so it works either way.
   - **Enable automatic RLS** - leave this **OFF** (unchecked, the default). Only the backend touches the database, using the secret key, which bypasses Row Level Security; the backend enforces admin access itself.
6. Click **Create new project** and wait about a minute for it to finish provisioning before continuing.

#### 2. Create the table

1. In the left sidebar, click the **SQL Editor** icon (looks like `>_`).
2. Click **+ New snippet** (top left of the editor).
3. Paste in the SQL below, then click **Run** (bottom right, or press Cmd/Ctrl+Enter):

   ```sql
   create table public.messages (
     id              bigint generated always as identity primary key,
     conversation_id uuid not null,
     conversation_name text,
     role            text not null check (role in ('visitor', 'avatar', 'human')),
     content         text not null,
     tool_calls      jsonb,
     needs_attention boolean not null default false,
     read            boolean not null default false,
     created_at      timestamptz not null default now()
   );

   create index messages_conversation_id_idx on public.messages (conversation_id);
   create index messages_created_at_idx on public.messages (created_at desc);

   -- Give the backend's secret key (service_role) access to the table.
   -- Required if you disabled "Automatically expose new tables"; harmless otherwise.
   grant select, insert, update, delete on public.messages to service_role;
   ```

4. When you click **Run**, Supabase shows a warning: *"This query creates a table without enabling Row Level Security..."* with two buttons. Click **Run without RLS** (the yellow one), NOT "Run and enable RLS". This is **expected and safe for this app**: we deliberately do not use RLS, because the table is only ever accessed by the backend's secret key, and the anon/publishable key is never used anywhere in this project, so there is no client that could reach the table. (If you do click "Run and enable RLS" by mistake, it still works - the secret key bypasses RLS - but "Run without RLS" is the intended choice.)

5. You should see **Success. No rows returned**. The table is now created.

   What the columns are for:
   - `conversation_id` - the unique id assigned to each visitor's chat
   - `conversation_name` - optional friendly name for the conversation
   - `role` - who sent the message: `visitor`, `avatar`, or `human` (you)
   - `content` - the message text
   - `tool_calls` - records any tools the Avatar used (for future expansion)
   - `needs_attention` - set when the Avatar pushes you a notification; cleared when you read it
   - `read` - whether you (the human) have read this message in the admin panel
   - `created_at` - timestamp

#### 3. Get the Project URL

1. In the left sidebar, click **Settings** (the gear icon at the bottom).
2. Click **Data API**.
3. Find the **API URL** (it may show as `https://your-project-ref.supabase.co/rest/v1/`). Copy only the **base** part, WITHOUT the trailing `/rest/v1/` - the client adds that itself. Add it to `.env`:
   ```
   SUPABASE_URL=https://your-project-ref.supabase.co
   ```
   For example, if Supabase shows `https://vsdbgmlilyduqkybcltg.supabase.co/rest/v1/`, you would use `https://vsdbgmlilyduqkybcltg.supabase.co`.

#### 4. Get the secret key

1. Still in **Settings**, click **API Keys**.
2. Make sure you are on the **API Keys** tab (NOT the "Legacy anon, service_role API keys" tab - we do not use those).
3. Under **Secret keys**, there is a default secret key. Click **Reveal** (or create one with **Create new secret key** if none exists), then copy the value (it starts with `sb_secret_`).
4. Add it to `.env`:
   ```
   SUPABASE_KEY=sb_secret_...
   ```

> Keep the secret key private. It has full access to your database and must only ever live in `.env` on the server - never commit it and never use it in the frontend.

That's it - once all the values above are in `.env`, the setup is complete.

### Validate the setup

Before running the app, confirm Supabase is reachable and writable with the connectivity test:

```
cd backend && uv run pytest tests/test_supabase_connection.py -v
```

All tests must pass. They check that `SUPABASE_URL` / `SUPABASE_KEY` are present and correctly formatted, that the `messages` table is reachable through the Data API, and that a row can be inserted and deleted (with the expected columns, including `needs_attention`, `read`, and `tool_calls`). If a test fails, re-check the table SQL and the URL/key steps above.

## Personalize the twin (the `knowledge/` folder)

The twin's knowledge and voice come from a few files in `knowledge/`, read into the system prompt at runtime. Edit these to make the twin yours:

- **`knowledge.md`** - a rich, first-person profile of you (background, work, courses, skills, personal notes). The main "who I am" source.
- **`style.md`** - how the twin should sound: voice and personality, formatting rules, and safety/guardrail rules for answering on the public internet.
- **`faq.jsonl`** - one JSON object per line. Each row has `faq` (number), `question` (the full question), `answer` (the full answer, in markdown), and `query` (a short, precise phrasing used only for routing). The prompt lists the `query` phrasings so the model can match a visitor's question to a number; the FAQ tool and the `Qn` shortcut then return the full original question and answer. Visitors can also type a bare `Qn` (e.g. `Q2`) for an instant answer with no LLM call, and a deep link like `…/?q=2` opens the chat and immediately asks Q2 (handy for sharing a direct answer or embedding).
- **`pic.jpg`** - your photo, used for the human avatar; a robotic variant is used for the twin (see `design-system/docs/avatar-generation.md`).

There is no vector database. (Earlier versions used `summary.txt` and a `linkedin.pdf`; these have been replaced by `knowledge.md` and `style.md`.)

A couple of owner-specific bits live in the frontend rather than `.env`: the **footer social links** in `frontend/index.html` point to the owner's LinkedIn and YouTube (update them to your own), and the avatar images in `frontend/public/` are generated from `pic.jpg` (see `design-system/docs/avatar-generation.md`). The background texture can also be swapped (rings / crosses / grid) via the `--grid-mark` token in `frontend/src/styles/tokens.css` — see `design-system/docs/background-texture.md`. The brand subtitle and any owner-specific copy are currently set for the default owner, so review those too when making the twin your own.

## Running the app

### Docker (recommended)

The app builds and runs as a single container. From the project root:

- macOS / Linux: `./scripts/start_mac.sh` to build and run, `./scripts/stop_mac.sh` to stop.
- Windows: `./scripts/start_pc.ps1` to build and run, `./scripts/stop_pc.ps1` to stop.

The start script stops any existing `avatar` container, rebuilds the image, and runs it with your root `.env`. When it finishes, open http://localhost:8000 (admin at http://localhost:8000/admin). Docker must be running.

### Local development

Run the backend and frontend in two terminals.

Backend (FastAPI on port 8000):

```
cd backend
uv run uvicorn app.main:app --reload --app-dir .
```

Frontend (Vite dev server):

```
cd frontend
npm install
npm run dev
```

Open the URL Vite prints. The Vite dev server proxies `/api` to the backend on http://localhost:8000, so run the backend alongside it. The visitor page (`/`) gets hot reload from Vite; `/admin` is proxied to the backend, so to preview admin changes, build the frontend (`npm run build`) and load `http://localhost:8000/admin` from the backend.

The visitor chat and the admin dashboard are both responsive (mobile and desktop, dark and light).

## Deploy to fly.io

The same single container deploys to [fly.io](https://fly.io). The full guide - the `scripts/fly.toml` config, the `scripts/deploy.sh` script, secrets, custom domains, and a post-deploy smoke-test checklist - is in **[DEPLOY.md](DEPLOY.md)**. In short:

1. Install `flyctl` and log in (`fly auth login`; `fly auth whoami` should print your email).
2. Make sure `.env` is fully populated, including `SESSION_SECRET`. Its values become Fly secrets (pulled in by `deploy.sh`) and are never baked into the image.
3. Pick your own globally-unique Fly app name and a region near your Supabase database, then set them in `scripts/deploy.sh` (`APP=...`) and `scripts/fly.toml` (`app`, `primary_region`). The reference deployment uses `avatar-ed` in `sjc`.
4. Run `scripts/deploy.sh`. It creates the app on first run, stages the secrets, and deploys one always-on machine with `COOKIE_SECURE=1` (so the admin cookie is `Secure` over HTTPS).
5. The app is then live at `https://<your-app>.fly.dev` (admin at `/admin`).

Putting the app on your own website is **optional** - the `https://<your-app>.fly.dev` URL works on its own. If you do want it on a subdomain of your site (which also keeps the "Keep chat" cookie first-party when embedding via an `<iframe>`), see the custom-domain section of [DEPLOY.md](DEPLOY.md), and `scripts/wordpress-embed.html` for a paste-ready embed snippet.

## Built-in protections

The backend guards your API key automatically, with no configuration: visitor messages longer than 20,000 characters are truncated (with a short note appended) before being stored or sent to the model, and more than 20 messages per minute from a single conversation are rejected (HTTP 429, with a friendly slow-down message in the chat) before any model call is made.

