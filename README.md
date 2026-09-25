# Nexus: autonomous web-app generation

Nexus turns a `user_requirement.md` into a working full-stack web application (Django 5 + DRF backend, Nuxt 3 + Tailwind frontend). A team of four AI agents does the work while you watch the live stream:

1. The **Team Lead** writes the design (`.agents/dds_output.md`) and the file manifest (`.agents/manifest.json`).
2. The **Frontend Dev** and **Backend Dev** build in parallel.
3. **QA** runs real checks and browser tests in a self-correcting loop (up to 3 repair cycles).
4. The **packager** zips the result, adding `start_servers.sh`, `README.md` and `.env.example`.

The spec is `NEXUS_DESIGN_DOCUMENT.md`. Implementation notes are in `docs/`. For day-to-day commands and known problems with their fixes, see **[user_guide.md](user_guide.md)**.

## Architecture

| Layer | Stack |
|---|---|
| API | Django 5, DRF, SimpleJWT (15 min access / 7 day refresh with rotation and blacklist), envelope `{success, data \| error}` |
| Realtime | Django Channels over Daphne, Redis channel layer, `ws://…/ws/projects/{id}/logs/?token=` |
| Workers | Celery (Redis broker) running `engine.tasks.run_generation_task` |
| Engine | `backend/engine/`: Antigravity SDK agents against **Moonshot kimi-k3** through a local auth relay, plus MCP servers (filesystem, sequential-thinking, Playwright) |
| Data | PostgreSQL 16 (Docker, host port 5433). Workspaces live in `media/workspaces/{user}/{project}/` |
| Client | Nuxt 3 SPA, Pinia, Tailwind, Shiki, marked + DOMPurify |

### Engine notes
- **`engine/llm_relay.py`.** The SDK's OpenAI-compatible path can't send an API key. The relay adds `Authorization: Bearer $MODEL_API_KEY` on 127.0.0.1. It also taps the stream: `reasoning_content` becomes THOUGHT events and tool messages become TOOL_RESULT events.
- **Sandboxing.** Agents get no builtin file tools. They read and write only through filesystem MCP servers rooted in the project workspace. QA also gets `run_command`, and it runs the app on private ports.
- **Ground-truth checks.** Before each QA turn, `engine/checks.py` runs the checks: manifest and layout, `compileall`, an isolated venv with `manage.py check`, `makemigrations --check` and `migrate`, then `npm install` and `nuxi build`. A PASS requires both the QA agent and these checks to pass.
- **Mock mode.** `NEXUS_ENGINE_MODE=mock` runs the same orchestrator with a scripted, LLM-free stream and a template Todo app. `NEXUS_MOCK_INJECT_FAULT=1` exercises the repair loop.

## Quick start

Requirements: Docker Desktop, [uv](https://docs.astral.sh/uv/) or Python 3.12, and Node 20+.

```bash
./scripts/setup_environment.sh      # Postgres + Redis, .venv, npm install, migrations, Playwright Chromium
# put your Moonshot key in .env → MODEL_API_KEY=...
./scripts/start_dev.sh              # Daphne :8000, Celery worker, Nuxt :3000 (logs in ./logs)
```

Open http://localhost:3000, create an account, create a project, upload or write the requirement, and press **Start Autonomous Generation**.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q                 # unit + integration (SQLite, in-memory channels)
cd frontend && npx nuxi typecheck && npm run build
./scripts/test_agent_pipeline.sh --mode mock --inject-fault     # end-to-end with self-correction, runs the generated app
./scripts/test_agent_pipeline.sh --mode live                    # full acceptance against kimi-k3 (slow; uses API credits)
```

`test_agent_pipeline.sh` runs its own Daphne and Celery worker on a private port and queue. It does the following:
- Streams the WebSocket with `scripts/ws_watch.py`.
- Checks that the QA report is `STATUS: PASS` and that the download's SHA256 matches.
- Unzips the archive and runs `./start_servers.sh`, waiting for both servers to answer.

## Layout

```
backend/   nexus_backend/ (settings, asgi, api envelope) · apps/{accounts,projects,realtime} · engine/ · tests/
frontend/  pages/ · components/{ui,dashboard,requirement,generation,delivery} · composables/ · stores/
scripts/   setup_environment.sh · start_dev.sh · test_agent_pipeline.sh · ws_watch.py · fixtures/
```
