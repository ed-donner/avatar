#!/usr/bin/env bash
# Build and run the Avatar container on macOS/Linux.
# Stops and removes any existing container, rebuilds the image, then runs it.
set -euo pipefail

IMAGE="avatar"
NAME="avatar"
PORT="8000"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Stopping any existing $NAME container..."
docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "Building image $IMAGE..."
docker build -t "$IMAGE" .

echo "Starting container $NAME..."
docker run -d --name "$NAME" --env-file .env -p "$PORT:$PORT" "$IMAGE"

echo "Avatar is running at http://localhost:$PORT"
