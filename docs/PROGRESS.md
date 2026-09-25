# Nexus: Implementation Progress & Handoff

> **Resuming in a new session?** Read this file first, then `docs/IMPLEMENTATION_PLAN.md` (the approved plan) and `NEXUS_DESIGN_DOCUMENT.md` (the spec).
> Last updated: 2026-09-25 (session 2, evening). All 7 phases are done. Live acceptance passed on runs 1, 3 and 5. Run 6 failed at QA loop 3 and was then completed live through "Continue repair". Everything is merged into `main` (PRs #1–#4). See **Resume here**.

## Decisions made by the user (do not re-ask)
| Topic | Decision |
|---|---|
| LLM | **Moonshot only**: `kimi-k3` at `https://api.moonshot.ai/v1`, set in `.env` `MODEL_*`. No Gemini path. |
| Infra | **Full stack via Docker**: `docker-compose.yml` runs Postgres 16 (host port **5433**) and Redis 7 (6379). Celery runs the pipeline and `channels_redis` fans events out. |
| Pacing | Run all 7 phases back to back, verifying each one. Stop only if blocked. |
| Mock mode | Add `NEXUS_ENGINE_MODE=mock|live`. Mock is a scripted stream plus a template Todo app. Tests use mock; final acceptance uses live. |

## Environment facts
- Python venv: `.venv` (Python 3.12.13, created with `uv venv -p 3.12`). Install with `uv pip install -p .venv/bin/python -r backend/requirements.txt`.
- The system `python3` is 3.14. Don't use it for the venv.
- Node 24.16 and npm 11.13 are installed. There is no `timeout` command on macOS.
- Docker Desktop is now running and the `nexus-postgres` / `nexus-redis` containers are up. Migrations are applied to Postgres.
- **SDK gap:** `google-antigravity` 0.1.18's `LocalOpenAIAgentConfig` sends only `base_url` (via `GemmaEndpoint`), with no API key or headers. Plan: `engine/llm_relay.py`, a local aiohttp proxy that adds `Authorization: Bearer $MODEL_API_KEY` and forwards to `MODEL_API_BASE`.
- Useful SDK facts:
  - `Agent(config)` is an async context manager. `await agent.chat(prompt)` returns a `ChatResponse`; `.chunks` yields `Thought`, `Text`, `ToolCall` and `ToolResult`.
  - `types.McpStdioServer(name=..., command=, args=)`: the name must match `^[a-zA-Z0-9_-]+$`.
  - `policies=[policy.allow_all()]` is required when MCP or write tools are enabled. Policy module: `google.antigravity.hooks.policy`; also check `google.antigravity.policy`.
  - The SDK source is in `.venv/lib/python3.12/site-packages/google/antigravity/`.
- `.env` holds the user's original `MODEL_*` lines plus a runtime block appended during setup (`NEXUS_ENGINE_MODE=live`, `DB_ENGINE=postgres`, `POSTGRES_*` on port 5433, `REDIS_URL`, `CHANNEL_LAYER=redis`, `DJANGO_SECRET_KEY`).
- **Known issue:** `npm install` in `frontend/` stalled twice during registry metadata fetches (`node_modules` still empty). Re-run with `cd frontend && npm install --no-fund --no-audit --fetch-timeout=60000 --fetch-retries=5`, in the background, and poll. `package.json` pins **Nuxt 3** (`^3.21.11`), `@pinia/nuxt ^0.11.3` with `pinia ^3`, `@nuxtjs/tailwindcss ^6.14` (Tailwind 3.4), `shiki ^3`, `typescript ^5.9` and `vue-tsc ^2.2`.

## Phase status
### Phase 1: Scaffolding. Done, except frontend verification
- Directories, `git init` (no commits), `.gitignore`, `.env.example`, `docker-compose.yml`.
- `scripts/setup_environment.sh` and `scripts/start_dev.sh` (Daphne :8000, a Celery `engine.celery_app` worker with `--pool=threads`, Nuxt :3000; logs go to `logs/`).
- Django project `backend/nexus_backend`. Apps live in `backend/apps/{accounts,projects,realtime}` with `name="apps.<x>"` and `label="<x>"`.
- `settings.py`:
  - Loads the repo-root `.env`.
  - `DB_ENGINE=postgres` selects Postgres; anything else falls back to SQLite.
  - `CHANNEL_LAYER=redis|memory`.
  - Celery settings.
  - `NEXUS_ENGINE_MODE`, `NEXUS_TASK_BACKEND` (`celery|thread|inline`), `NEXUS_MAX_QA_ITERATIONS` and `NEXUS_MONTHLY_GENERATION_QUOTA`.
  - `WORKSPACES_ROOT = MEDIA_ROOT/workspaces`.
- Frontend files written so far: `package.json`, `nuxt.config.ts` (`ssr:false`, runtimeConfig `apiBase` / `wsBase`, component `pathPrefix:false`), `tailwind.config.js` (ESM import of typography), `assets/css/main.css` (glass-card, text-gradient, shiki styles), `app.vue`, a placeholder `pages/index.vue`, and `public/favicon.svg`. The empty directory tree from §8 has also been created.
- **Still to do:** finish `npm install`, then verify with `npx nuxi prepare && npm run build`.

### Phase 2: Models, DB, Auth. Done and verified
- `apps/accounts/models.py`: User with a UUID pk, `USERNAME_FIELD=email`, and a manager that auto-generates usernames. Admin is registered.
- `apps/projects/models.py`: all §4.2 models. Additions beyond the spec:
  - `GenerationTask.created_at`
  - `GeneratedArtifact.total_lines_of_code`
  - `Project.save()` auto-fills the slug and `workspace_dir`
  - `ACTIVE_STATUSES`
  - `Project.latest_task()`
- `nexus_backend/api.py`: `EnvelopeJSONRenderer`, `envelope_exception_handler`, `ApiError(message, code, status_code)` and `ok()`.
- Auth at `/api/v1/auth/`: register, login, refresh (rotation and blacklist), logout, and me (GET and PATCH, with a quota summary).
- Tests: `backend/tests/` (`conftest.py`, `test_auth.py`) use `nexus_backend/settings_test.py` (SQLite in memory, memory channel layer, temp media, `NEXUS_TASK_BACKEND=inline`). **5/5 pass.** Run them with `cd backend && ../.venv/bin/python -m pytest -q`.

### Phase 3: Projects API. Done and verified
- `apps/projects/serializers.py`: `ProjectSerializer` (list/create; includes `has_requirement`, `download_ready`, `progress_percentage`), `ProjectDetailSerializer` (adds `requirement` with preview and raw content, `latest_task`, `artifact`), plus Requirement, Task, Artifact and Log serializers.
- `apps/projects/views.py`: `ProjectViewSet` (list, create, retrieve, update, destroy, owner-scoped) with actions `requirement` (GET/POST), `generate` (202; 409 while active unless `force_restart`; 429 over monthly quota; deletes old artifact; calls `engine.tasks.dispatch(task)` and stores the returned job id), `logs` (`?task_id=`, `?after=<seq>`), `files`, `files/content?path=` (JSON: path, size, extension, is_binary, truncated, content) and `download` (FileResponse, `X-Checksum-SHA256`).
- Uploads: `.md` only, text-ish MIME, 5 MB, NUL/control-byte binary check (`_is_binary_upload`, so stray non-UTF-8 bytes are decoded with replacement rather than rejected), at least 20 words.
- `apps/projects/urls.py` uses a `SimpleRouter` (DefaultRouter's API root clashes with list at `""`), mounted at `api/v1/projects/`.
- `engine/tasks.py` is a stub `dispatch()` that returns `None`. Phase 4 replaces it.
- Tests: `tests/test_projects.py`. **39/39 pass overall.** A curl run against runserver on Postgres went through register, create, upload, files, generate (202, then 409), download (404) and delete (204).

### Phase 1 frontend: `npm install` completed (847 packages, `nuxt prepare` ran in postinstall).

### Phase 4: Engine. Done and verified
- **Live SDK smoke test PASSED** (`cd backend && ../.venv/bin/python -m engine.devtools.sdk_smoke <dir>`): kimi-k3 through `engine/llm_relay.py`, and the MCP `write_file` landed in the workspace.
- Harness facts:
  - kimi-k3 yields only `ToolCall` and `Text` chunks, with **no `Thought` and no `ToolResult` chunks**.
  - `LLMRelay(on_event=...)` taps the missing pieces: SSE `reasoning_content` becomes `("reasoning", {text})`, and the request's `role:"tool"` messages become `("tool_result", {...})`, deduplicated by id.
  - The live runner starts **one relay per agent attempt**, so events are attributed correctly.
- Sandboxing: agents get `enabled_tools=[FINISH]` plus MCP servers. File I/O goes only through filesystem MCP servers rooted in the workspace. QA additionally gets `RUN_COMMAND` (daemons, sandbox flag).
  - **Not yet verified live:** whether `enabled_tools=[FINISH]` works with the harness. If an agent errors on it, fall back to `disabled_tools=[VIEW_FILE, CREATE_FILE, EDIT_FILE, ...]`.
- Files:
  - `engine/config.py`, `llm_relay.py`, `context.py` (`PipelineContext`, `.agents/*` file constants, QA ports picked by `free_port()`), `events.py` (`EventSink`: persists an `AgentStepLog` and then broadcasts; handles phase, progress, `file_created`, complete and fail), and `broadcast.py` (group `project_{id}`, message `{"type": "relay.event", "event": {type, data}}`).
  - `mcp/registry.py`: thinking, filesystem and playwright servers.
  - `agents/{base,architect,frontend_dev,backend_dev,qa_tester}.py`: prompts, `build_config`, and `AgentJob(role, agent_name, prompt, config_fn, extra)`.
  - `runner.py`: `StreamPump`, and `LiveAgentRunner` (a fresh Agent and relay per attempt, backoff of 70s×2^n on 429/503/etc., a 45-minute timeout per agent).
  - `mock_engine.py`: `MockAgentRunner`, which writes `templates/todo_app`; `NEXUS_MOCK_INJECT_FAULT=1` injects a syntax error that the repair loop then fixes. `NEXUS_MOCK_DELAY` sets the step delay (default 0.12s).
  - `checks.py`: `NEXUS_QA_CHECKS=off|fast|full` (live defaults to full). Checks cover layout and manifest, compileall, an isolated venv under `workspace/.qa`, then `manage.py check`, `makemigrations --check` and `migrate`, then `npm install` and `nuxi build`.
  - `orchestrator.py` (`run_pipeline`, which never raises; failures mark FAILED and emit `pipeline_failed`). A QA pass also requires the deterministic checks to pass, and after each QA run it kills anything listening on the QA ports.
  - `packager/{generator,zipper}.py`, `celery_app.py`, and `tasks.py` (`dispatch`: celery, thread or inline).
- The template Todo app (`engine/templates/todo_app`) passes `manage.py check` and `migrate`, and its frontend passes `npm install` and `nuxi build`.
- Migration `projects/0002_widen_file_paths`: FileField `max_length` 100 → 500. The workspace zip path is longer than 100 characters; Postgres rejected it, but SQLite never enforced the limit.
- Tests: `tests/test_engine.py` (zipper, relay taps, pump, retry with a fresh agent, mock pipeline happy path, fault → repair, fail after max iterations, missing requirement). **48/48 pass overall.**
- A mock run through a real Celery worker (threads pool) on Postgres and Redis reached COMPLETED with 28 files and 86 logs.

### Phase 5: WebSockets. Done and verified
- `apps/realtime/middleware.py` (`JWTQueryAuthMiddleware`, `?token=`), `consumers.py` (`ProjectLogConsumer`), `routing.py` (`ws/projects/<uuid>/logs/`), and `nexus_backend/asgi.py` (`ProtocolTypeRouter` + `AllowedHostsOriginValidator`).
- Protocol:
  - The server accepts, then closes with **4401** (no or bad token) or **4404** (not the owner).
  - On connect it sends `{"type":"history","data":{task_id, logs:[...]}}` (honouring `?after=<seq>`), then a `phase_update` snapshot with `snapshot:true`, `status`, `error_message` and `artifact`.
  - Live events: `log_event`, `phase_update`, `file_created`, `pipeline_complete` and `pipeline_failed`. `{"type":"ping"}` gets a `pong`.
- `scripts/ws_watch.py`: a watcher with reconnect-and-dedupe that asserts the required log types.
- Tests: `tests/test_realtime.py` (5). **53/53 pass overall.**
- Live check: Daphne on :8766 with a Celery worker (mock) and Docker Redis. REST register → create → upload → generate, and `ws_watch` saw the whole stream through `pipeline_complete` (THOUGHT, TOOL_CALL and more; 33 files streamed). Download returned 200.
- `CORS_EXPOSE_HEADERS` now includes `X-Checksum-SHA256`.

### Phase 6: Frontend. Done and verified
- Core:
  - `types/api.ts`, `stores/auth.ts` (tokens and user in localStorage under `nexus.auth`).
  - `composables/useApi.ts`: envelope unwrap, `ApiError`, and a single-flight refresh on 401 with one retry.
  - `useAuth`, `useProjects` (download fetches a blob with the auth header), `useToast`, and `useProjectSocket` (reconnect with backoff, `?after=`, dedupe by seq, `expectNewRun`, seeding from `/files/`).
  - `middleware/auth.global.ts`.
  - `utils/{pipeline,format,markdown,presets,fileTree,highlight}.ts`. Shiki is lazy-loaded; Markdown goes through marked + DOMPurify.
- Components: `ui/*` (BaseButton, BaseInput, StatusBadge, BaseModal, ConfirmDialog, ToastHost, NexusLogo), `auth/AgentFlowGraphic`, `dashboard/*`, `requirement/*`, `generation/*`, `delivery/*`, `common/FileTreeNode`.
- Pages: `auth/login`, `auth/register`, `dashboard`, `projects/[id]/{index,mission-control,ready,generate(→mission-control)}`.
- Verified: `nuxi typecheck` and `npm run build` pass (a build fails with "Another Nuxt dev is already running" if the dev server is up).
- Browser run-through in Chrome, mock worker with fault injection:
  - Steps: auth redirect → dashboard → create modal → editor preset with split preview → Start → Mission Control streaming (stepper, QA loop 1 FAIL, repair cycle) → auto-redirect → Ready (stats, 2 QA loops, Shiki explorer, README, download card).
  - No console errors.
  - The session was injected via localStorage; the login and register forms were not submitted in the browser.
- Bugs found and fixed:
  - **redis-py 8 defaults `socket_timeout=5`**, the same as channels_redis's BZPOPMIN block, so idle WebSockets died with 1011 "Timeout reading". `CHANNEL_LAYERS` hosts now use `{"address": REDIS_URL, "socket_timeout": 30}`.
  - Grid overflow on `ready` and `mission-control` (now `minmax(0,1fr)`).
  - Modal autofocus.
  - Badge wrapping.
  - 24-hour timestamps.

### Phase 7: Scripts & acceptance. Done
- `scripts/test_agent_pipeline.sh [--mode mock|live] [--inject-fault] [--skip-startup] [--requirement F] [--timeout S] [--verify-only PROJECT_ID]`:
  - Runs a private Daphne on a free port and a Celery worker on a private queue (`NEXUS_CELERY_QUEUE`, setting `CELERY_TASK_DEFAULT_QUEUE`, default `nexus`; `start_dev.sh` passes `-Q`).
  - Flow: register → create → upload the fixture → generate → `ws_watch` → **log in again** (access tokens last 15 minutes; live runs take longer) → assertions → download → SHA256 check → unzip → `start_servers.sh` with `env -i` on free ports → poll `localhost` (Nuxt dev binds `::1`).
- **Mock + inject-fault acceptance PASSED**: 2 QA iterations, QA PASS, SHA256 match, and the extracted app served 200 on the frontend, backend and `/api/`.
- **LIVE acceptance (kimi-k3) PASSED**, project `9ddc5158-…`:
  - The pipeline completed with 59 THOUGHT and 102 TOOL_CALL events. QA passed on loop 1, after all deterministic checks passed, including a hand-written migration that matched the models.
  - The live QA agent ran 14 curl API checks and drove the UI with Playwright; its report is in `.agents/qa_report.md`.
  - The first script run failed only on the expired token. Re-verified with `--verify-only`: all checks passed, including `start_servers.sh`.
- Fixes prompted by the live run:
  1. **Environment scrubbing** (`engine/config.py:scrub_process_env`, called at the start of `run_pipeline`): the harness merges `os.environ` into agent subprocesses, so QA's shell could see `MODEL_API_KEY`, and `POSTGRES_DB` would point generated apps at Nexus's database. These variables are now removed from the process environment and read through `env_value()`.
  2. Dev agents wrote notes into `frontend/.agents/` and `backend/.agents/`. The orchestrator now moves them into the root (`_collect_stray_notes`), and `iter_files(include_hidden_agents=False)` excludes `.agents` at any depth.
  3. `view_file` is enabled but path-scoped (see the sandbox refinement).
- These fixes were verified with unit tests plus a mock Celery acceptance run. **A second full live run after them has not been done yet.**
- **57/57 backend tests passed at the end of session 1** (58 after fix 5). Frontend `nuxi typecheck` and `npm run build` pass.

## §12 acceptance checklist
- [x] Auth flow: register, login, JWT refresh/rotation/blacklist, protected routes, and redirect to `/auth/login` (API tests plus the browser redirect; the forms were not submitted in the browser).
- [x] Upload handling: `.md` upload and editor content persisted (API tests plus the browser editor/preset save). **Browser upload tested in session 2**: a file set through the drop zone's file input passed validation, rendered the preview and was saved as a draft byte-for-byte. A physical drag gesture was not simulated.
- [x] Agent execution: `POST /generate/` → Celery → orchestrator (mock and live).
- [x] Streaming logs: Mission Control live stream, stepper and file tree (browser).
- [x] Generated app completeness: the live kimi-k3 output has a full Nuxt 3 frontend and Django 5 backend.
- [x] Self-correction: the injected syntax error is detected and repaired (mock). **Also exercised live** in run `b8f0e944`: a real Vue template bug was caught by QA and repaired in loop 2.
- [x] Download: a valid zip with `.env.example` and an executable `start_servers.sh`, SHA256 verified (script and API). **Browser button tested in session 2** (with the user's approval): `nexus_project_team-task-tracker.zip` reached `~/Downloads` with a matching SHA256.
- [x] Clean startup: `./start_servers.sh` served 200s for both the mock and the live archives.

## Resume here (2026-09-25, second session)
- **The second live run (project `e39016e8-…`) FAILED on its own, before the restart**, at 25% in the Frontend Dev agent:
  - The agent wrote every frontend file, then called `filesystem-frontend.create_directory(".agents")`. That server is rooted at `generated/frontend`, so the call was denied (the notes are only reachable via `agents-notes`).
  - The harness then dropped its WebSocket (close 1006). `is_retryable` didn't match `AntigravityConnectionError`, so the whole pipeline failed.
  - Root cause: the old `SHARED_RULES` wording ("the only exception is the notes files under the `.agents` directory") read as allowing a relative path.
- **Fixed (commit `739e126`, in PR #1):**
  1. `SHARED_RULES`: every tool path must be absolute.
  2. New `DEV_NOTES_RULE` in `agents/base.py`, used by both dev agents: write notes only via `agents-notes` at `{root}/.agents/<file>.md`. Task prompts name the server too.
  3. `runner.py`: "harness process exited unexpectedly" is retryable. Attempts after the first prepend `RETRY_PREAMBLE` ("finish the files already on disk; don't start over").
  4. Tests extended. **57/57 pass.**
- **Third live run (project `b8f0e944-…`), started with `739e126`:** the dev agents did call `agents-notes`, but it was still denied, while `agents-notes.write_file` to `frontend/fe_output.md` *succeeded*.
  - ~~Diagnosed as "the harness routes MCP calls by tool name"~~. **That was wrong**; see run 4 below.
  - The denial did *not* crash the harness this time. The agents fell back to `frontend/fe_output.md` and `backend/be_output.md`.
- **Run `b8f0e944` result: ALL CHECKS PASSED (live), with the first live self-correction:**
  - QA loop 1 FAILED correctly: `TodoItem.vue` had `\"` escapes inside Vue attribute bindings, so `nuxi build` failed and the page was a Nuxt 500 in Playwright.
  - The Team Lead's repair plan led the Frontend agent to a surgical fix (single quotes). The Backend agent correctly did nothing. QA loop 2 PASSED.
  - Totals: 120 THOUGHT and 198 TOOL_CALL events, 39 files streamed, zip 128K / 34 files, SHA256 match. The extracted `start_servers.sh` served 200 on the backend, frontend and `/api/`.
  - Known leak in this run (pre-fix-2 code): `backend/be_output.md` and `frontend/fe_output.md` are inside the zip. Fix 2's `_collect_stray_notes` prevents that.
- **Run 4 (`2db677fd-…`, with the two-root server) was still denied**, and the error listed only `generated/frontend` as allowed. **Actual root cause:**
  - `server-filesystem` implements the MCP roots protocol. When the client advertises roots, it REPLACES its command-line directories with them.
  - The harness advertises each agent's `workspaces` as roots. Dev agents had `workspaces=[<side>_dir]`, so every filesystem server (including `agents-notes`) was re-rooted to that subtree.
  - Proven over stdio: CLI dirs `[frontend, .agents]` with client roots `[frontend]` produced the identical denial; with roots `[frontend, .agents]` the write succeeded.
- **Fix 3 (commit `b1d2a92`, in PR #1; supersedes fix 2's two-root server, which is reverted):**
  - `build_config` adds `generated/.agents` to `workspaces` whenever the agent's workspace is a subtree that doesn't contain it. The view_file sandbox uses the same list.
  - The registry docstring documents the roots override.
  - `_collect_stray_notes` still handles the top-level fallback notes. 57/57 tests pass.
- **Run 4 result: FAILED in QA loop 1** with `AntigravityExecutionError: unexpected EOF`.
  - The QA agent viewed a full-page Playwright screenshot. Its next model request hung for about 9.5 minutes, then Moonshot reset the streaming connection (`ClientPayloadError`, `ConnectionResetError`, logged in `llm_relay._forward`). The harness itself said "network issue… please try again".
  - Up to that point, the backend and UI checks were passing.
  - As expected for pre-fix-3 code, the dev agents' notes writes were denied. This time both agents put their summaries inline instead of writing fallback files.
- **Fix 4 (uncommitted):** `RETRYABLE_MARKERS` gains "unexpected eof", "network issue", "connection reset" and "payload is not completed". 57/57 tests pass.
- Fixes 1–4 were merged into `main` through PR #1 (merge commit `0501e32`).
- **Run 5 (`9a159a77-…`, merged code): ALL CHECKS PASSED (live), in 23m52s.**
  - Both dev agents wrote `.agents/fe_output.md` and `.agents/be_output.md` directly, with **0 "Access denied"** events and 0 retries. **Fix 3 is confirmed live.**
  - QA passed on loop 1. The zip is 180K / 33 files, with no notes files or `.agents` inside. SHA256 matched, and `start_servers.sh` served 200 on the frontend, backend and `/api/`.
  - Fix 4 (stream-reset retry) wasn't triggered in this run; only the unit test covers it.
- **Fix 5 (PR #2):**
  - `LLMRelay` separates a per-chunk `read_timeout` (default **180s**; `NEXUS_RELAY_READ_TIMEOUT_SECONDS`, via `EngineConfig.relay_read_timeout`) from a total per-request cap (1800s, previously 900s for both).
  - A stalled stream is now cut after 3 minutes instead of 15. The harness sees an EOF, and fix 4 retries with a fresh agent.
  - Test `test_relay_cuts_stalled_stream_after_read_timeout`. **58/58 pass.**
- **Session 2 browser checks (Chrome, dev stack):**
  - Create-project modal → upload through the drop zone's file input → Save Draft: persisted, byte-identical to the fixture.
  - Zip download: SHA256 matches the DB.
  - Delete through the in-page ConfirmDialog: the DB rows, workspace and uploaded file are all removed. No console errors.
- **Run 6 (`8c50ba26-…`, "Asset Inventory", 55 files): FAILED at QA loop 3/3** after about 1h45m. The platform behaved correctly.
  - Loops 1–2 found real bugs, and the repairs fixed all of them (B1–B6, FE1).
  - Loop 3 found one new bug, F1: check-in returns 409 because the Team Lead's DDS contradicts itself. Its transition table has no `active → in_stock` edge, but its check-in spec requires one.
  - The bug was hidden until loop 3 because check-in first crashed on B2 (the audit TypeError). No loops were left to repair it.
- **Fix 6 (commit "Add \"Continue repair\"…" on `b_pbv_main`): "Continue repair" (resume) for failed runs.**
  - `POST /generate {"resume": true}` creates a `GenerationTask(resume=True)` (migration `0003`).
  - A resumed run keeps the workspace, skips plan and build, runs one repair cycle from the existing `.agents/qa_report.md`, then runs a fresh QA loop (1..max) and packages.
  - The request is refused (409 `resume_unavailable`) unless the project is FAILED, the DDS, manifest and QA report exist, and the requirement is unchanged. `engine.context.resume_problem` enforces this in both the view and the orchestrator.
  - `ProjectDetail.can_resume` drives a "Continue repair" button in Mission Control, next to "Start over".
  - `started_at` is now also set on TESTING.
  - **61/61 pass.** `nuxi typecheck` is clean. **Verified live on run 6** (see "Run 6 resumed" below).
- **Fix 7: the WebSocket history is sent in batches.** Run 6 has 2065 logs, so its one `history` message was 1.56 MB, over the 1 MiB Daphne/autobahn frame limit (`PayloadExceededError`). Mission Control then looped on "Connection lost. Reconnecting…".
  - `apps/realtime/consumers.py` now sends the history as several `history` messages of about 256 KB each (`history_batches`). The client already appends them.
  - **62/62 pass.**
- **Dev-stack gotcha:** a second `start_dev.sh` while an old one is still running fails silently. Its Daphne can't bind :8000, so the old backend keeps serving stale code, and Nuxt falls back to :3001. Two Celery workers also end up on the same queue, so a job can land on the old code.
  - **Fixed in `scripts/start_dev.sh`:** it now refuses to start while :8000, :3000 or a Nexus Celery worker are in use, and prints the stop command. It waits until Daphne listens on :8000, printing the log tail if it dies, and then watches every service. If any one exits, it says which and stops the stack. Verified live: preflight refusal, a clean start, and the watchdog on a killed worker.
- **Fix 8: the generated `start_servers.sh` adapts its ports** (`engine/packager/generator.py`). A downloaded app run while Nexus was up put Django on 127.0.0.1:8000, beside Daphne's `*:8000`, which macOS allows. Nuxt moved itself to :3001, but CORS still allowed only :3000, so the browser saw "Failed to fetch" even though the server logged 200s.
  - Default ports now move to the next free port. A port the user sets must be free.
  - CORS always includes the actual frontend origin, and `NUXT_PUBLIC_API_BASE` follows the actual backend port.
  - The script waits for both servers before saying "ready", and stops both if either exits.
  - `.env.example` leaves ports, CORS and the API base commented out.
  - Verified live on a copy of the Asset Inventory app (8001/3002 picked, CORS header correct, watchdog cleanup). **63/63 pass.** Apps packaged before this fix still have the old script.
- **Fix 9: repackaging.** `manage.py repackage <project_id>... | --all` rebuilds a completed project's zip and artifact row with the current delivery files, without rerunning agents (`orchestrator.repackage` / `build_package`). `write_support_files` now also refreshes `.env.example` and `README.md` when Nexus wrote them (matched by marker lines); files the agents wrote are left alone.
  - Run 6 was repackaged: its zip is now sha256 `58fcf4e6…`, and it includes the new `start_servers.sh`. **64/64 pass.**
- **Run 6 resumed ("Continue repair", live): COMPLETED.**
  - Task `e730e76d` (`resume=True`) resumed run 6 from its loop-3 QA report. It ran one repair cycle (fixing F1, the DDS `active → in_stock` contradiction), and the fresh QA loop **passed on loop 1**.
  - Timing: 09:55 → 10:17 UTC (about 22 min), 376 logs. Compare the original run: 2,065 logs over about 1h45m.
  - Then repackaged (fix 9): zip sha256 `58fcf4e6a064…`, 60 files, 212,937 bytes. The copy the user downloaded to `~/Downloads/nexus_project_asset-inventory.zip` has the identical sha256 and runs with the adaptive-ports `start_servers.sh`.
- **Git:** local `main` was reset to `origin/main` (dropping the stale handoff commit `b3a3ee0`). `b_pbv_main` is **kept** at the user's request.
  - Merged into `main`: PR #1 (`0501e32`), PR #2 (`78913cd`), PR #3 (`3456bc7`) and PR #4 (`d39da24`, fixes 6–9).
- **Dev stack:** restarted by the user at 17:58 (after fixes 8–9). It was verified as a single `start_dev.sh`, Daphne :8000, one Celery worker ("ready") and Nuxt :3000.
- **Login/register:** the user registered (`prapon@gmail.com`) and logged in through the browser UI themselves. My browser rules forbid me typing passwords.
- **Open items:**
  - The live fail-over after a stalled or reset model stream (fixes 4–5) is covered only by unit tests; a real stall can't be triggered on demand.
  - QA `run_command` is prompt-constrained only; there is no OS sandbox on macOS.
  - Idea: add a consistency check of the Team Lead's DDS, e.g. state-transition tables vs. endpoint specs. Run 6's last bug (F1) was a self-contradiction in the DDS that surfaced only in QA loop 3.
  - Housekeeping: old acceptance-run workspaces in `media/workspaces/` and `e2e-*@example.com` test users.

## Possible follow-ups
- QA `run_command` is prompt-constrained only; there is no OS sandbox on macOS.
- Git: all work is merged into `main` on the private origin through PRs #1–#4 (https://github.com/praponb/New_Nexus_Web/pulls?q=is%3Apr). `b_pbv_main` is kept as the working branch.

## Where everything is
- Approved plan: `docs/IMPLEMENTATION_PLAN.md` (a copy of `~/.claude/plans/pasted-content-id-cf92-please-read-rosy-pixel.md`).
- Spec: `NEXUS_DESIGN_DOCUMENT.md`. The original prompt is in `CLAUDE_CODE_PROMPT.md`.
