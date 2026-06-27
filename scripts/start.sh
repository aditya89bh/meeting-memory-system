#!/usr/bin/env sh
# Production startup script for the Meeting Memory System API.
#
# Configuration is read from the environment so the same image runs unchanged
# across environments:
#   MEETING_MEMORY_DB       SQLite database path (default /data/meeting-memory.db)
#   MEETING_MEMORY_HOST     bind host (default 0.0.0.0)
#   MEETING_MEMORY_PORT     bind port (default 8000)
#   MEETING_MEMORY_WORKERS  uvicorn worker count (default 1; keep 1 for SQLite)
#   MEETING_MEMORY_LOG_LEVEL  uvicorn log level (default info)
set -eu

HOST="${MEETING_MEMORY_HOST:-0.0.0.0}"
PORT="${MEETING_MEMORY_PORT:-8000}"
WORKERS="${MEETING_MEMORY_WORKERS:-1}"
LOG_LEVEL="${MEETING_MEMORY_LOG_LEVEL:-info}"
DB="${MEETING_MEMORY_DB:-/data/meeting-memory.db}"

export MEETING_MEMORY_DB="${DB}"

# Ensure the database directory exists before the workers start.
DB_DIR="$(dirname "${DB}")"
mkdir -p "${DB_DIR}"

echo "Starting Meeting Memory API on ${HOST}:${PORT} (db=${DB}, workers=${WORKERS})"
exec python -m uvicorn meeting_memory.api.app:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --log-level "${LOG_LEVEL}"
