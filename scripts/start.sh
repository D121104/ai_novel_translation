#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for command in docker uv npm; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command '$command' was not found in PATH." >&2
        exit 1
    fi
done

if [[ ! -f "$ROOT/.env" ]]; then
    echo "Warning: no .env file found. Copy .env.example to .env before translating." >&2
fi

echo "Starting PostgreSQL, Neo4j, Qdrant, Redis, and MinIO..."
docker compose up -d

pids=()

cleanup() {
    trap - EXIT INT TERM
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}

trap cleanup EXIT INT TERM

uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 &
pids+=("$!")

uv run celery -A src.workers.celery_app:celery_app worker --loglevel=INFO --concurrency=1 &
pids+=("$!")

(
    cd "$ROOT/frontend"
    npm run dev -- --host 0.0.0.0
) &
pids+=("$!")

echo "Project started."
echo "Frontend: http://localhost:5173"
echo "API:      http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop API, worker, and frontend."
echo "The external LLM service must be running separately."

while true; do
    for pid in "${pids[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid"
            exit $?
        fi
    done
    sleep 1
done
