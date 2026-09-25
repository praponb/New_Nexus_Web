"""QA Automation Tester agent: validates the generated app and writes .agents/qa_report.md."""

from __future__ import annotations

from ..context import DDS_FILE, QA_REPORT_FILE, PipelineContext
from ..mcp import registry
from .base import QA_TESTER, SHARED_RULES, AgentJob, build_config

AGENT_NAME = QA_TESTER

SYSTEM_PROMPT = """\
You are a meticulous QA automation engineer. You verify generated full-stack apps
(Django REST backend + Nuxt 3 frontend) by reading code, running them, and driving the UI
in a real browser with the Playwright MCP tools. You report facts with evidence (commands,
outputs, stack traces, screenshots); you never fix application code yourself.
Always start long-running servers as daemons, and stop every process you started before you finish.

""" + SHARED_RULES


def config(ctx: PipelineContext, session: str):
    def _fn(base_url: str):
        return build_config(
            ctx,
            base_url,
            session=session,
            system_instructions=SYSTEM_PROMPT.replace("{root}", str(ctx.root)),
            mcp_servers=[
                registry.filesystem(ctx.root, "filesystem"),
                registry.playwright(ctx.qa_dir / "playwright"),
            ],
            allow_commands=True,
        )

    return _fn


def build_job(ctx: PipelineContext, iteration: int, checks_summary: str, checks_ok: bool, venv_python: str) -> AgentJob:
    be, fe = ctx.qa_backend_port, ctx.qa_frontend_port
    prompt = f"""\
QA verification loop {iteration}/{ctx.config.max_qa_iterations} for the app at {ctx.root}.
The design and acceptance checks are in {ctx.root / DDS_FILE}.

The orchestrator already ran these deterministic checks (ground truth; any FAILED check means
the overall status MUST be FAIL):
{checks_summary}

Your job:
1. Audit the code against the design: every endpoint and page exists, the frontend calls the
   endpoints with the right paths and field names, no placeholder code.
2. Unless a deterministic check failed in a way that makes running impossible, run the app on
   the QA ports (never use 8000 or 3000; they belong to the host platform):
   - Backend (daemon), from {ctx.backend_dir}:
     `CORS_ALLOWED_ORIGINS=http://localhost:{fe},http://127.0.0.1:{fe} {venv_python} manage.py migrate --noinput && CORS_ALLOWED_ORIGINS=http://localhost:{fe},http://127.0.0.1:{fe} {venv_python} manage.py runserver 127.0.0.1:{be} --noreload`
   - Frontend (daemon), from {ctx.frontend_dir} (dependencies are already installed):
     `NUXT_PUBLIC_API_BASE=http://127.0.0.1:{be} npx nuxi dev --port {fe} --host 127.0.0.1`
   - Wait for both to respond (poll with curl), exercise the API with curl (create, list,
     update, delete for each resource), then use Playwright to open http://127.0.0.1:{fe}/,
     perform the main user flow from the design, and check the browser console for errors.
   - Stop both servers when you are done.
3. Write {ctx.root / QA_REPORT_FILE} in Markdown. Its FIRST line must be exactly
   `STATUS: PASS` or `STATUS: FAIL`. Then: a checklist of what you verified, and for every
   failure the file, the evidence (command + output or stack trace) and the suspected cause.
   Use PASS only if the app works end to end and every deterministic check passed.

Deterministic checks overall: {"PASSED" if checks_ok else "FAILED"}.
"""
    return AgentJob(
        role="qa",
        agent_name=AGENT_NAME,
        prompt=prompt,
        config_fn=config(ctx, f"qa-{iteration}"),
        extra={"iteration": iteration, "checks_ok": checks_ok, "checks_summary": checks_summary},
    )
