# Avatar - single multi-stage container.
# Stage 1 builds the Vite frontend; stage 2 runs the FastAPI backend that serves it.

# --- Stage 1: build the frontend ---
FROM node:24-slim AS frontend

WORKDIR /build

# Install dependencies first for better layer caching.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build the static site into /build/dist.
COPY frontend/ ./
RUN npm run build

# --- Stage 2: runtime ---
FROM python:3.12-slim AS runtime

# uv as the Python package manager (latest).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Pre-install the web-fetch MCP server onto PATH so the first chat doesn't pay a
# download (the agent launches it per turn as `mcp-server-fetch`; see app/agent.py).
RUN UV_TOOL_BIN_DIR=/usr/local/bin uv tool install mcp-server-fetch

WORKDIR /app

# Install backend dependencies first (cached unless lockfile changes).
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --frozen --no-dev

# Application code.
COPY backend/ ./backend/

# Built frontend and knowledge assets.
COPY --from=frontend /build/dist ./frontend/dist
COPY knowledge/ ./knowledge/

ENV FRONTEND_DIST=/app/frontend/dist \
    KNOWLEDGE_DIR=/app/knowledge \
    PORT=8000

EXPOSE 8000

# app.main:app with the backend dir as the import root.
CMD ["uv", "run", "--project", "backend", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
