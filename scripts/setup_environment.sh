#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Nexus — one-shot environment setup.
#   * verifies toolchain (python 3.12 via uv or system, node, npm, docker)
#   * starts PostgreSQL + Redis via docker compose and waits until healthy
#   * creates .venv and installs backend requirements
#   * installs frontend dependencies
#   * runs database migrations
#   * installs Playwright's Chromium (used by the QA agent's @playwright/mcp)
# Usage: ./scripts/setup_environment.sh [--skip-docker] [--skip-frontend]
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKIP_DOCKER=0
SKIP_FRONTEND=0
for arg in "$@"; do
  case "$arg" in
    --skip-docker) SKIP_DOCKER=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

c_blue=$'\033[1;34m'; c_green=$'\033[1;32m'; c_red=$'\033[1;31m'; c_off=$'\033[0m'
step() { echo "${c_blue}==>${c_off} $*"; }
ok()   { echo "${c_green}✔${c_off} $*"; }
die()  { echo "${c_red}✘ $*${c_off}" >&2; exit 1; }

# 1. Toolchain ----------------------------------------------------------------
step "Checking toolchain"
command -v node >/dev/null || die "node is required (>= 20)"
command -v npm  >/dev/null || die "npm is required"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 20 ] || die "node >= 20 required (found $(node --version))"
ok "node $(node --version), npm $(npm --version)"

if command -v uv >/dev/null; then
  PY_CREATE=(uv venv -q -p 3.12 .venv)
  PIP_INSTALL=(uv pip install -q -p .venv/bin/python)
elif command -v python3.12 >/dev/null; then
  PY_CREATE=(python3.12 -m venv .venv)
  PIP_INSTALL=(.venv/bin/pip install -q)
else
  die "Python 3.12 is required (install uv: https://docs.astral.sh/uv/ or python3.12)"
fi

# 2. .env ---------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example — fill in MODEL_API_KEY before live runs"
else
  ok ".env present"
fi

# 3. Docker services ----------------------------------------------------------
if [ "$SKIP_DOCKER" -eq 0 ]; then
  step "Starting PostgreSQL + Redis (docker compose)"
  command -v docker >/dev/null || die "docker is required (or pass --skip-docker and set DB_ENGINE=sqlite CHANNEL_LAYER=memory)"
  docker info >/dev/null 2>&1 || die "Docker daemon is not running — start Docker Desktop first"
  docker compose up -d
  for svc in nexus-postgres nexus-redis; do
    for _ in $(seq 1 60); do
      status="$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo starting)"
      [ "$status" = "healthy" ] && break
      sleep 1
    done
    [ "$status" = "healthy" ] || die "$svc did not become healthy"
    ok "$svc healthy"
  done
fi

# 4. Python backend -----------------------------------------------------------
step "Setting up Python virtual environment"
[ -x .venv/bin/python ] || "${PY_CREATE[@]}"
"${PIP_INSTALL[@]}" -r backend/requirements.txt
ok "backend requirements installed ($(.venv/bin/python --version))"

step "Running migrations"
(cd backend && ../.venv/bin/python manage.py migrate --noinput)
ok "database migrated"

# 5. Frontend -----------------------------------------------------------------
if [ "$SKIP_FRONTEND" -eq 0 ]; then
  step "Installing frontend dependencies"
  (cd frontend && if [ -f package-lock.json ]; then npm ci --no-fund --no-audit; else npm install --no-fund --no-audit; fi)
  ok "frontend dependencies installed"
fi

# 6. Agent tooling ------------------------------------------------------------
step "Pre-fetching MCP servers and Playwright Chromium (for QA agent)"
npx -y @playwright/mcp@latest --version >/dev/null 2>&1 || true
for pkg in @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-sequential-thinking; do
  npm cache add "$pkg" >/dev/null 2>&1 || true
done
npx -y playwright install chromium >/dev/null 2>&1 || echo "  (playwright chromium install skipped/failed — QA browser checks may be limited)"
ok "agent tooling ready"

mkdir -p media/workspaces logs
echo
ok "Setup complete. Start everything with: ./scripts/start_dev.sh"
