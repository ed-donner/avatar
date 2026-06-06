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
  and cheap per the spec). Run locally:
  `uv run --directory backend uvicorn app.main:app --reload --app-dir .`
- Frontend: `cd frontend && npm run build` (runs `tsc` then `vite build`; type errors fail the build).
- Container: `./scripts/start_mac.sh` (build + run). If host `:8000` is busy, run on another port,
  e.g. `docker run -d --name avatar --env-file .env -p 8001:8000 avatar`.
- The web-fetch tool needs `mcp-server-fetch` on PATH locally: `uv tool install mcp-server-fetch`.

## Guardrails

- The single Supabase database is PRODUCTION (shared by local dev, the tests, and the live site).
  Only ever create/delete throwaway rows you own, and clean them up. Inspect before any bulk delete.
- Do not deploy - the owner deploys via `scripts/deploy.sh`; use local Docker only for testing.
