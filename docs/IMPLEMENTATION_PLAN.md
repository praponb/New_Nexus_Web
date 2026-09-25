# Nexus: Full Implementation Plan

## Context
The repo `/Users/praponb/GitHub/New_Nexus_Web` holds only `NEXUS_DESIGN_DOCUMENT.md`, `CLAUDE_CODE_PROMPT.md` and `.env`. The job is to build the whole Nexus platform: a Django 5 + DRF + Channels backend, an autonomous multi-agent generator in `backend/engine/`, and a Nuxt 3 client. The build follows the 7 phases in §11 of the design doc and verifies each phase before starting the next. The end result: an uploaded `user_requirement.md` produces a downloadable zip containing a working full-stack app.

### Decisions (from the user)
- **LLM: Moonshot only.** Settings come from `.env`: `MODEL_NAME=kimi-k3`, `MODEL_API_BASE=https://api.moonshot.ai/v1`, `MODEL_API_KEY`, `MODEL_REASONING_EFFORT`. There is no Gemini path.
- **Infra: full stack via Docker.** PostgreSQL 16 and Redis 7 run from `docker-compose.yml`. Celery workers run the pipeline, and `channels_redis` carries WebSocket fan-out between processes. SQLite and the in-memory layer remain as env fallbacks for unit tests only.
- **Pacing:** run all phases back to back, verifying each one, and stop only if blocked.
- **Mock mode:** `NEXUS_ENGINE_MODE=mock|live`. Mock replays a scripted agent stream and writes a known-good template app, with no LLM calls. Tests and UI development use mock. The final acceptance run uses live.

### Environment findings
- `python3` is 3.14. uv has 3.12.13, which will be used for `.venv` to keep packages compatible (`uv venv -p 3.12`).
- Node 24.16 and npm 11 are available.
- The Docker daemon is **currently off**, so the user must start Docker Desktop before Phase 2's Postgres/Redis steps. Brew `postgresql@17` exists but is stopped, so the Docker Postgres uses host port **5433** to avoid clashing with it.
- `google-antigravity` 0.1.7 is installed globally (the latest is 0.1.18). The API it exposes:
  - `Agent(config)` used as an async context manager.
  - `agent.chat(prompt)` returns a `ChatResponse`, whose `.chunks` yields `Thought`, `Text`, `ToolCall` and `ToolResult`.
  - `LocalOpenAIAgentConfig(model=, base_url=, system_instructions=, mcp_servers=, workspaces=, policies=, capabilities=)`.
  - `types.McpStdioServer(name=..., command=, args=)`, where the name must match `^[a-zA-Z0-9_-]+$`.
  - `policy.allow_all()` is required whenever MCP or write tools are enabled.
  - **Gap:** in 0.1.7 the OpenAI-compatible path sends only `base_url` (`GemmaEndpoint`) and has no API-key field. Moonshot needs `Authorization: Bearer`. Fix: pin the latest SDK; if it still has no key or header support, the engine starts a small **local auth relay** (aiohttp, on 127.0.0.1 with a random port) that forwards `/v1/*` to `MODEL_API_BASE` and adds the Bearer header. The agent's `base_url` then points at the relay.

## Phase 1: Scaffolding
- Create `backend/`, `frontend/`, `scripts/`, `media/` and `static/`. Run `git init` (no commits unless asked). Add `.gitignore`, which excludes `.env`, `.venv`, `node_modules`, `media/` and `.nuxt`.
- Create `.venv` with Python 3.12 and write `backend/requirements.txt`: django≥5.1, djangorestframework, djangorestframework-simplejwt, django-cors-headers, channels, channels-redis, daphne, celery, redis, psycopg2-binary, python-dotenv, google-antigravity, aiohttp and pytest-django.
- `django-admin startproject nexus_backend backend`, then create apps under `backend/apps/{accounts,projects,realtime}` with `AppConfig.name = "apps.<x>"`, and an `engine/` package.
- Scaffold Nuxt 3 in `frontend/` (`npx nuxi init`) with TypeScript, `@nuxtjs/tailwindcss`, `@tailwindcss/typography`, `@pinia/nuxt`, `lucide-vue-next`, `radix-vue`, `shiki` and `marked`.
- Add `docker-compose.yml` (postgres:16 on host port 5433, redis:7 on 6379), `.env.example`, and `scripts/setup_environment.sh`, `scripts/start_dev.sh` (Daphne, Celery worker and Nuxt together).
- `settings.py` loads `.env` from the repo root.
- **Verify:** `manage.py check`, `nuxi prepare` / `npm run build`, and `docker compose config`.

## Phase 2: Models, DB, Auth
- Implement the §4.2 models exactly, in `apps/accounts/models.py` (User, with email login) and `apps/projects/models.py`. Add Meta ordering and indexes (`AgentStepLog(task, sequence_num)`), and a `Project.save()` that auto-slugs.
- DB: Postgres when the `POSTGRES_*` env vars are set (the Docker defaults), otherwise SQLite.
- Configure SimpleJWT: 15-minute access and 7-day refresh tokens, rotation and blacklist. Use the Argon2 hasher first (add `argon2-cffi`), then PBKDF2.
- Add a response envelope `{success, data}` / `{success:false, error:{code,message}}` in `nexus_backend/api.py`, via a custom renderer and exception handler shared by all apps.
- Auth endpoints: `register/`, `login/`, `refresh/` and `me/` (profile plus quota summary: project count and generation count).
- **Verify:** makemigrations/migrate against Docker Postgres, plus pytest-django tests for register, login, refresh, me and bad credentials. The tests run on SQLite.

## Phase 3: Projects API
- In `apps/projects/views.py`, `ProjectViewSet` (list, create, retrieve, destroy, scoped to the owner) with these actions:
  - `requirement` (POST, multipart `file` or `content`): `.md` only, 5 MB maximum, rejects binary MIME types, decodes UTF-8 with `errors="replace"`, and requires at least 20 words. It upserts `RequirementDoc`, saving the raw text to a file when content is supplied.
  - `generate` (POST, returns 202): requires a requirement and rejects a run already in progress unless `force_restart`. Creates the `GenerationTask`, sets the status to QUEUED and dispatches it through `engine.tasks.dispatch()`.
  - `files` (GET, tree), `files/content` (GET `?path=`) and `download` (a `FileResponse` zip).
- A shared `safe_join(workspace, rel)` helper blocks path traversal. The workspace is `MEDIA_ROOT/workspaces/{user_id}/{project_id}/`.
- The project detail response includes the requirement preview, the latest task and artifact metadata.
- **Verify:** pytest for ownership isolation, upload validation (wrong extension, too few words, oversize), traversal rejection, and download returning 404 before any artifact exists.

## Phase 4: Engine (backend/engine/)
- `config.py`: reads `MODEL_*` and `NEXUS_ENGINE_MODE` into a frozen dataclass.
- `llm_relay.py`: the auth-injecting OpenAI proxy described above, as an async context manager. Skipped if the SDK supports a key natively.
- `mcp/registry.py`: factory functions returning `types.McpStdioServer` objects, each with a `name=`:
  - `thinking`: `npx -y @modelcontextprotocol/server-sequential-thinking`
  - `filesystem` / `filesystem-frontend` / `filesystem-backend`: `npx -y @modelcontextprotocol/server-filesystem <scoped dir>`
  - `playwright`: `npx -y @playwright/mcp --headless`

  All filesystem roots are confined to the project workspace (§10.2).
- `agents/{architect,frontend_dev,backend_dev,qa_tester}.py`: each exposes a `SYSTEM_PROMPT`, a `build_config(ctx)` that returns a `LocalOpenAIAgentConfig`, and a `build_prompt(ctx, …)`. The prompts contain the §6.2 rules, the output files (`.agents/dds_output.md`, `manifest.json`, `fe_output.md`, `be_output.md`, `qa_report.md`) and the §9 output layout. Two changes from the doc:
  - The generated backend uses **SQLite by default**, switching to Postgres only when `POSTGRES_*` env vars are set, so `start_servers.sh` works on a clean machine.
  - The QA report must contain the literal `STATUS: PASS` or `STATUS: FAIL`.
- `orchestrator.py`: `run_pipeline(task_id)`:
  - Phase transitions (PLANNING → GENERATING → TESTING → PACKAGING → COMPLETED/FAILED) with progress percentages.
  - Frontend and backend agents run together with `asyncio.gather`.
  - The §6.3 self-correction loop, at most 3 QA iterations, updating `qa_iterations`.
  - `run_agent_with_retry(config_fn, prompt)` builds a **fresh `Agent` for every attempt**. On 429, 503, RESOURCE_EXHAUSTED or connection-closed errors it backs off exponentially, starting at 70 s, for up to 4 attempts.
  - A stream pump maps each chunk to an `AgentStepLog`:
    - Thought deltas are buffered and flushed on sentence or size boundaries, so there isn't one row per token.
    - ToolCall and ToolResult become their own rows, with args and results in `metadata`.
    - Filesystem write calls produce a `file_created` event.
  - Every row is persisted, then broadcast through `engine/broadcast.py`.
  - Before QA, a deterministic check:
    - Every file in the manifest exists.
    - `python -m py_compile` passes on the backend.
    - `manage.py check` and `makemigrations --check` pass in a temporary venv.
    - `npm install && npx nuxi build` passes on the frontend.

    Its results go into the QA agent's prompt, so QA reasons from real signals instead of only what it observes in the browser.
- `mock_engine.py`: the same orchestrator interface. It emits a scripted stream (thoughts, tool calls, file writes) with small delays, and copies `engine/templates/todo_app/` into the workspace. The template is a small, real Todo app (Django + Nuxt) that also serves as a fallback reference.
- `packager/generator.py`: writes `start_servers.sh` (from §9, with chmod 755), a README built from the DDS, and `.env.example`. `packager/zipper.py` builds the zip with streaming writes; excludes `node_modules`, `.venv`, `.git`, `.nuxt`, `.output`, `__pycache__` and `db.sqlite3`; keeps the executable bit via `ZipInfo.external_attr`; computes SHA256 and file count; and creates the `GeneratedArtifact`.
- `celery_app.py` and `tasks.py`: `run_generation_task(task_id)` calls `asyncio.run(orchestrator.run_pipeline(...))` and catches everything to mark the project FAILED with `error_message`. `dispatch()` uses Celery `.delay`, and uses a background thread when `NEXUS_TASK_BACKEND=thread` (tests only).
- **Verify:**
  1. A live SDK smoke test: one small agent turn against kimi-k3 through the relay, confirming Thought/Text/ToolCall chunks arrive and an MCP filesystem write lands in the workspace.
  2. Unit tests for the zipper (exclusions, exec bit, checksum), `safe_join`, and orchestrator control flow using a fake agent runner (a forced first QA failure takes the repair path, then passes).
  3. A mock-mode full pipeline run through Celery.

## Phase 5: WebSockets
- `apps/realtime/middleware.py`: `JWTQueryAuthMiddleware`, which validates `?token=` with SimpleJWT.
- `consumers.py`: `ProjectLogConsumer` (AsyncJsonWebsocketConsumer) checks ownership and closes with 4401/4403 if it fails. It joins group `project_{id}`, sends the history of the latest task's logs followed by a `phase_update` snapshot, and relays `log_event`, `phase_update`, `file_created` and `pipeline_complete`/`pipeline_failed`.
- `routing.py` and `asgi.py`: `ProtocolTypeRouter` with `AllowedHostsOriginValidator`.
- `engine/broadcast.py`: `async_to_sync(channel_layer.group_send)` from Celery. The event shape follows §5.3.
- **Verify:** channels `WebsocketCommunicator` tests (auth rejected, history replayed, live event received), then a live check: run Daphne and Celery on Docker Redis, trigger a mock generation, and watch the socket with a Python `websockets` client script.

## Phase 6: Frontend (Nuxt 3, SPA mode `ssr:false`)
- Build the file tree from §8.
- `nuxt.config.ts`: `runtimeConfig.public.apiBase` / `wsBase`, the Inter font, and a dark theme using the §7.1 palette (slate-950, indigo `#6366f1`, cyan `#06b6d4`, glass cards).
- Pinia auth store and `useAuth` (tokens in localStorage; `$fetch` wrapper that refreshes on 401 and retries once).
- `useProjects`. `useProjectSocket`, with automatic reconnect, dedup by `sequence_num`, and reactive `logs`, `phase`, `progress`, `files` and `status`.
- Global `auth.ts` middleware.
- Pages:
  - login/register: split-screen with an animated agent-flow graphic.
  - dashboard: project grid, create modal, status badges, download and delete.
  - `projects/[id]`: Upload and Editor tabs, `FileUploadZone`, `MarkdownEditor` with split preview and 4 preset templates, Save Draft, and Start Generation.
  - `mission-control`: `PipelineStepper`, `TerminalStream` with agent filter tabs, icons and collapsible tool results, and a live `FileTreePreview`. It redirects to `ready` when generation completes.
  - `ready`: stats banner, `CodeViewer` (tree plus Shiki highlighting), README preview, the `./start_servers.sh` copy command, and `DownloadCard`.
- **Verify:** `nuxi typecheck` and `npm run build`, then drive the running app with Playwright (register, create a project, upload, mock generation streaming in mission control, ready page, download) and check screenshots.

## Phase 7: Scripts & acceptance
- `scripts/setup_environment.sh`: checks for python 3.12, node, npm and docker; runs `docker compose up -d`; waits for Postgres and Redis to be healthy; creates the venv and installs packages; runs `npm ci`; runs migrations; runs `npx playwright install chromium`; copies `.env.example` to `.env` if it's missing.
- `scripts/test_agent_pipeline.sh [--mode mock|live]`:
  1. Starts Daphne and Celery if they aren't running.
  2. Uses curl + jq to register or log in a test user, create a project and upload `scripts/fixtures/user_requirement.md` (a simple Todo app).
  3. Starts generation.
  4. A Python helper watches the WebSocket, asserts THOUGHT and TOOL_CALL events appear, and waits for completion.
  5. Asserts that files exist under `media/workspaces/...`, that the QA report says PASS, and that the download returns a valid zip whose SHA256 matches.
  6. Unzips to the scratch directory, runs `./start_servers.sh` in the background, polls `:8000` and `:3000` for HTTP 200, and shuts both down.
- The self-correction acceptance check: a mock-mode flag (`NEXUS_MOCK_INJECT_FAULT=1`) injects a syntax error; the test asserts QA sees FAIL, a repair cycle runs, and the next iteration passes.
- **Final acceptance:** run the full `--mode live` test against kimi-k3 and work through the §12 checklist.

## Critical files
- `backend/nexus_backend/{settings,asgi,urls,api}.py`
- `backend/apps/{accounts,projects,realtime}/*`
- `backend/engine/{orchestrator,tasks,celery_app,broadcast,config,llm_relay,mock_engine}.py`, `engine/agents/*.py`, `engine/mcp/registry.py`, `engine/packager/{generator,zipper}.py`, `engine/templates/todo_app/`
- `frontend/{nuxt.config.ts,composables/*,stores/auth.ts,pages/**,components/**}`
- `docker-compose.yml`, `scripts/*.sh`, `scripts/ws_watch.py`, `scripts/fixtures/user_requirement.md`

## Risks
- Docker Desktop must be running before Phase 2 migrations; if it isn't, the build pauses and asks.
- It is unverified whether the SDK's localharness drives kimi-k3 tool calling correctly. The Phase 4 smoke test checks this first; if it fails, report the details and ask before switching approach.
- Live runs take a long time (npm install and builds inside QA). Celery task time limits are set to about 60 minutes.
