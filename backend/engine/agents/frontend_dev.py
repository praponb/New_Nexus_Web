"""Frontend Developer agent: builds ./frontend (Nuxt 3) from the DDS."""

from __future__ import annotations

from ..context import AGENTS_DIR, DDS_FILE, FE_OUTPUT_FILE, MANIFEST_FILE, REPAIR_PLAN_FILE, PipelineContext
from ..mcp import registry
from .base import FRONTEND_DEV, DEV_NOTES_RULE, SHARED_RULES, AgentJob, build_config

AGENT_NAME = FRONTEND_DEV

SYSTEM_PROMPT = """\
You are a senior frontend engineer. You implement complete Nuxt 3 applications:
- Vue 3 single-file components with `<script setup lang="ts">`.
- Tailwind CSS (module @nuxtjs/tailwindcss) with a modern, clean, responsive design, generous
  spacing and dark-mode support (`darkMode: 'class'`).
- Pinia stores (module @pinia/nuxt) for state; API calls with `$fetch` / `useFetch` against
  `useRuntimeConfig().public.apiBase` (default http://localhost:8000). Never hard-code another host.
- `nuxt.config.ts` sets `ssr: false`, registers the modules, `css: ['~/assets/css/main.css']`,
  and runtimeConfig.public.apiBase from NUXT_PUBLIC_API_BASE.
- package.json: "type": "module"; scripts dev = "nuxt dev --port 3000", build = "nuxt build",
  postinstall = "nuxt prepare"; dependencies nuxt ^3.21.11, @nuxtjs/tailwindcss ^6.14.0,
  @pinia/nuxt ^0.11.3, pinia ^3.0.4, vue ^3.5.0, vue-router ^4.5.0. No other dependencies unless essential.
- Handle loading, empty and error states in the UI. Every endpoint the DDS lists for the UI must be wired up.
You may only write inside the frontend directory. Do not create node_modules or lock files.

""" + SHARED_RULES + DEV_NOTES_RULE


def config(ctx: PipelineContext, session: str):
    def _fn(base_url: str):
        return build_config(
            ctx,
            base_url,
            session=session,
            system_instructions=SYSTEM_PROMPT.replace("{root}", str(ctx.frontend_dir))
            .replace("{notes}", str(ctx.root / AGENTS_DIR))
            .replace("{server}", "filesystem-frontend"),
            mcp_servers=[
                registry.filesystem(ctx.frontend_dir, "filesystem-frontend"),
            ],
            workspace=ctx.frontend_dir,
        )

    return _fn


def _docs(ctx: PipelineContext) -> str:
    return (
        f"--- dds_output.md ---\n{ctx.read(DDS_FILE)}\n--- end ---\n\n"
        f"--- manifest.json ---\n{ctx.read(MANIFEST_FILE)}\n--- end ---\n"
    )


def build_job(ctx: PipelineContext) -> AgentJob:
    prompt = f"""\
Implement the complete frontend described in the design below, writing every file owned by
"frontend" in the manifest under {ctx.frontend_dir} (manifest paths are relative to {ctx.root}).
When done, write {ctx.root / FE_OUTPUT_FILE}: a Markdown summary listing every file you wrote,
the routes, and how each page talks to the API.

{_docs(ctx)}"""
    return AgentJob(role="frontend", agent_name=AGENT_NAME, prompt=prompt, config_fn=config(ctx, "frontend"))


def repair_job(ctx: PipelineContext, iteration: int) -> AgentJob:
    prompt = f"""\
QA found problems. Apply every item under "## Frontend fixes" in the repair plan below with
surgical edits to files under {ctx.frontend_dir}. Read each file before editing it. If the
section says "None.", reply "No frontend changes needed." without editing anything.
Afterwards append a short "## Repair {iteration}" section to {ctx.root / FE_OUTPUT_FILE}.

--- repair_plan.md ---
{ctx.read(REPAIR_PLAN_FILE)}
--- end ---

{_docs(ctx)}"""
    return AgentJob(
        role="frontend_repair",
        agent_name=AGENT_NAME,
        prompt=prompt,
        config_fn=config(ctx, f"frontend-repair-{iteration}"),
        extra={"iteration": iteration},
    )
