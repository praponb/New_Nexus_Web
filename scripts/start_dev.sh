#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Nexus — launch the full dev stack:
#   Daphne (ASGI: REST + WebSockets) :8000, Celery worker, Nuxt dev :3000
# Logs go to ./logs/*.log. Ctrl+C stops everything.
# Refuses to start while :8000/:3000 or a Nexus Celery worker are still in use (a stale stack
# would keep serving old code), and stops the stack if any service exits.
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

# --- preflight: a half-dead earlier stack must not shadow this one ----------------------
listener() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1 || true; }
busy=0
PORTS="8000"
[ "$NO_FRONTEND" -eq 0 ] && PORTS="8000 3000"
for port in $PORTS; do
  pid="$(listener "$port")"
  if [ -n "$pid" ]; then
    echo "Port $port is already in use by pid $pid: $(ps -o command= -p "$pid" | cut -c1-100)" >&2
    busy=1
  fi
done
workers="$(pgrep -f "celery -A engine.celery_app worker" || true)"
if [ -n "$workers" ]; then
  echo "A Nexus Celery worker is already running (pid $(echo $workers | tr ' ' ',')); it would take jobs with stale code." >&2
  busy=1
fi
if [ "$busy" -eq 1 ]; then
  echo >&2
  echo "Another Nexus stack looks alive. Press Ctrl+C in its terminal, or stop it with:" >&2
  echo "  pkill -f start_dev.sh; pkill -f 'daphne .*nexus_backend'; pkill -f 'celery -A engine.celery_app'" >&2
  echo "Then run this script again." >&2
  exit 1
fi

if docker info >/dev/null 2>&1; then
  docker compose up -d >/dev/null
fi

PIDS=()
NAMES=()
cleanup() {
  local status="${1:-0}"
  echo
  echo "Shutting down Nexus dev stack..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  exit "$status"
}
trap cleanup SIGINT SIGTERM

(cd backend && "$PY" manage.py migrate --noinput >/dev/null)

echo "--> Daphne (backend) on http://localhost:8000   [logs/backend.log]"
(cd backend && exec "$PY" -m daphne -b 0.0.0.0 -p 8000 nexus_backend.asgi:application) >logs/backend.log 2>&1 &
PIDS+=($!); NAMES+=("Daphne (logs/backend.log)")

echo "--> Celery worker                                [logs/celery.log]"
(cd backend && exec "$PY" -m celery -A engine.celery_app worker -Q "${NEXUS_CELERY_QUEUE:-nexus}" --loglevel=INFO --concurrency=2 --pool=threads) >logs/celery.log 2>&1 &
PIDS+=($!); NAMES+=("Celery worker (logs/celery.log)")

if [ "$NO_FRONTEND" -eq 0 ]; then
  echo "--> Nuxt (frontend) on http://localhost:3000     [logs/frontend.log]"
  (cd frontend && exec npm run dev -- --port 3000) >logs/frontend.log 2>&1 &
  PIDS+=($!); NAMES+=("Nuxt (logs/frontend.log)")
fi

# --- wait for the backend to bind, then watch every service -------------------------------
for _ in $(seq 1 30); do
  [ -n "$(listener 8000)" ] && break
  if ! kill -0 "${PIDS[0]}" 2>/dev/null; then
    echo "Daphne exited during startup. Last lines of logs/backend.log:" >&2
    tail -n 20 logs/backend.log >&2
    cleanup 1
  fi
  sleep 1
done
[ -n "$(listener 8000)" ] || { echo "Daphne did not listen on :8000 within 30s; see logs/backend.log" >&2; cleanup 1; }

echo
echo "Nexus is up: backend http://localhost:8000$([ "$NO_FRONTEND" -eq 0 ] && echo ", frontend http://localhost:3000"). Press Ctrl+C to stop."
# bash 3.2 (macOS) has no `wait -n`, so poll: if any service dies, say which and stop the rest.
while true; do
  for i in "${!PIDS[@]}"; do
    if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
      echo "${NAMES[$i]} exited unexpectedly; stopping the stack." >&2
      cleanup 1
    fi
  done
  sleep 2
done
