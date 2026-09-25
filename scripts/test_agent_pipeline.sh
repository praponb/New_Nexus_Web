#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Nexus — end-to-end acceptance test for the agent pipeline (§11 Phase 7, §12).
#
#   1. Starts a private Daphne + Celery worker (own port, own Celery queue).
#   2. Registers a throwaway user, creates a project, uploads the fixture requirement.
#   3. Starts generation and watches the WebSocket (THOUGHT + TOOL_CALL events required).
#   4. Asserts generated files exist, QA reported PASS, and the downloaded zip matches its SHA256.
#   5. Unzips the archive, runs ./start_servers.sh and waits for the backend and frontend to answer.
#
# Usage: ./scripts/test_agent_pipeline.sh [--mode mock|live] [--inject-fault] [--skip-startup]
#                                         [--requirement FILE] [--timeout SECONDS]
#   --inject-fault   mock mode only: backend dev writes a syntax error first; asserts QA
#                    detects it and the repair cycle fixes it (qa_iterations >= 2).
#   --skip-startup   skip step 5 (running the generated app).
#   --verify-only ID skip steps 2-3 and re-run the checks against an already generated project
#                    (a token for its owner is minted locally via manage.py).
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
MODE="mock"
INJECT_FAULT=0
SKIP_STARTUP=0
REQUIREMENT="$ROOT/scripts/fixtures/user_requirement.md"
TIMEOUT=3600
VERIFY_ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --inject-fault) INJECT_FAULT=1; shift ;;
    --skip-startup) SKIP_STARTUP=1; shift ;;
    --requirement) REQUIREMENT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --verify-only) VERIFY_ONLY="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[ "$MODE" = "mock" ] || [ "$MODE" = "live" ] || { echo "--mode must be mock or live" >&2; exit 2; }
[ "$INJECT_FAULT" -eq 0 ] || [ "$MODE" = "mock" ] || { echo "--inject-fault requires --mode mock" >&2; exit 2; }
[ -x "$PY" ] || { echo "Missing .venv — run ./scripts/setup_environment.sh" >&2; exit 1; }
[ -f "$REQUIREMENT" ] || { echo "Requirement file not found: $REQUIREMENT" >&2; exit 1; }

c_blue=$'\033[1;34m'; c_green=$'\033[1;32m'; c_red=$'\033[1;31m'; c_off=$'\033[0m'
step() { echo; echo "${c_blue}==>${c_off} $*"; }
ok()   { echo "${c_green}✔${c_off} $*"; }
fail() { echo "${c_red}✘ $*${c_off}" >&2; exit 1; }

free_port() { "$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'; }
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {'d': d}))" "$1"; }

RUN_ID="$(date +%s)-$$"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/nexus-e2e-XXXXXX")"
API_PORT="$(free_port)"
API="http://127.0.0.1:$API_PORT"
QUEUE="nexus-e2e-$RUN_ID"
PIDS=()
APP_PGID=""

cleanup() {
  local code=$?
  if [ -n "$APP_PGID" ]; then kill -TERM -- "-$APP_PGID" 2>/dev/null || true; sleep 1; kill -KILL -- "-$APP_PGID" 2>/dev/null || true; fi
  for pid in "${PIDS[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  if [ "$code" -eq 0 ]; then rm -rf "$WORK"; else echo "Logs kept in $WORK" >&2; fi
}
trap cleanup EXIT

echo "Nexus pipeline acceptance test — ${VERIFY_ONLY:+verify-only $VERIFY_ONLY, }mode=$MODE inject_fault=$INJECT_FAULT work=$WORK"

# 1. Services ---------------------------------------------------------------
step "Starting private backend (Daphne :$API_PORT) and Celery worker (queue $QUEUE)"
if docker info >/dev/null 2>&1; then (cd "$ROOT" && docker compose up -d >/dev/null); fi
export NEXUS_ENGINE_MODE="$MODE" NEXUS_CELERY_QUEUE="$QUEUE" NEXUS_TASK_BACKEND=celery
export NEXUS_MOCK_DELAY="${NEXUS_MOCK_DELAY:-0.02}"
[ "$INJECT_FAULT" -eq 1 ] && export NEXUS_MOCK_INJECT_FAULT=1 || unset NEXUS_MOCK_INJECT_FAULT
(cd "$ROOT/backend" && "$PY" manage.py migrate --noinput >/dev/null)
(cd "$ROOT/backend" && exec "$PY" -m daphne -b 127.0.0.1 -p "$API_PORT" nexus_backend.asgi:application) >"$WORK/daphne.log" 2>&1 &
PIDS+=($!)
(cd "$ROOT/backend" && exec "$PY" -m celery -A engine.celery_app worker -Q "$QUEUE" -n "e2e-$RUN_ID@%h" --pool=threads -c 2 -l info) >"$WORK/celery.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 60); do curl -sf "$API/api/v1/health/" >/dev/null && break; sleep 1; done
curl -sf "$API/api/v1/health/" >/dev/null || fail "backend did not start (see $WORK/daphne.log)"
for _ in $(seq 1 60); do grep -q " ready" "$WORK/celery.log" && break; sleep 1; done
grep -q " ready" "$WORK/celery.log" || fail "celery worker did not start (see $WORK/celery.log)"
ok "backend and worker up"

EMAIL=""
PASSWORD=""
if [ -z "$VERIFY_ONLY" ]; then
# 2. User, project, requirement ----------------------------------------------
step "Registering test user and creating project"
EMAIL="e2e-$RUN_ID@example.com"
PASSWORD="E2e-$(openssl rand -hex 12)"
TOKEN="$(curl -sf -X POST "$API/api/v1/auth/register/" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"E2E Runner\"}" | json 'd["data"]["tokens"]["access"]')"
AUTH=(-H "Authorization: Bearer $TOKEN")
PROJECT_ID="$(curl -sf -X POST "$API/api/v1/projects/" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"name\":\"E2E Todo $RUN_ID\",\"description\":\"Acceptance test ($MODE)\"}" | json 'd["data"]["id"]')"
ok "project $PROJECT_ID"
WORDS="$(curl -sf -X POST "$API/api/v1/projects/$PROJECT_ID/requirement/" "${AUTH[@]}" -F "file=@$REQUIREMENT" | json 'd["data"]["word_count"]')"
ok "requirement uploaded ($WORDS words)"

# 3. Generate + watch the stream ---------------------------------------------
step "Starting generation and watching the WebSocket stream"
"$PY" "$ROOT/scripts/ws_watch.py" --project "$PROJECT_ID" --token "$TOKEN" --ws-base "ws://127.0.0.1:$API_PORT" \
  --timeout "$TIMEOUT" --require THOUGHT,TOOL_CALL --quiet >"$WORK/ws.log" 2>&1 &
WATCH_PID=$!
sleep 1
TASK_ID="$(curl -sf -X POST "$API/api/v1/projects/$PROJECT_ID/generate/" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"force_restart": false}' | json 'd["data"]["task_id"]')"
ok "task $TASK_ID queued"
if ! wait "$WATCH_PID"; then
  cat "$WORK/ws.log" >&2
  fail "pipeline did not complete successfully"
fi
tail -3 "$WORK/ws.log"
ok "stream delivered THOUGHT and TOOL_CALL events through pipeline_complete"
else
  PROJECT_ID="$VERIFY_ONLY"
fi

# 4. Assertions ----------------------------------------------------------------
step "Verifying results"
# Access tokens live 15 minutes and a live run takes longer, so authenticate afresh.
if [ -n "$EMAIL" ]; then
  TOKEN="$(curl -sf -X POST "$API/api/v1/auth/login/" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | json 'd["data"]["tokens"]["access"]')"
else
  TOKEN="$(cd "$ROOT/backend" && "$PY" manage.py shell -c "
from apps.accounts.serializers import tokens_for
from apps.projects.models import Project
print(tokens_for(Project.objects.get(id='$PROJECT_ID').owner)['access'])" 2>/dev/null | tail -1)"
fi
AUTH=(-H "Authorization: Bearer $TOKEN")
DETAIL="$(curl -sf "$API/api/v1/projects/$PROJECT_ID/" "${AUTH[@]}")"
STATUS="$(echo "$DETAIL" | json 'd["data"]["status"]')"
QA_ITER="$(echo "$DETAIL" | json 'd["data"]["latest_task"]["qa_iterations"]')"
EXPECTED_SHA="$(echo "$DETAIL" | json 'd["data"]["artifact"]["sha256_checksum"]')"
[ "$STATUS" = "COMPLETED" ] || fail "project status is $STATUS"
ok "project COMPLETED after $QA_ITER QA iteration(s)"
if [ "$INJECT_FAULT" -eq 1 ]; then
  [ "$QA_ITER" -ge 2 ] || fail "fault injection expected a repair cycle, got qa_iterations=$QA_ITER"
  ok "self-correction: QA caught the injected fault and the repair cycle fixed it"
fi

TOTAL_FILES="$(curl -sf "$API/api/v1/projects/$PROJECT_ID/files/" "${AUTH[@]}" | json 'd["data"]["total_files"]')"
[ "$TOTAL_FILES" -gt 5 ] || fail "only $TOTAL_FILES generated files"
WORKSPACE="$(cd "$ROOT/backend" && "$PY" manage.py shell -c "from apps.projects.models import Project; print(Project.objects.get(id='$PROJECT_ID').workspace_dir)" 2>/dev/null | tail -1)"
for f in backend/manage.py backend/requirements.txt frontend/package.json frontend/nuxt.config.ts start_servers.sh; do
  [ -f "$WORKSPACE/generated/$f" ] || fail "missing $f under $WORKSPACE/generated"
done
ok "$TOTAL_FILES files generated under ${WORKSPACE#$ROOT/}"

QA_FIRST_LINE="$(curl -sf -G "$API/api/v1/projects/$PROJECT_ID/files/content/" "${AUTH[@]}" --data-urlencode "path=.agents/qa_report.md" \
  | json 'd["data"]["content"].strip().splitlines()[0]')"
[ "$QA_FIRST_LINE" = "STATUS: PASS" ] || fail "QA report says: $QA_FIRST_LINE"
ok "QA report: $QA_FIRST_LINE"

ZIP="$WORK/artifact.zip"
HTTP="$(curl -s -o "$ZIP" -D "$WORK/headers.txt" -w '%{http_code}' "$API/api/v1/projects/$PROJECT_ID/download/" "${AUTH[@]}")"
[ "$HTTP" = "200" ] || fail "download returned HTTP $HTTP"
grep -qi 'content-type: application/zip' "$WORK/headers.txt" || fail "download is not application/zip"
ACTUAL_SHA="$(shasum -a 256 "$ZIP" | awk '{print $1}')"
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || fail "sha256 mismatch: $ACTUAL_SHA != $EXPECTED_SHA"
unzip -tq "$ZIP" >/dev/null || fail "zip failed integrity test"
ok "zip downloaded ($(du -h "$ZIP" | awk '{print $1}')), sha256 matches, archive intact"

unzip -q "$ZIP" -d "$WORK/unzipped"
APP_DIR="$(find "$WORK/unzipped" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -x "$APP_DIR/start_servers.sh" ] || fail "start_servers.sh is missing or not executable after unzip"
[ -f "$APP_DIR/.env.example" ] || fail ".env.example missing from archive"
ok "archive contains executable start_servers.sh and .env.example ($(basename "$APP_DIR"))"

# 5. Clean startup of the generated app -----------------------------------------
if [ "$SKIP_STARTUP" -eq 0 ]; then
  step "Running ./start_servers.sh from the extracted archive"
  BE_PORT="$(free_port)"; FE_PORT="$(free_port)"
  set -m
  (cd "$APP_DIR" && env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" LANG="${LANG:-en_US.UTF-8}" \
      BACKEND_PORT="$BE_PORT" FRONTEND_PORT="$FE_PORT" ./start_servers.sh) >"$WORK/start_servers.log" 2>&1 &
  APP_PGID=$!
  set +m
  disown "$APP_PGID" 2>/dev/null || true  # no job-control notice when cleanup kills the group
  be_ok=0; fe_ok=0
  for _ in $(seq 1 360); do
    kill -0 "$APP_PGID" 2>/dev/null || break
    [ $be_ok -eq 1 ] || { [ "$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$BE_PORT/")" = "200" ] && be_ok=1 && ok "backend answered 200 on :$BE_PORT"; }
    [ $fe_ok -eq 1 ] || { [ "$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$FE_PORT/")" = "200" ] && fe_ok=1 && ok "frontend answered 200 on :$FE_PORT"; }
    [ $be_ok -eq 1 ] && [ $fe_ok -eq 1 ] && break
    sleep 2
  done
  if [ $be_ok -ne 1 ] || [ $fe_ok -ne 1 ]; then
    tail -40 "$WORK/start_servers.log" >&2
    fail "generated app did not start cleanly (backend=$be_ok frontend=$fe_ok)"
  fi
  grep -qiE "Traceback|SyntaxError|No migrations to apply.*error" "$WORK/start_servers.log" && fail "errors in start_servers.log" || true
  API_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$BE_PORT/api/")"
  ok "generated API root /api/ -> HTTP $API_STATUS"
fi

echo
ok "ALL CHECKS PASSED (${VERIFY_ONLY:+verify-only, }mode=$MODE, inject_fault=$INJECT_FAULT)"
