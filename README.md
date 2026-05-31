# Avatar

Interact with a digital version of you

## Introduction

This project is a web application for visitors to the site to interact with a Digital Twin of you. During their interaction, you can personally jump in (via an admin panel) and engage with the visitors direcly.

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
```

`OWNER_NAME` is the name of the person this Digital Twin represents (you). It is shown in the UI - the site header/subtitle, the page title, how the Avatar refers to itself, and on your own messages when you join a conversation from admin (e.g. "Ed Donner - live"). Set it to how you want your name to appear. It is configuration, never hardcoded, so each owner sets their own.

### OpenRouter

The Avatar's LLM calls go through [OpenRouter](https://openrouter.ai). If you already have a key in `.env`, skip this.

1. Go to https://openrouter.ai and sign in (or sign up).
2. Click your avatar (top right) and choose **Keys**, or go straight to https://openrouter.ai/keys.
3. Click **Create Key**, give it a name (e.g. `avatar`), and click **Create**.
4. Copy the key (it starts with `sk-or-v1-`) and add it to `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   ```
5. Add some credit under **Settings > Credits** if your account has none. The Avatar uses `openai/gpt-5.4-nano` (set in `MODEL`), which is very cheap.

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

## Personalize the twin (the `knowledge/` folder)

The twin's knowledge and voice come from a few files in `knowledge/`, read into the system prompt at runtime. Edit these to make the twin yours:

- **`knowledge.md`** - a rich, first-person profile of you (background, work, courses, skills, personal notes). The main "who I am" source.
- **`style.md`** - how the twin should sound: voice and personality, formatting rules, and safety/guardrail rules for answering on the public internet.
- **`faq.jsonl`** - one JSON object per line. Each row has `faq` (number), `question` (the full question), `answer` (the full answer, in markdown), and `query` (a short, precise phrasing used only for routing). The prompt lists the `query` phrasings so the model can match a visitor's question to a number; the FAQ tool and the `Qn` shortcut then return the full original question and answer. Visitors can also type a bare `Qn` (e.g. `Q2`) for an instant answer with no LLM call.
- **`pic.jpg`** - your photo, used for the human avatar; a robotic variant is used for the twin (see `design-system/docs/avatar-generation.md`).

There is no vector database. (Earlier versions used `summary.txt` and a `linkedin.pdf`; these have been replaced by `knowledge.md` and `style.md`.)

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

