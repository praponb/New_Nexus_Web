"""Mock agent runner: a scripted, LLM-free stand-in for LiveAgentRunner.

It goes through the real orchestrator (phases, checks, QA loop, packaging) but each
agent turn replays a scripted stream and writes files from ``templates/todo_app``.
With ``NEXUS_MOCK_INJECT_FAULT=1`` the backend developer first writes a syntax error, so
the deterministic checks fail, QA reports FAIL and the repair cycle has to fix it.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from apps.projects.models import LogType

from .agents.base import AgentJob
from .context import (
    BE_OUTPUT_FILE,
    DDS_FILE,
    FE_OUTPUT_FILE,
    MANIFEST_FILE,
    QA_REPORT_FILE,
    REPAIR_PLAN_FILE,
    PipelineContext,
)

TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates" / "todo_app"
FAULT_FILE = "backend/api/views.py"
FAULT_SNIPPET = "\n\ndef broken_view(request)\n    return None  # missing colon: injected fault\n"


def template_files(prefix: str) -> list[str]:
    base = TEMPLATE_ROOT / prefix
    return sorted(p.relative_to(TEMPLATE_ROOT).as_posix() for p in base.rglob("*") if p.is_file())


def fault_injection_enabled() -> bool:
    return os.environ.get("NEXUS_MOCK_INJECT_FAULT", "").lower() in {"1", "true", "yes"}


class MockAgentRunner:
    def __init__(self, ctx: PipelineContext, delay: float | None = None):
        self.ctx = ctx
        self.delay = float(os.environ.get("NEXUS_MOCK_DELAY", "0.12")) if delay is None else delay
        self.inject_fault = fault_injection_enabled()
        self._fault_repaired = False

    async def run(self, job: AgentJob) -> str:
        handler = getattr(self, f"_{job.role}")
        return await handler(job)

    # ------------------------------------------------------------------ primitives
    async def _pause(self, factor: float = 1.0) -> None:
        if self.delay:
            await asyncio.sleep(self.delay * factor)

    async def _think(self, job: AgentJob, text: str) -> None:
        await self._pause()
        await self.ctx.sink.log(job.agent_name, LogType.THOUGHT, text)

    async def _say(self, job: AgentJob, text: str) -> str:
        await self._pause()
        await self.ctx.sink.log(job.agent_name, LogType.TEXT, text)
        return text

    async def _write(self, job: AgentJob, rel: str, content: str, server: str = "filesystem") -> None:
        target = self.ctx.path(rel)
        await self.ctx.sink.log(
            job.agent_name,
            LogType.TOOL_CALL,
            f"{server}.write_file → {rel}",
            {"tool": "write_file", "server": server, "args": {"path": str(target), "content": content[:2000]}},
        )
        await self._pause(0.5)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if rel.endswith(".sh"):
            target.chmod(0o755)
        await self.ctx.sink.file_created(job.agent_name, rel, "write_file")
        await self.ctx.sink.log(
            job.agent_name,
            LogType.TOOL_RESULT,
            f"Successfully wrote to {target}",
            {"tool": "write_file", "length": len(content)},
        )

    async def _copy_template(self, job: AgentJob, rel: str, server: str) -> None:
        content = (TEMPLATE_ROOT / rel).read_text(encoding="utf-8")
        if self.inject_fault and not self._fault_repaired and rel == FAULT_FILE:
            content += FAULT_SNIPPET
        await self._write(job, rel, content, server)

    # ------------------------------------------------------------------ roles
    async def _architect(self, job: AgentJob) -> str:
        words = len(self.ctx.requirement.split())
        headings = re.findall(r"^#+\s*(.+)$", self.ctx.requirement, flags=re.M)[:6]
        await self._think(job, f"Reading user_requirement.md ({words} words). Sections: {', '.join(headings) or 'none'}.")
        await self._think(job, "Core entity: Todo(title, description, completed, due_date). CRUD plus a status filter.")
        await self.ctx.sink.log(
            job.agent_name,
            LogType.TOOL_CALL,
            "thinking.sequentialthinking",
            {"tool": "sequentialthinking", "server": "thinking", "args": {"thought": "Plan API before UI."}},
        )
        await self._pause()
        await self.ctx.sink.log(job.agent_name, LogType.TOOL_RESULT, '{"thoughtNumber": 1, "nextThoughtNeeded": false}')
        await self._think(job, "Designing REST contract: /api/todos/ (GET, POST), /api/todos/{id}/ (GET, PATCH, DELETE).")
        await self._write(job, DDS_FILE, self._dds())
        await self._write(job, MANIFEST_FILE, json.dumps(self._manifest(), indent=2))
        return await self._say(job, "Design complete: 1 entity, 5 endpoints, 1 page. Handing off to the developers.")

    async def _frontend(self, job: AgentJob) -> str:
        files = template_files("frontend")
        await self._think(job, "Scaffolding a Nuxt 3 SPA with Tailwind and a Pinia store for todos.")
        for rel in files:
            await self._copy_template(job, rel, "filesystem-frontend")
        await self._write(job, FE_OUTPUT_FILE, "# Frontend output\n\n" + "\n".join(f"- `{f}`" for f in files) + "\n")
        return await self._say(job, f"Frontend complete: {len(files)} files.")

    async def _backend(self, job: AgentJob) -> str:
        files = template_files("backend")
        await self._think(job, "Building Django 5 + DRF: Todo model, serializer with validation, ModelViewSet, router.")
        for rel in files:
            await self._copy_template(job, rel, "filesystem-backend")
        await self._write(job, BE_OUTPUT_FILE, "# Backend output\n\n" + "\n".join(f"- `{f}`" for f in files) + "\n")
        return await self._say(job, f"Backend complete: {len(files)} files.")

    async def _qa(self, job: AgentJob) -> str:
        iteration = job.extra.get("iteration", 1)
        checks_ok = job.extra.get("checks_ok", True)
        summary = job.extra.get("checks_summary", "")
        await self._think(job, f"QA loop {iteration}: reviewing deterministic check results and auditing endpoints.")
        await self.ctx.sink.log(
            job.agent_name,
            LogType.TOOL_CALL,
            "playwright.browser_navigate → /",
            {"tool": "browser_navigate", "server": "playwright", "args": {"url": f"http://127.0.0.1:{self.ctx.qa_frontend_port}/"}},
        )
        await self._pause()
        await self.ctx.sink.log(job.agent_name, LogType.TOOL_RESULT, "Page title: Todo — 0 console errors (mock)")
        if checks_ok:
            report = (
                "STATUS: PASS\n\n# QA report (iteration {i})\n\n- [x] Deterministic checks passed\n"
                "- [x] CRUD endpoints respond\n- [x] Todo page renders and adds items\n"
            ).format(i=iteration)
        else:
            report = (
                f"STATUS: FAIL\n\n# QA report (iteration {iteration})\n\n"
                f"Deterministic checks failed:\n\n{summary}\n\nSuspected cause: syntax error in `{FAULT_FILE}`.\n"
            )
        await self._write(job, QA_REPORT_FILE, report)
        return await self._say(job, report.splitlines()[0])

    async def _architect_repair(self, job: AgentJob) -> str:
        await self._think(job, "QA failure traced to a compile error in the backend views module.")
        plan = (
            f"# Repair plan (iteration {job.extra.get('iteration')})\n\n## Backend fixes\n\n"
            f"- `{FAULT_FILE}`: remove the malformed `broken_view` definition (missing colon).\n\n"
            "## Frontend fixes\n\nNone.\n"
        )
        await self._write(job, REPAIR_PLAN_FILE, plan)
        return await self._say(job, "Repair plan written.")

    async def _backend_repair(self, job: AgentJob) -> str:
        if self.inject_fault and not self._fault_repaired:
            self._fault_repaired = True
            await self._think(job, f"Applying surgical fix to {FAULT_FILE}.")
            await self._copy_template(job, FAULT_FILE, "filesystem-backend")
            return await self._say(job, "Backend fix applied.")
        return await self._say(job, "No backend changes needed.")

    async def _frontend_repair(self, job: AgentJob) -> str:
        return await self._say(job, "No frontend changes needed.")

    # ------------------------------------------------------------------ documents
    def _dds(self) -> str:
        return f"""# Design Doc Spec: {self.ctx.project_name}

## Overview
A task manager where users create, edit, complete, filter and delete todos.

## Data model
- **Todo**: `title` CharField(200, required), `description` TextField(blank), `completed` Boolean(default False),
  `due_date` Date(nullable), `created_at`, `updated_at`. Ordering: incomplete first, newest first.

## REST API (JSON, no auth)
| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check → `{{"status": "ok"}}` |
| GET | `/api/todos/?status=all\\|active\\|completed&search=` | List todos |
| POST | `/api/todos/` | Create `{{title, description?, due_date?}}` → 201 |
| GET | `/api/todos/{{id}}/` | Retrieve |
| PATCH | `/api/todos/{{id}}/` | Update any field |
| DELETE | `/api/todos/{{id}}/` | Delete → 204 |

## Frontend
- `/` — list with add form, status filter chips, inline edit, toggle and delete.
- Pinia store `useTodoStore` wraps every endpoint; API base from `runtimeConfig.public.apiBase`.

## Acceptance checks
- `manage.py check` and `makemigrations --check` pass; CRUD works via curl; the page adds a todo.

## Consistency review
- State machines: consistent (`completed` is a plain boolean; no transition table).
- Fields, endpoints, errors, manifest: consistent.
"""

    def _manifest(self) -> dict:
        files = [{"path": p, "owner": "backend", "purpose": ""} for p in template_files("backend")]
        files += [{"path": p, "owner": "frontend", "purpose": ""} for p in template_files("frontend")]
        return {
            "app_name": "todo",
            "backend_package": "todo_backend",
            "entities": [{"name": "Todo", "fields": ["title", "description", "completed", "due_date"]}],
            "api_endpoints": [
                {"method": "GET", "path": "/api/todos/"},
                {"method": "POST", "path": "/api/todos/"},
                {"method": "GET", "path": "/api/todos/{id}/"},
                {"method": "PATCH", "path": "/api/todos/{id}/"},
                {"method": "DELETE", "path": "/api/todos/{id}/"},
            ],
            "pages": [{"route": "/", "file": "frontend/pages/index.vue"}],
            "files": files,
        }
