#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Nexus — launch the full dev stack:
#   Daphne (ASGI: REST + WebSockets) :8000, Celery worker, Nuxt dev :3000
# Logs go to ./logs/*.log. Ctrl+C stops everything.
# Usage: ./scripts/start_dev.sh [--no-frontend]
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

NO_FRONTEND=0
[ "${1:-}" = "--no-frontend" ] && NO_FRONTEND=1

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Missing .venv — run ./scripts/setup_environment.sh first" >&2; exit 1; }

if docker info >/dev/null 2>&1; then
  docker compose up -d >/dev/null
fi

PIDS=()
cleanup() {
  echo
  echo "Shutting down Nexus dev stack..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

(cd backend && "$PY" manage.py migrate --noinput >/dev/null)

echo "--> Daphne (backend) on http://localhost:8000   [logs/backend.log]"
(cd backend && exec "$PY" -m daphne -b 0.0.0.0 -p 8000 nexus_backend.asgi:application) >logs/backend.log 2>&1 &
PIDS+=($!)

echo "--> Celery worker                                [logs/celery.log]"
(cd backend && exec "$PY" -m celery -A engine.celery_app worker -Q "${NEXUS_CELERY_QUEUE:-nexus}" --loglevel=INFO --concurrency=2 --pool=threads) >logs/celery.log 2>&1 &
PIDS+=($!)

if [ "$NO_FRONTEND" -eq 0 ]; then
  echo "--> Nuxt (frontend) on http://localhost:3000     [logs/frontend.log]"
  (cd frontend && exec npm run dev -- --port 3000) >logs/frontend.log 2>&1 &
  PIDS+=($!)
fi

echo
echo "Nexus is starting. Press Ctrl+C to stop."
wait
