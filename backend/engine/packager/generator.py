"""Adds the delivery files to the generated app: start_servers.sh, README.md, .env.example."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..context import DDS_FILE, MANIFEST_FILE, PipelineContext

START_SERVERS_SH = r"""#!/usr/bin/env bash
set -e

echo "=========================================="
echo " Starting Your Generated WebApp "
echo "=========================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Prefer a Python that Django 5 fully supports.
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
    for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi

# Ports: a port you set (env or .env) must be free; a default moves to the next free port.
port_busy() {
    "$PYTHON_BIN" - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                sys.exit(0)
    except OSError:
        pass
sys.exit(1)
PY
}

pick_port() {  # $1 = port, $2 = 1 if the user chose it
    local port="$1"
    while port_busy "$port"; do
        if [ "$2" = "1" ]; then
            echo "Port $port is already in use. Stop whatever is using it or choose another port." >&2
            return 1
        fi
        port=$((port + 1))
    done
    echo "$port"
}

BACKEND_PORT="$(pick_port "${BACKEND_PORT:-8000}" "${BACKEND_PORT:+1}")"
FRONTEND_PORT="$(pick_port "${FRONTEND_PORT:-3000}" "${FRONTEND_PORT:+1}")"
[ "$BACKEND_PORT" = "8000" ] || echo "--> Port 8000 is busy; the backend will use $BACKEND_PORT."
[ "$FRONTEND_PORT" = "3000" ] || echo "--> Port 3000 is busy; the frontend will use $FRONTEND_PORT."

# 1. Setup Backend
echo "--> Setting up Python Virtual Environment ($PYTHON_BIN)..."
cd "$PROJECT_ROOT/backend"
if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate
pip install --disable-pip-version-check -r requirements.txt
python manage.py migrate --fake-initial || python manage.py migrate

# 2. Setup Frontend
echo "--> Setting up Frontend Dependencies..."
cd "$PROJECT_ROOT/frontend"
npm install --no-fund --no-audit --cache "/tmp/npm-cache-$(basename "$PROJECT_ROOT")"

# 3. Launch Services Concurrently
BACKEND_PID=""
FRONTEND_PID=""
kill_tree() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
    kill "$1" 2>/dev/null || true
}
cleanup() {
    echo "Shutting down servers..."
    for pid in $BACKEND_PID $FRONTEND_PID; do kill_tree "$pid"; done
    exit "${1:-0}"
}
trap cleanup SIGINT SIGTERM

wait_for() {  # $1 = url, $2 = pid, $3 = name
    for _ in $(seq 1 120); do
        curl -s -o /dev/null "$1" && return 0
        kill -0 "$2" 2>/dev/null || { echo "$3 exited during startup (see the output above)." >&2; return 1; }
        sleep 1
    done
    echo "$3 did not respond at $1 within 120s." >&2
    return 1
}

# The frontend's origin is always allowed, whatever port it ended up on.
FRONTEND_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"

echo "--> Starting Backend on http://localhost:$BACKEND_PORT..."
cd "$PROJECT_ROOT/backend"
CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:+$CORS_ALLOWED_ORIGINS,}$FRONTEND_ORIGINS" \
    .venv/bin/python manage.py runserver "$BACKEND_PORT" &
BACKEND_PID=$!
wait_for "http://127.0.0.1:$BACKEND_PORT/" "$BACKEND_PID" "The backend" || cleanup 1

echo "--> Starting Frontend on http://localhost:$FRONTEND_PORT..."
cd "$PROJECT_ROOT/frontend"
NUXT_PUBLIC_API_BASE="${NUXT_PUBLIC_API_BASE:-http://localhost:$BACKEND_PORT}" \
    npx nuxi dev --port "$FRONTEND_PORT" &
FRONTEND_PID=$!
wait_for "http://localhost:$FRONTEND_PORT/" "$FRONTEND_PID" "The frontend" || cleanup 1

echo "Application is ready!"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Press Ctrl+C to stop both servers."
# Stop both servers if either one exits.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 2
done
echo "A server exited unexpectedly." >&2
cleanup 1
"""

ENV_EXAMPLE = """\
# Copy to .env to override defaults. start_servers.sh loads it automatically.

# Backend (Django)
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
# Extra allowed origins; start_servers.sh always adds the frontend it starts.
# CORS_ALLOWED_ORIGINS=https://app.example.com

# Optional PostgreSQL (SQLite is used when POSTGRES_DB is unset)
# POSTGRES_DB=app
# POSTGRES_USER=app
# POSTGRES_PASSWORD=app
# POSTGRES_HOST=/tmp
# POSTGRES_PORT=5432

# Frontend (Nuxt). start_servers.sh points it at the backend it starts unless you set it.
# NUXT_PUBLIC_API_BASE=http://localhost:8000

# Ports for start_servers.sh. Unset, it uses 8000/3000 or the next free ports; set, the port must be free.
# BACKEND_PORT=8000
# FRONTEND_PORT=3000
"""


ENV_EXAMPLE_MARKER = ENV_EXAMPLE.splitlines()[0]
README_MARKER = "Generated by **Nexus**: "


def _written_by_nexus(path: Path, marker: str) -> bool:
    try:
        return marker in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _section(markdown: str, title: str) -> str:
    match = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", markdown, flags=re.M | re.S | re.I)
    return match.group(1).strip() if match else ""


def _tree(root: Path, depth: int = 2) -> str:
    from apps.projects.workspace import EXCLUDED_DIRS

    lines = [f"{root.name}/"]

    def walk(path: Path, prefix: str, level: int):
        if level > depth:
            return
        entries = sorted(
            (p for p in path.iterdir() if p.name not in EXCLUDED_DIRS and p.name not in {".agents", ".DS_Store"}),
            key=lambda p: (p.is_file(), p.name.lower()),
        )
        for i, entry in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                walk(entry, prefix + ("    " if last else "│   "), level + 1)

    walk(root, "", 1)
    return "\n".join(lines)


def build_readme(ctx: PipelineContext) -> str:
    dds = ctx.read(DDS_FILE)
    overview = _section(dds, "Overview") or ctx.project_description or "A full-stack web application generated by Nexus."
    api = _section(dds, "REST API") or _section(dds, "REST API (JSON, no auth)")
    endpoints = ""
    if not api:
        try:
            manifest = json.loads(ctx.read(MANIFEST_FILE) or "{}")
            endpoints = "\n".join(
                f"- `{e.get('method', 'GET')} {e.get('path', '')}` {e.get('description', '')}".rstrip()
                for e in manifest.get("api_endpoints", [])
            )
        except (json.JSONDecodeError, AttributeError):
            endpoints = ""
    tree = _tree(ctx.root).replace(f"{ctx.root.name}/", f"{ctx.project_slug}_generated/", 1)
    return f"""# {ctx.project_name}

{overview}

Generated by **Nexus**: a Django 5 + Django REST Framework backend and a Nuxt 3 + Tailwind CSS frontend.

## Quick start

Requirements: Python 3.10+, Node.js 18+ and npm.

```bash
chmod +x start_servers.sh   # if your unzip tool dropped the executable bit
./start_servers.sh
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/

The script creates `backend/.venv`, installs Python and npm dependencies, applies migrations
(SQLite by default) and starts both servers. If port 8000 or 3000 is busy it uses the next free
port and prints the URLs it chose. Press Ctrl+C to stop them.

## Configuration

Copy `.env.example` to `.env` to change ports, CORS origins, or switch to PostgreSQL by setting `POSTGRES_DB`.

## Manual setup

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python manage.py migrate && python manage.py runserver 8000
# new terminal
cd frontend && npm install && npm run dev
```

## API

{api or endpoints or "See `backend/api/urls.py`."}

## Project structure

```
{tree}
```
"""


def write_support_files(ctx: PipelineContext) -> list[str]:
    """Write delivery files into the generated root; returns the relative paths written."""
    written = []
    script = ctx.path("start_servers.sh")
    script.write_text(START_SERVERS_SH, encoding="utf-8")
    script.chmod(0o755)
    written.append("start_servers.sh")

    # Refresh files Nexus wrote earlier (so repackaging picks up template changes), but never
    # overwrite ones the agents wrote themselves.
    env_example = ctx.path(".env.example")
    if not env_example.exists() or _written_by_nexus(env_example, ENV_EXAMPLE_MARKER):
        env_example.write_text(ENV_EXAMPLE, encoding="utf-8")
        written.append(".env.example")

    readme = ctx.path("README.md")
    if not readme.exists() or readme.stat().st_size < 200 or _written_by_nexus(readme, README_MARKER):
        readme.write_text(build_readme(ctx), encoding="utf-8")
        written.append("README.md")

    gitignore = ctx.path(".gitignore")
    if not gitignore.exists():
        gitignore.write_text(
            "backend/.venv/\nbackend/db.sqlite3\n__pycache__/\nfrontend/node_modules/\nfrontend/.nuxt/\n"
            "frontend/.output/\n.env\n",
            encoding="utf-8",
        )
        written.append(".gitignore")
    return written
