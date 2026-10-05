# Nexus User Guide

A practical handbook for running, testing and maintaining Nexus: the important commands, how to use
the app, and every known problem found so far (as of 2026-10-05), with its cause and solution.

> Paths are relative to the repo root, `/Users/praponb/GitHub/New_Nexus_Web`, unless noted.
> Deep implementation notes and the full run history are in `docs/PROGRESS.md`.
> The spec is `NEXUS_DESIGN_DOCUMENT.md`.

---

## 1. At a glance

| What | Where |
|---|---|
| Nexus web app (frontend) | http://localhost:3000 |
| Backend API + WebSockets (Daphne) | http://localhost:8000 (`/api/v1/…`, `ws://localhost:8000/ws/projects/{id}/logs/`) |
| PostgreSQL 16 (Docker `nexus-postgres`) | `localhost:5433` (db / user / password: `nexus`) |
| Redis 7 (Docker `nexus-redis`) | `localhost:6379` |
| Settings and secrets | `.env` (template: `.env.example`) |
| Dev-stack logs | `logs/backend.log`, `logs/celery.log`, `logs/frontend.log` |
| Generated projects | `media/workspaces/{user_id}/{project_id}/`: `generated/` (the app plus `.agents/` notes) and `packages/` (the zip) |
| LLM | Moonshot `kimi-k3` (`https://api.moonshot.ai/v1`), key in `.env` → `MODEL_API_KEY` |
| GitHub | https://github.com/praponb/New_Nexus_Web (private). Work on `b_pbv_main`, merge to `main` by PR |
| Production | https://nexus.praponb.com: Docker on the Ubuntu server 192.168.1.49, `~/nexus` (see section 11) |

**How a generation works:**
1. The **Team Lead** writes the design (`.agents/dds_output.md` and `.agents/manifest.json`) and reviews it for contradictions.
2. The **Frontend Dev** and **Backend Dev** build in parallel.
3. **QA** runs the real checks plus curl and Playwright tests, in up to 3 repair loops.
4. The **packager** zips the app with `start_servers.sh`, `README.md` and `.env.example`.

---

## 2. Everyday commands

### Start the dev stack
```bash
cd /Users/praponb/GitHub/New_Nexus_Web
./scripts/start_dev.sh            # Daphne :8000 + Celery worker + Nuxt :3000 (add --no-frontend for API only)
```
Wait for **`Nexus is up: backend http://localhost:8000, frontend http://localhost:3000`**.
The script starts Docker Postgres and Redis if Docker is running, applies migrations, and watches every service. If one exits, it says which and stops the rest.

### Stop / restart the dev stack
- **Stop:** press **Ctrl+C** in the terminal running `start_dev.sh`.
- **If you can't find that terminal:**
  ```bash
  pkill -f start_dev.sh; pkill -f 'daphne .*nexus_backend'; pkill -f 'celery -A engine.celery_app'
  ```
- **Restart** = stop, then `./scripts/start_dev.sh` again, from the repo root.
- There is **no `stop_dev.sh`**. `start_dev.sh` is the only dev-stack script; it stops everything on Ctrl+C (see P26).
- If `start_dev.sh` prints "Another Nexus stack looks alive", the old stack is still running. Run the `pkill` line above and start it again.

> **Always restart after pulling or merging code changes.** The Celery worker loads the engine code once at start-up. A worker that's still running keeps generating with the **old** prompts and packaging.

### Check that the stack is healthy
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/                 # expect 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/v1/auth/me/  # expect 401 (= up, not logged in)
grep "ready." logs/celery.log | tail -1                                          # worker ready
ps -eo pid,lstart,command | grep -E "start_dev.sh|daphne .*nexus|celery -A engine|nuxt dev" | grep -v grep
docker ps --format '{{.Names}} {{.Status}}'                                      # nexus-postgres / nexus-redis healthy
```
The `lstart` column shows when the worker started. Compare it with your last merge time to know whether it has the latest code.
There is no `/api/health/` route, and `http://localhost:8000/` returns 404 on the Nexus backend. A **401** from `/api/v1/auth/me/` is the "backend is up" signal (see P27).

### First-time setup (a new machine)
```bash
./scripts/setup_environment.sh    # Docker Postgres+Redis, .venv (Python 3.12 via uv), npm install, migrations, Playwright Chromium
# then put your Moonshot key in .env → MODEL_API_KEY=...
```

---

## 3. Using the app

1. **Register / log in** at http://localhost:3000/auth/register or `/auth/login`. The session uses JWTs: a 15-minute access token that refreshes automatically, and a 7-day refresh token.
2. **Dashboard → "+ New WebApp Project"**: give it a name and description.
3. **Requirement:** either
   - **Upload tab:** drop or choose `user_requirement.md` (Markdown only, up to 5 MB, at least 20 words), or
   - **Editor tab:** write it, or start from a preset (E-Commerce Store, SaaS Dashboard, Social Feed, Custom).

   Press **Save Draft**.
4. **Start Autonomous Generation.** This **spends Moonshot credits** in live mode. Mission Control shows:
   - the phase stepper
   - the live agent stream (🧠 thoughts, 🔧 tool calls, ✅ results), filterable by agent
   - the file tree as files appear

   A typical run takes about 25–40 minutes. Large apps can take 1–2 hours.
5. **If the run FAILS** (for example, QA still failing after 3 loops), Mission Control offers:
   - **Continue repair**: keeps the generated code, runs one repair cycle from the last QA report, then a fresh QA loop and packaging. It's usually much faster and cheaper. It's available only if the project FAILED, the design, manifest and QA report exist, and the requirement is unchanged.
   - **Start over**: regenerates from scratch.
6. **Ready page:** stats, a code explorer, the rendered README, and **Download Complete Source Code (.ZIP)**.

### Running a downloaded app
```bash
unzip nexus_project_<name>.zip && cd <name>_generated
./start_servers.sh                # creates backend/.venv, npm install, migrates, starts both servers
```
- If ports 8000/3000 are busy (for example, Nexus itself is running), the script **picks the next free ports** and prints them. CORS and the frontend's API base follow automatically.
- To force ports: `BACKEND_PORT=8100 FRONTEND_PORT=3100 ./start_servers.sh`. Forced ports must be free.
- Ctrl+C stops both servers.

---

## 4. Testing commands

```bash
# Backend unit + integration tests (SQLite, in-memory channels): 66 pass as of 2026-09-25
cd backend && ../.venv/bin/python -m pytest -q

# Frontend type check + production build (stop the dev stack first: see problem P16)
cd frontend && npx nuxi typecheck && npm run build

# End-to-end acceptance, mock engine (free, a few minutes), with a deliberate bug to exercise self-correction
./scripts/test_agent_pipeline.sh --mode mock --inject-fault

# End-to-end acceptance against kimi-k3 (about 25–40 min, SPENDS CREDITS)
./scripts/test_agent_pipeline.sh --mode live --timeout 5400

# Re-check an already generated project without regenerating it
./scripts/test_agent_pipeline.sh --verify-only <project_id>
```
`test_agent_pipeline.sh` runs its **own private** Daphne and Celery worker (free port, private queue), so it can run alongside the dev stack. It does the following:
1. registers a throwaway `e2e-…@example.com` user
2. uploads `scripts/fixtures/user_requirement.md`
3. streams the WebSocket
4. checks the QA report, the SHA256 of the download and the zip contents
5. unzips the archive, runs `start_servers.sh` and waits for HTTP 200s

On failure it keeps its logs in `$TMPDIR/nexus-e2e-XXXX/` (`celery.log`, `daphne.log`, `ws.log`).

Other options: `--skip-startup` (don't run the generated app) and `--requirement FILE`.

Watch any project's live stream from a terminal:
```bash
.venv/bin/python scripts/ws_watch.py --project <uuid> --token <access-jwt> [--require THOUGHT,TOOL_CALL]
```

---

## 5. Maintenance commands

### Inspect a project from the shell
```bash
cd backend && ../.venv/bin/python manage.py shell -c "
from apps.projects.models import Project
p = Project.objects.get(id='<project_id>'); t = p.latest_task()
print(p.status, t.current_phase, t.progress_percentage, 'qa', t.qa_iterations, p.error_message)"
```
- A project's agent notes are in `media/workspaces/*/<project_id>/generated/.agents/`: `dds_output.md`, `manifest.json`, `fe_output.md`, `be_output.md`, `qa_report.md` and `repair_plan.md`.
- Its agent sessions are in `…/.sessions/`.

### Rebuild zips with the latest delivery files (no agents, no credits)
```bash
cd backend && ../.venv/bin/python manage.py repackage <project_id> [<project_id> ...]
cd backend && ../.venv/bin/python manage.py repackage --all        # every COMPLETED project
```
Use this after changes to `start_servers.sh`, `README.md` or `.env.example` generation, so older projects get them too. Files the agents wrote are never overwritten.

### Clean up test data (users/projects created by test runs)
```bash
.venv/bin/python scripts/cleanup_test_data.py                       # DRY RUN: lists what would go
.venv/bin/python scripts/cleanup_test_data.py --yes                 # really delete
.venv/bin/python scripts/cleanup_test_data.py --yes --include-old-test-accounts
```
- It deletes every `e2e-<n>-<n>@example.com` user with their projects, workspaces, zips and uploaded files, plus the kept `$TMPDIR/nexus-e2e-*` log folders.
- `--include-old-test-accounts` also removes `smoke14225`, `celery-smoke`, `ws4045` and `ui-demo7896` (`@example.com`).
- **`prapon@gmail.com` is never touched.**
- A successful run starts with `DELETING: …` and ends with `done.`. If it says `DRY RUN`, `--yes` was missing.
- **Verify afterwards** with a plain dry run: it should print `DRY RUN (add --yes to delete): 0 user(s)` and list no log dirs. Check the size with `du -sh media/workspaces`.
- On 2026-09-25 this removed the 8 e2e users and the workspaces of live runs 1–5; `media/workspaces` went from 4.5 GB to 929 MB. The four older test accounts were not removed (they need `--include-old-test-accounts`).

### Database migrations
```bash
cd backend && ../.venv/bin/python manage.py makemigrations && ../.venv/bin/python manage.py migrate
cd backend && ../.venv/bin/python manage.py showmigrations projects
```

---

## 6. Configuration (`.env`)

| Setting | Default | Meaning |
|---|---|---|
| `MODEL_NAME` / `MODEL_API_BASE` / `MODEL_API_KEY` | `kimi-k3` / Moonshot | The LLM. Nexus is Moonshot-only |
| `MODEL_REASONING_EFFORT` | `high` | Passed through to the model |
| `NEXUS_ENGINE_MODE` | `live` in `.env` | `live` = real agents (credits); `mock` = scripted, free (tests, demos) |
| `NEXUS_MAX_QA_ITERATIONS` | `3` | QA/repair loops before FAILED |
| `NEXUS_QA_CHECKS` | `full` (live) / `fast` (mock) | `off` / `fast` / `full` deterministic checks before each QA turn |
| `NEXUS_AGENT_TIMEOUT_SECONDS` | `2700` | Max time for one agent turn |
| `NEXUS_RETRY_ATTEMPTS` / `NEXUS_RETRY_BACKOFF_SECONDS` | `4` / `70` | Retries with a fresh agent (backoff 70s × 2ⁿ) on rate limits, disconnects, stream resets |
| `NEXUS_RELAY_READ_TIMEOUT_SECONDS` | `180` | A model stream silent this long is cut and retried |
| `NEXUS_CELERY_QUEUE` | `nexus` | Queue the API sends to and the worker consumes |
| `NEXUS_MONTHLY_GENERATION_QUOTA` | `25` | Generations per user per month |
| `NEXUS_MOCK_DELAY` / `NEXUS_MOCK_INJECT_FAULT` | `0.12` / `0` | Mock pacing / inject a bug to test repair |
| `DB_ENGINE` + `POSTGRES_*` | `postgres`, port `5433` | Anything but `postgres` uses SQLite |
| `REDIS_URL` / `CHANNEL_LAYER` | `redis://localhost:6379/0` / `redis` | `memory` only for single-process dev |

Secrets (`MODEL_API_KEY`, `POSTGRES_*`, …) are **scrubbed from the agents' environment**, so the QA shell and generated apps never see them (see P11).

---

## 7. Git workflow

- Develop on **`b_pbv_main`**, and **keep this branch** after merges. Merge into **`main`** through a PR.
```bash
git checkout b_pbv_main
cd backend && ../.venv/bin/python -m pytest -q && cd ..          # tests first
git add <files> && git commit -m "…" && git push origin b_pbv_main
gh pr create --base main --head b_pbv_main --title "…" --body "…"
gh pr merge <N> --merge
git fetch origin && git branch -f main origin/main               # sync local main (main isn't checked out)
```
- PRs #1–#9 were merged on 2026-09-25 (#9 added this guide's last updates). The repo is private.
- A docs-only merge (for example, PRs #7 and #8) doesn't need a dev-stack restart. A merge that touches `backend/engine/` or the apps does (P9).
- If `git fetch origin main:main` is rejected as non-fast-forward, local `main` has commits that GitHub doesn't. Look at them (`git log origin/main..main`) before resetting it.

---

## 8. Known problems and solutions

Status: ✅ fixed · 🔧 workaround · ⚠️ open.

### Generation pipeline

**P1 ✅ Dev agents can't write their notes to `.agents/` ("Access denied — path outside allowed directories").**
- **Cause:** `@modelcontextprotocol/server-filesystem` implements the MCP *roots* protocol. When the client advertises roots, the server **replaces** its command-line directories with them. The Antigravity harness advertises each agent's `workspaces`, and the dev agents' workspace was only `frontend/` or `backend/`. That also silently re-rooted a separate "agents-notes" server.
- **Fix:** `build_config` adds `generated/.agents` to `workspaces`. Confirmed live in run 5 (0 denials).
- **Lesson:** scope MCP filesystem access through `workspaces`, not server arguments.

**P2 ✅ One agent failure crashes the whole run ("Harness process exited unexpectedly (WS close code 1006)").**
- **Cause:** the runner only retried rate-limit errors.
- **Fix:** harness drops are retryable. The retry uses a fresh agent, and its prompt says "finish the files already on disk; don't start over".

**P3 ✅ QA agent fails with "AntigravityExecutionError: unexpected EOF" / "network issue".**
- **Cause:** Moonshot reset a streaming response (`ClientPayloadError`, `ConnectionResetError`) after a request hung for about 9.5 minutes.
- **Fix:** these errors are retryable (fix 4).

**P4 ✅ A stalled model response blocks an agent for up to 15 minutes.**
- **Fix:** the relay cuts a stream after **180 s of silence** (`NEXUS_RELAY_READ_TIMEOUT_SECONDS`), then P3's retry takes over.
- The total per-request cap is 30 minutes, so long answers aren't cut off.
- ⚠️ Not yet seen live; covered by unit tests only.

**P5 ✅/🔧 A run fails after 3 QA loops although each loop fixed real bugs.**
- **Cause:** bugs can hide behind others. In run 6, the last bug (F1) only appeared once an earlier crash was fixed.
- **Solution:** press **Continue repair** in Mission Control (or `POST /api/v1/projects/{id}/generate/ {"resume": true}`). Run 6 finished this way in 22 minutes.

**P6 ✅ The design contradicts itself** (run 6: check-in needed an `active → in_stock` transition that the design's own table forbade), and QA finds it only late.
- **Fix:** the Team Lead must run a **consistency review** and append `## Consistency review` to the DDS.
- A structural check then logs **"Design check: N warning(s)"** in Mission Control. These are advisory only: missing review, bad JSON, duplicate files, owner mismatch, page not in the file list, endpoints outside `/api/…/`.
- ⚠️ Not yet seen in a live run.

**P7 ✅ Generated code with `\"` inside Vue template attributes breaks `nuxi build` (a Nuxt 500 page).**
- The QA loop catches and repairs this automatically (seen live in run 3).

**P8 ✅ Agent notes (`fe_output.md`, `be_output.md`) end up inside the zip.**
- **Fix:** stray or fallback notes are moved into `.agents/` before QA, and `.agents` is never zipped.

### Dev stack

**P9 ✅ After a code change, generation still behaves like the old code.**
- **Cause:** an old worker (or a whole old stack) was still running. A second `start_dev.sh` couldn't bind :8000, so the old backend kept serving, and Nuxt silently moved to :3001.
- **Fix:** `start_dev.sh` now **refuses to start** while :8000, :3000 or a Nexus worker is in use, and prints the stop command. **Always restart after merges** (section 2).

**P10 ✅ Mission Control loops on "Connection lost. Reconnecting…" for big runs.**
- **Cause:** one WebSocket `history` message over Daphne's 1 MiB frame limit (run 6 had 2,065 logs, 1.56 MB).
- **Fix:** history is sent in about 256 KB batches.

**P11 ✅ The QA shell could see `MODEL_API_KEY`, and generated apps pointed at Nexus's own Postgres (`POSTGRES_DB`).**
- **Fix:** `scrub_process_env()` removes these at pipeline start. The engine reads them via `env_value()`.

**P12 ✅ Idle WebSockets die with 1011 "Timeout reading".**
- **Cause:** redis-py 8 defaults `socket_timeout=5`, equal to channels_redis's block time.
- **Fix:** the channel layer uses `socket_timeout: 30`.

**P13 ✅ Postgres rejects saving the zip path (the SQLite dev database never did).**
- **Fix:** the FileField `max_length` was raised to 500 (migration `0002`).

**P14 🔧 `npm install` in `frontend/` stalls on registry fetches.**
- **Workaround:** `cd frontend && npm install --no-fund --no-audit --fetch-timeout=60000 --fetch-retries=5`

**P15 🔧 Python version.**
- The system `python3` is 3.14. **Use `.venv/bin/python` (3.12)**, created with `uv venv -p 3.12`.
- Install with `uv pip install -p .venv/bin/python -r backend/requirements.txt`.

**P16 🔧 `npm run build` fails with "Another Nuxt dev is already running".**
- Stop the dev stack (or at least Nuxt) before a production build.

**P17 🔧 macOS details.**
- There is no `timeout` command.
- Nuxt dev binds `[::1]:3000`, so use `http://localhost:3000`, not `127.0.0.1`.
- Django may bind `127.0.0.1:8000` next to Daphne's `*:8000` without an error (the cause of P18).

### Generated (downloaded) apps

**P18 ✅ A downloaded app shows "Failed to fetch" even though its server logs 200s.**
- **Cause:** it was started while Nexus was running. Nuxt moved to :3001, but CORS only allowed :3000.
- **Fix:** `start_servers.sh` now picks free ports and keeps CORS and the API base in step.
- **Zips built before this fix still have the old script:** run `manage.py repackage <id>` and download again.

### Access tokens and auth

**P19 🔧 A long script or run returns 401 partway through.**
- The access token lasts 15 minutes. The web app refreshes automatically. Scripts must log in again (`test_agent_pipeline.sh` does this after the stream ends).

### Working with Claude Code (the assistant)

**P20 🔧 Claude can't type passwords or create accounts in the browser.**
- Its browser-safety rules forbid it, even for local test apps. Test login/register yourself.
- Claude can do upload, download and delete tests. It asks before downloading and names the file.

**P21 🔧 Claude's permission system may block bulk deletes.**
- If it does, Claude doesn't retry another way. It gives you a script to run yourself (for example, `scripts/cleanup_test_data.py`). Dry run is the default; add `--yes`.

**P22 🔧 "API Error: Your computer went to sleep mid-response".**
- Ask Claude to redo. It re-checks the repo state first.
- Background runs usually survive sleep, but check them afterwards (section 2 health check).

**P23 🔧 `! command` in the Claude prompt vs. your own terminal.**
- `!` runs the command in Claude's session, and its output appears in the chat.
- If a result can't be seen or verified, run the command in your own terminal and paste the output.

**P24 🔧 Session handoff.** When starting a new Claude session:
- say "continue from the last save"
- Claude reads `docs/PROGRESS.md` ("Resume here") and its memory notes
- keep that file updated through PRs

**P25 🔧 "I ran it" but nothing changed.**
- Seen twice with the cleanup script: it was run without `--yes` (a dry run) or from another folder, so nothing was deleted. The same happened once with the restart (the worker's start time hadn't changed).
- **Solution:** run commands from the repo root and read the last line of output (`done.` for the cleanup, "Nexus is up" for the stack). Ask Claude to verify: it checks the real state (the dry run's user count, the worker's start time, `git log origin/main`) before closing an item.

**P26 🔧 Claude named a script that doesn't exist (`./scripts/stop_dev.sh`).**
- **Cause:** Claude answered from memory instead of checking the `scripts/` folder.
- **Solution:** the real stop is Ctrl+C or the `pkill` line in section 2. If a command says "no such file", `ls scripts/` and tell Claude; this guide lists only commands that were checked against the repo.

**P27 🔧 A backend health check returns 404.**
- `/api/health/` and `/` don't exist on the Nexus backend. Use `curl http://localhost:8000/api/v1/auth/me/` and expect **401**.
- (Generated apps are different: their backend's `GET /` returns `{"status": "ok"}`.)

---

## 9. Live run history (2026-09-25)

| Run | Project | Result | What it taught us |
|---|---|---|---|
| 1 | `9ddc5158` | ✅ PASS (QA loop 1) | First live acceptance; led to env scrubbing (P11) and the notes fixes |
| 2 | `e39016e8` | ❌ FAILED at 25% | Notes write denied → harness crash (P1, P2) |
| 3 | `b8f0e944` | ✅ PASS (QA loop 2) | First **live self-correction** (P7); notes still denied (P1) |
| 4 | `2db677fd` | ❌ FAILED in QA | Moonshot stream reset (P3, P4); led to the real P1 diagnosis |
| 5 | `9a159a77` | ✅ PASS (loop 1, 24 min) | All fixes merged; notes written to `.agents/` with 0 denials; clean zip |
| 6 | `8c50ba26` "Asset Inventory" (55 files) | ❌ → ✅ | Failed at loop 3/3 after 1h45m (F1, P5/P6). **Continue repair** completed it in 22 min, then repackaged (P18) |

Runs 1–5 belonged to throwaway `e2e-…` users, so the cleanup deleted their projects and workspaces; `--verify-only` no longer works for them. Only run 6 (owned by `prapon@gmail.com`) remains.

---

## 10. Open items / limitations

Status at the end of 2026-10-05: Nexus is deployed at **https://nexus.praponb.com** (section 11) and all work is merged into `main` (PRs #1–#11, `aaa1d1d`). Your data was copied to the server, and you logged in there and browsed Asset Inventory. Nothing is broken or waiting.

Your choices, postponed to a later session:
1. **Switch production to live mode:** set `NEXUS_ENGINE_MODE=live` in `~/nexus/.env.prod`, then `docker compose -f docker-compose.prod.yml up -d web worker`. Generations then spend Moonshot credits.
2. **Server cleanup (optional):** `~/nexus/media-import/`, `~/nexus/media-import.dump`, and the orphan smoke-test workspace `workspaces/cfa725f7-…` in the `nexus_media` volume.
3. **Make `~/nexus` a git checkout (optional):** it needs a read-only GitHub deploy key, since the repo is private. Until then, `~/nexus` is an rsync copy of the repo matching `main` `aaa1d1d`, and updates are rsync + `up -d --build`.

On the Mac:
- The repo's **`.venv` is missing**, so `start_dev.sh` and the pytest commands fail until you run `./scripts/setup_environment.sh`. The tests also pass inside the production image (66/66 on 2026-10-05).
- The Mac dev database now holds only prapon@gmail.com and Asset Inventory. The four old test accounts are gone, so `--include-old-test-accounts` has nothing left to do.

Limitations:
- ⚠️ **QA sandbox:** the QA agent's `run_command` is limited only by its prompt. In production it runs inside the `worker` container (non-root, 4 CPU / 6 GB cap, only the `media` volume mounted), which is better isolation than on macOS, but it is still not a real sandbox. Keep Cloudflare Access on, so only you can start generations.
- ⚠️ **Not yet seen live:** the stall fail-over (P4) and the design consistency review (P6). Watch the next live generation for a `## Consistency review` section in `.agents/dds_output.md` and any "Design check" message.

---

## 11. Production deployment (https://nexus.praponb.com)

Nexus runs in Docker on the home Ubuntu server **192.168.1.49** (`ssh prapon@192.168.1.49`) in **`~/nexus`**, as the compose project `nexus` defined in `docker-compose.prod.yml`. The server also hosts other apps (inventory, twin, sql2pyspark, batch2stream, ollama); Nexus shares none of their ports or containers.

| Piece | What it is |
|---|---|
| `frontend` | nginx (`deploy/frontend.Dockerfile`, `deploy/nginx.conf`): the generated Nuxt SPA, plus a proxy of `/api/`, `/admin/`, `/ws/` → `web`. The **only host port: `127.0.0.1:8090`** |
| `web` | Daphne (`deploy/backend.Dockerfile`, `deploy/entrypoint-web.sh`): migrates and runs collectstatic on every start |
| `worker` | Celery, same image (Python 3.12 + Node 20 + Playwright Chromium for QA). Capped at 4 CPUs / 6 GB |
| `postgres`, `redis` | Internal only, with volumes `nexus_pgdata` and `nexus_redisdata` |
| Volumes `nexus_media`, `nexus_static` | Workspaces, uploads, zips; Django admin assets |
| Settings | `~/nexus/.env.prod` (mode 600; template `.env.prod.example`) |
| Public URL | The host's systemd `cloudflared` (tunnel `4fc26704…`, `/etc/cloudflared/config.yml`) routes `nexus.praponb.com` → `http://localhost:8090`. Cloudflare provides HTTPS |

### First-time setup (done 2026-10-05)
1. Copy the code to `~/nexus` on the server. Create `.env.prod` from `.env.prod.example` with a new `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`, then `chmod 600 .env.prod`.
2. `docker compose -f docker-compose.prod.yml up -d --build`. The first build takes about 5 minutes, and the backend image is ~2.6 GB because of Node and Chromium.
3. Check on the server: `curl http://127.0.0.1:8090/api/v1/auth/me/` → 401, `/api/v1/health/` → 200.
4. Public route (needs sudo, so the user does it):
   - add the rule below to `/etc/cloudflared/config.yml`, above the catch-all `- service: http_status:404`:
     ```yaml
     - hostname: nexus.praponb.com
       service: http://localhost:8090
     ```
   - `sudo systemctl restart cloudflared`. It takes about **90 s**: the old process ignores SIGTERM until systemd kills it, and sql2pyspark, inventory and nexus are offline meanwhile. The command returns only when the restart is done. Check with `systemctl is-active cloudflared`.
   - in the Cloudflare dashboard, add a DNS CNAME `nexus` → `4fc26704-4a77-4a7e-a7bc-30861b3802cb.cfargotunnel.com` (proxied).
5. ✅ Done 2026-10-05: Cloudflare Access (Zero Trust → Access → Applications, email one-time PIN) in front of `nexus.praponb.com`. Otherwise anyone can register, spend Moonshot credits, and run generated code on the server.

### Everyday commands (on the server, in `~/nexus`)
```bash
docker compose -f docker-compose.prod.yml ps                        # status / health
docker compose -f docker-compose.prod.yml logs -f --tail 100 web worker
docker compose -f docker-compose.prod.yml restart worker
docker compose -f docker-compose.prod.yml up -d --build             # after code changes
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/api/v1/auth/me/   # 401 = up
```
Changing `.env.prod` needs `up -d` (not `restart`) so the containers pick up the new values. `NUXT_PUBLIC_*` are baked into the frontend image at build time (defaults: `https://` / `wss://nexus.praponb.com`).

### Backup
```bash
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U nexus -Fc nexus > nexus-$(date +%F).dump
docker run --rm -v nexus_media:/m -v "$PWD":/b alpine tar czf /b/nexus-media-$(date +%F).tgz -C /m .
```

### Data copied from the Mac (2026-10-05)
- `pg_dump -Fc` of the Mac DB was restored with `pg_restore --clean --if-exists --no-owner`. It brought prapon@gmail.com, the Asset Inventory project (`8c50ba26`) and 2,441 log rows.
- `media/` was copied into the `nexus_media` volume, owned by uid 1000, **without** the macOS-built caches (`node_modules`, `.qa/venv`, `.qa/npm-cache`, `.nuxt`, `.output`). Nexus rebuilds those on Linux when needed.
- `Project.workspace_dir` stores an absolute path, so it was rewritten after the restore:
  `update projects_project set workspace_dir = replace(workspace_dir, '/Users/praponb/GitHub/New_Nexus_Web/media', '/app/media');`
- The restore replaced the two `e2e-deploy-…@example.com` smoke-test users. Their workspace `nexus_media:/workspaces/cfa725f7-…` is now orphaned and can be removed.

### Production problems
**D1 ✅ The site returns 502 after `web` is recreated.** nginx resolved `web` once at startup and kept the old container IP. Fix: `deploy/nginx.conf` now resolves `web` through Docker DNS (`resolver 127.0.0.11`, `proxy_pass $backend`).

**D2 ✅ Page paths without a trailing slash redirected to `http://`.** nginx only sees plain HTTP behind the tunnel, so its absolute redirects used `http://nexus.praponb.com/...`. Fix: `absolute_redirect off;` sends relative `Location` headers.

**D3 🔧 `sudo systemctl restart cloudflared` takes ~90 s** and takes every tunnel site offline meanwhile (see step 4 above).

**D4 🔧 The browser says `DNS_PROBE_FINISHED_NXDOMAIN` for a new hostname.** The home Pi-hole (192.168.1.36) cached the "doesn't exist" answer from before the record was created (Cloudflare's negative TTL is 30 min). Fix: Pi-hole → Tools → Restart DNS resolver (or `pihole restartdns`), `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` on the Mac, and `chrome://net-internals/#dns` → Clear host cache.
