#!/usr/bin/env bash
# Stop and remove the Avatar container on macOS/Linux.
set -euo pipefail

NAME="avatar"

echo "Stopping and removing $NAME container..."
docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "Avatar stopped."
