# Deployment (fly.io)

How to deploy Avatar to [fly.io](https://fly.io) as a single container, run it in production, and verify it. Nothing here is created automatically — the deployment artifacts live in `scripts/` (see below) and you deploy with `scripts/deploy.sh`.

| | |
|---|---|
| **App** | `avatar-ed` → `https://avatar-ed.fly.dev` |
| **Region** | `sjc` (San Jose) |
| **Machine** | `shared-cpu-2x`, 1 GB RAM |
| **Always-on** | yes — `min_machines_running = 1` |
| **Build** | the existing multi-stage `Dockerfile` (builds the Vite frontend, runs the FastAPI backend, copies `knowledge/`) |

### Why this shape

The app is **IO-bound**: a chat reply is dominated by the OpenRouter LLM, which is streamed back **asynchronously** (SSE), so ~100 concurrent chats are ~100 mostly-idle async tasks relaying tokens — light on CPU. The likelier constraint is **memory** (Python + the Agents SDK + many live connections), so we give 1 GB. `shared-cpu-2x` (vs 1x) buys more consistent CPU on an always-on box for not much money.

**Region:** `us-west-2` is an AWS code (Oregon, where Supabase lives); Fly uses its own regions and has no Pacific-Northwest one, so `sjc` is the closest. Bonus: from `sjc`, the Supabase round-trips that take ~110 ms from a laptop drop to ~15–25 ms, so admin/chat DB calls are actually faster in production.

## 1. Prerequisites

- `flyctl` installed and logged in: `fly auth whoami` should print your email.
- The root `.env` fully populated, including `SESSION_SECRET` (see secrets below). `.env` is **never** baked into the image (`.dockerignore` excludes it); its values become Fly secrets.
- No local Docker needed — `fly deploy` builds on Fly's remote builders.

## 2. Deployment artifacts (in `scripts/`)

Keep the Fly config and deploy script alongside the existing `start_mac.sh` / `stop_mac.sh` etc. Two files to add:

### `scripts/fly.toml`

```toml
# Fly.io config for the Avatar app. Deploy with scripts/deploy.sh.
app = "avatar-ed"
primary_region = "sjc"               # closest Fly region to the Supabase us-west-2 (Oregon) DB

[env]
  PORT = "8000"                      # matches the Dockerfile's uvicorn --port
  COOKIE_SECURE = "1"                # production is HTTPS -> admin session cookie must be Secure

[http_service]
  internal_port = 8000
  force_https = true
  auto_start_machines = true
  auto_stop_machines = "stop"        # stop EXTRA machines when idle...
  min_machines_running = 1           # ...but always keep 1 warm

  [http_service.concurrency]
    type = "connections"             # SSE holds one connection for the whole streamed reply
    soft_limit = 90                  # (only relevant with >1 machine) start another past this
    hard_limit = 150                 # one machine accepts up to this many — set above your peak

  [[http_service.checks]]
    method = "GET"
    path = "/api/config"             # returns 200 with no DB hit — a clean health check
    interval = "15s"
    timeout = "3s"
    grace_period = "10s"

[[vm]]
  size = "shared-cpu-2x"
  memory = "1gb"
```

Note: the `Dockerfile` and build context (`frontend/`, `backend/`, `knowledge/`) are at the **repo root**, but this config lives in `scripts/`. So `deploy.sh` runs from the repo root and passes both `--config scripts/fly.toml` and `--dockerfile Dockerfile` explicitly. For ad-hoc commands (`status`, `logs`, `secrets`), use `-a avatar-ed`; for `deploy`, use `-c scripts/fly.toml`.

Why the concurrency block matters: if omitted, Fly's defaults are low (~20 soft / 25 hard **connections**). Because every chat reply holds a connection open while it streams, a single machine would refuse the ~26th simultaneous user. Raising `hard_limit` to 150 lets one always-on machine comfortably serve the ~100 target; `soft_limit` only does anything once more than one machine exists.

### `scripts/deploy.sh`

```bash
#!/usr/bin/env bash
# Build and deploy Avatar to fly.io: create the app on first run, stage secrets
# from the root .env, then deploy. Run from anywhere; it finds the repo root.
set -euo pipefail

APP="avatar-ed"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

command -v flyctl >/dev/null || { echo "flyctl not found — install it first"; exit 1; }
flyctl auth whoami >/dev/null || { echo "Not logged in — run 'fly auth login'"; exit 1; }

# 1. Create the app on first run (name must be globally unique).
flyctl status -a "$APP" >/dev/null 2>&1 || { echo "Creating $APP..."; flyctl apps create "$APP"; }

# 2. Stage secrets from .env (surrounding quotes stripped). PORT/COOKIE_SECURE are
#    set in fly.toml [env], not here. --stage applies them on the next deploy (one rollout).
KEYS="OPENROUTER_API_KEY MODEL OWNER_NAME ADMIN_PASSWORD PUSHOVER_USER PUSHOVER_TOKEN SUPABASE_URL SUPABASE_KEY SESSION_SECRET"
args=()
for k in $KEYS; do
  v=$(grep -E "^${k}=" .env | head -1 | cut -d= -f2-)
  v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  [ -n "$v" ] && args+=("${k}=${v}")
done
[ ${#args[@]} -gt 0 ] && flyctl secrets set --stage -a "$APP" "${args[@]}"

# 3. Deploy (build context = repo root; start with 1 machine — scale later if needed).
flyctl deploy --config scripts/fly.toml --dockerfile Dockerfile -a "$APP" --ha=false

echo "Deployed: https://${APP}.fly.dev  (admin at /admin)"
```

Make it executable: `chmod +x scripts/deploy.sh`.

## 3. Environment variables / secrets

Set in `scripts/fly.toml` `[env]` (non-sensitive, committed):

| Var | Value | Why |
|---|---|---|
| `PORT` | `8000` | matches the Dockerfile's uvicorn port / `internal_port` |
| `COOKIE_SECURE` | `1` | production is HTTPS, so the admin session cookie must be `Secure` (it defaults off so local http works) |

Set as **Fly secrets** (sensitive, pulled from `.env` by `deploy.sh`):

`OPENROUTER_API_KEY`, `MODEL`, `OWNER_NAME`, `ADMIN_PASSWORD`, `PUSHOVER_USER`, `PUSHOVER_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, `SESSION_SECRET`.

Notes:
- **`SESSION_SECRET`** (now in `.env`) signs the admin session cookie. Setting it explicitly means rotating `ADMIN_PASSWORD` later won't unexpectedly invalidate the session-secret derivation. Use a long random value.
- **`MODEL`** is whatever is in `.env` (currently `openai/gpt-5.4-nano`, the cheap dev/test model). Decide if production should use a stronger model (e.g. `openai/gpt-5.4-mini`) and set it in `.env` before deploying, or update it later with `fly secrets set -a avatar-ed MODEL=openai/gpt-5.4-mini`.
- Secrets can be set/changed any time: `fly secrets set -a avatar-ed KEY=value` (triggers a rolling restart). View names with `fly secrets list -a avatar-ed` (values are never shown).

## 4. Deploy

First time and every subsequent deploy are the same command:

```bash
scripts/deploy.sh
```

It creates the app if needed, stages secrets, and deploys 1 machine to `sjc`. For redundancy / zero-downtime deploys later, run a second machine:

```bash
fly scale count 2 -a avatar-ed     # min_machines_running=1 keeps 1 warm; soft_limit balances across both
```

## 5. Testing (post-deploy smoke)

Run against `https://avatar-ed.fly.dev`. Use `MODEL=openai/gpt-5.4-nano` for cheap test calls if you like, and clean up test data afterwards.

- [ ] `fly status -a avatar-ed` — 1 machine in `sjc`, state `started`, health check **passing**.
- [ ] `curl -s https://avatar-ed.fly.dev/api/config` → `{"owner_name":"..."}` (200).
- [ ] `/` loads the visitor UI (dark + light, desktop + mobile); the rings background and the LinkedIn/YouTube footer render.
- [ ] A normal question streams a reply (real LLM call); `Q2` returns the instant FAQ; `https://avatar-ed.fly.dev/?q=2` opens and immediately answers Q2.
- [ ] FAQ routing works (e.g. ask about a NameError → `faq_tool`), and links in replies are clickable.
- [ ] `/admin` → wrong password rejected; correct `ADMIN_PASSWORD` opens the dashboard; the inbox lists conversations and a thread opens quickly.
- [ ] Post a human message from admin → it appears in the visitor's chat within ~10 s (polling), styled as the "live" bubble.
- [ ] Contact-capture flow ("I'd like to get in touch", give an email) fires a **Pushover** notification.
- [ ] In DevTools, the admin session cookie has the **`Secure`** flag (confirms `COOKIE_SECURE=1`).
- [ ] `fly logs -a avatar-ed` shows no errors during the above.
- [ ] Clean up: delete the test conversation threads from Supabase and any screenshots.

## 6. Success criteria

Deployment is successful when:
- The app is reachable at `https://avatar-ed.fly.dev` with HTTPS forced, ≥1 machine always running in `sjc`, and the health check green.
- All of the visitor, admin (login-gated), three-way human-in-the-loop, `Qn`/`?q=` instant answers, FAQ-tool routing, and Pushover paths work end to end.
- Secrets are configured via Fly (never baked into the image); the admin cookie is `Secure`.
- Logs are clean and the admin "open conversation" feels snappy (DB round-trips are fast from `sjc`).

## 7. Custom domain (recommended next step)

Map a subdomain of your site to the app:

```bash
fly certs add avatar.edwarddonner.com -a avatar-ed   # then add the shown DNS records
```

This is also what makes **iframe embedding** clean: serving the app from `avatar.edwarddonner.com` (same site as `edwarddonner.com`) keeps the "Keep chat" cookie **first-party**, avoiding third-party-cookie blocking. The host page then passes the deep link through to the iframe, e.g. `edwarddonner.com/avatar?q=2` → set the iframe `src` to `https://avatar.edwarddonner.com/?q=2` (server-side in a template/shortcode, or a few lines of JS on the host page) and the embedded app answers Q2 on load. See SPEC.md "Tech stack decisions" for the iframe param-passing notes and the `frame-ancestors` guidance.

## 8. Operations

- Status / logs: `fly status -a avatar-ed`, `fly logs -a avatar-ed`.
- Scale up/out: `fly scale vm shared-cpu-4x -a avatar-ed` (bigger), `fly scale count 2 -a avatar-ed` (more machines).
- Roll back: `fly releases -a avatar-ed` then `fly deploy` a prior image, or `fly releases rollback -a avatar-ed`.
- Secrets change: `fly secrets set -a avatar-ed KEY=value` (rolling restart).
