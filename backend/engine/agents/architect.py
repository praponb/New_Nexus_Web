"""Team Lead agent: requirement → design doc spec (DDS) + file manifest; also plans repairs."""

from __future__ import annotations

from ..context import DDS_FILE, MANIFEST_FILE, QA_REPORT_FILE, REPAIR_PLAN_FILE, REQUIREMENT_FILE, PipelineContext
from ..mcp import registry
from .base import SHARED_RULES, TEAM_LEAD, AgentJob, build_config

AGENT_NAME = TEAM_LEAD

SYSTEM_PROMPT = """\
You are the Team Lead and System Architect of an autonomous software team. You turn a product
requirement into a precise, buildable design for a full-stack web app:
- Backend: Django 5 + Django REST Framework, project package `<app>_backend`, one app named `api`.
- Frontend: Nuxt 3 (Vue 3 `<script setup lang="ts">`, Tailwind CSS via @nuxtjs/tailwindcss, Pinia).
Two developers (frontend and backend) build in parallel from your documents alone, so every
contract between them (endpoints, payloads, field names, status codes) must be explicit.
Use the `thinking` MCP server to reason step by step before you write.

""" + SHARED_RULES

MANIFEST_SCHEMA = """\
{
  "app_name": "short_snake_case_name",
  "backend_package": "<app_name>_backend",
  "entities": [{"name": "Todo", "fields": [{"name": "title", "type": "CharField(max_length=200)"}]}],
  "api_endpoints": [{"method": "GET", "path": "/api/todos/", "description": "List todos"}],
  "pages": [{"route": "/", "file": "frontend/pages/index.vue", "description": "..."}],
  "files": [
    {"path": "backend/manage.py", "owner": "backend", "purpose": "Django entry point"},
    {"path": "frontend/pages/index.vue", "owner": "frontend", "purpose": "Todo list page"}
  ]
}"""


def config(ctx: PipelineContext, session: str):
    def _fn(base_url: str):
        return build_config(
            ctx,
            base_url,
            session=session,
            system_instructions=SYSTEM_PROMPT.replace("{root}", str(ctx.root)),
            mcp_servers=[registry.thinking(), registry.filesystem(ctx.root, "filesystem")],
        )

    return _fn


def plan_job(ctx: PipelineContext) -> AgentJob:
    root = ctx.root
    prompt = f"""\
Project: {ctx.project_name}
{('Description: ' + ctx.project_description) if ctx.project_description else ''}

The user's requirement document is at {root / REQUIREMENT_FILE} (also reproduced below).

Produce exactly two files:

1. {root / DDS_FILE} — the Design Doc Spec, in Markdown, with these sections:
   Overview · Assumptions · Data model (every entity, field, type, constraint, relation) ·
   REST API (every endpoint: method, path, request body, response shape, status codes; all
   under /api/, trailing slashes, JSON, no authentication unless the requirement asks for it) ·
   Frontend (routes, page-by-page UI, components, Pinia stores, which endpoint each action calls) ·
   File plan (every file each developer must create) · Acceptance checks (what QA must verify).

2. {root / MANIFEST_FILE} — machine-readable JSON with this shape:
{MANIFEST_SCHEMA}
   The "files" list must include at least:
   backend/manage.py, backend/requirements.txt, backend/<app_name>_backend/{{__init__,settings,urls,wsgi}}.py,
   backend/api/{{__init__,apps,models,serializers,views,urls,admin}}.py, backend/api/migrations/__init__.py,
   backend/api/migrations/0001_initial.py, frontend/package.json, frontend/nuxt.config.ts,
   frontend/tailwind.config.js, frontend/app.vue, frontend/assets/css/main.css, and every page,
   component and store the frontend needs. Keep the scope tight: build what the requirement asks
   for, well, rather than extras.

Fixed technical decisions (put them in the DDS so both developers follow them):
- Backend uses SQLite by default and PostgreSQL only when the POSTGRES_DB env var is set.
- Backend reads CORS_ALLOWED_ORIGINS (comma-separated, default "http://localhost:3000,http://127.0.0.1:3000").
- `GET /` on the backend returns 200 JSON {{"status": "ok"}} (health check).
- Frontend reads the API base from runtimeConfig.public.apiBase (env NUXT_PUBLIC_API_BASE, default
  http://localhost:8000), runs as an SPA (`ssr: false`), and `npm run dev` serves on port 3000.

--- user_requirement.md ---
{ctx.requirement}
--- end ---
"""
    return AgentJob(role="architect", agent_name=AGENT_NAME, prompt=prompt, config_fn=config(ctx, "architect"))


def repair_job(ctx: PipelineContext, iteration: int, qa_report: str) -> AgentJob:
    root = ctx.root
    prompt = f"""\
QA verification iteration {iteration} FAILED. The QA report is at {root / QA_REPORT_FILE}
and reproduced below. The design is in {root / DDS_FILE} and {root / MANIFEST_FILE}.

Diagnose the root cause of every failure (read the offending files), then write
{root / REPAIR_PLAN_FILE}: a Markdown plan with two sections, "## Backend fixes" and
"## Frontend fixes". Each fix names the exact file, the problem, and the precise change.
Write "None." under a section that needs no changes. If the design itself was wrong, also
patch {root / DDS_FILE} and {root / MANIFEST_FILE}. Do not edit application code yourself.

--- qa_report.md ---
{qa_report}
--- end ---
"""
    return AgentJob(
        role="architect_repair",
        agent_name=AGENT_NAME,
        prompt=prompt,
        config_fn=config(ctx, f"architect-repair-{iteration}"),
        extra={"iteration": iteration, "qa_report": qa_report},
    )
