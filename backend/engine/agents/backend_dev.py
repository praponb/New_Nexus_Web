"""Backend Developer agent: builds ./backend (Django 5 + DRF) from the DDS."""

from __future__ import annotations

from ..context import BE_OUTPUT_FILE, DDS_FILE, MANIFEST_FILE, REPAIR_PLAN_FILE, PipelineContext
from ..mcp import registry
from .base import BACKEND_DEV, SHARED_RULES, AgentJob, build_config

AGENT_NAME = BACKEND_DEV

SYSTEM_PROMPT = """\
You are a senior backend engineer. You implement complete Django 5 + Django REST Framework APIs:
- Project package `<app_name>_backend` (settings.py, urls.py, wsgi.py, __init__.py) and one app `api`
  (apps.py, models.py, serializers.py, views.py, urls.py, admin.py, migrations/).
- settings.py: SECRET_KEY/DEBUG/ALLOWED_HOSTS from env with safe dev defaults; SQLite at
  BASE_DIR / "db.sqlite3" by default, PostgreSQL only when POSTGRES_DB is set (HOST default "/tmp",
  PORT default "5432", other POSTGRES_* env fallbacks); django-cors-headers with
  CORS_ALLOWED_ORIGINS read from env (default "http://localhost:3000,http://127.0.0.1:3000");
  REST_FRAMEWORK defaults; DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField".
- Root urls.py: `GET /` returns JsonResponse({"status": "ok"}); the API is mounted at /api/.
- Models with proper field types, constraints, Meta.ordering and indexes. Hand-write the initial
  migration `api/migrations/0001_initial.py` so it exactly matches models.py (field order, options,
  index names of at most 30 characters, set explicitly with `name=`), plus an empty `__init__.py`.
- Serializers with validation, ViewSets or APIViews, a DefaultRouter in api/urls.py.
- requirements.txt: Django>=5.1,<6, djangorestframework>=3.15, django-cors-headers>=4.4,
  and `psycopg2-binary>=2.9; python_version < "3.14"`. Nothing else unless essential.
- The code must pass `python manage.py check` and `python manage.py makemigrations --check`.
You may only write inside the backend directory. Do not create virtualenvs or databases.

""" + SHARED_RULES


def config(ctx: PipelineContext, session: str):
    def _fn(base_url: str):
        return build_config(
            ctx,
            base_url,
            session=session,
            system_instructions=SYSTEM_PROMPT.replace("{root}", str(ctx.backend_dir)),
            mcp_servers=[
                registry.filesystem(ctx.backend_dir, "filesystem-backend"),
                registry.filesystem(ctx.root / ".agents", "agents-notes"),
            ],
            workspace=ctx.backend_dir,
        )

    return _fn


def _docs(ctx: PipelineContext) -> str:
    return (
        f"--- dds_output.md ---\n{ctx.read(DDS_FILE)}\n--- end ---\n\n"
        f"--- manifest.json ---\n{ctx.read(MANIFEST_FILE)}\n--- end ---\n"
    )


def build_job(ctx: PipelineContext) -> AgentJob:
    prompt = f"""\
Implement the complete backend described in the design below, writing every file owned by
"backend" in the manifest under {ctx.backend_dir} (manifest paths are relative to {ctx.root}).
When done, write {ctx.root / BE_OUTPUT_FILE}: a Markdown summary listing every file you wrote
and every endpoint with its request/response shape.

{_docs(ctx)}"""
    return AgentJob(role="backend", agent_name=AGENT_NAME, prompt=prompt, config_fn=config(ctx, "backend"))


def repair_job(ctx: PipelineContext, iteration: int) -> AgentJob:
    prompt = f"""\
QA found problems. Apply every item under "## Backend fixes" in the repair plan below with
surgical edits to files under {ctx.backend_dir}. Read each file before editing it. If the
section says "None.", reply "No backend changes needed." without editing anything.
Afterwards append a short "## Repair {iteration}" section to {ctx.root / BE_OUTPUT_FILE}.

--- repair_plan.md ---
{ctx.read(REPAIR_PLAN_FILE)}
--- end ---

{_docs(ctx)}"""
    return AgentJob(
        role="backend_repair",
        agent_name=AGENT_NAME,
        prompt=prompt,
        config_fn=config(ctx, f"backend-repair-{iteration}"),
        extra={"iteration": iteration},
    )
