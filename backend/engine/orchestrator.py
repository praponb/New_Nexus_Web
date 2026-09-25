"""Coordinates the 4-agent pipeline: plan → build (FE ∥ BE) → QA self-correction loop → package."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Protocol

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections

from apps.projects import workspace as ws
from apps.projects.models import GeneratedArtifact, GenerationTask, LogType, Project, ProjectStatus

from . import checks
from .agents import architect, backend_dev, frontend_dev, qa_tester
from .agents.base import BACKEND_DEV, FRONTEND_DEV, QA_TESTER, TEAM_LEAD, AgentJob
from .config import load_config, scrub_process_env
from .context import (
    AGENTS_DIR,
    BE_OUTPUT_FILE,
    DDS_FILE,
    FE_OUTPUT_FILE,
    MANIFEST_FILE,
    QA_REPORT_FILE,
    REQUIREMENT_FILE,
    PipelineContext,
    resume_problem,
)
from .events import EventSink
from .packager import generator, zipper

logger = logging.getLogger(__name__)


class GenerationPipelineError(RuntimeError):
    pass


class AgentRunner(Protocol):
    async def run(self, job: AgentJob) -> str: ...


def _load_context(task_id) -> PipelineContext:
    task = GenerationTask.objects.select_related("project", "project__requirement_doc").get(id=task_id)
    project = task.project
    try:
        requirement = project.requirement_doc.raw_content
    except Exception as exc:  # RelatedObjectDoesNotExist
        raise GenerationPipelineError("The project has no requirement document.") from exc
    workspace = project.workspace
    resume_from = 0
    if task.resume:
        previous = project.generation_tasks.exclude(id=task.id).order_by("-created_at").first()
        resume_from = max(previous.qa_iterations if previous else 0, 1)
    return PipelineContext(
        task_id=str(task.id),
        project_id=str(project.id),
        project_name=project.name,
        project_slug=project.slug,
        project_description=project.description or "",
        workspace=workspace,
        root=ws.generated_dir(workspace),
        requirement=requirement,
        config=load_config(),
        sink=EventSink(task.id, project.id),
        resume=task.resume,
        resume_from=resume_from,
    )


def default_runner(ctx: PipelineContext) -> AgentRunner:
    if ctx.config.is_live:
        from .runner import LiveAgentRunner

        return LiveAgentRunner(ctx)
    from .mock_engine import MockAgentRunner

    return MockAgentRunner(ctx)


def _prepare_workspace(ctx: PipelineContext) -> None:
    ws.reset_dir(ctx.root)
    ctx.qa_dir.mkdir(parents=True, exist_ok=True)
    ctx.sessions_dir.mkdir(parents=True, exist_ok=True)
    ws.packages_dir(ctx.workspace).mkdir(parents=True, exist_ok=True)
    req = ctx.path(REQUIREMENT_FILE)
    req.parent.mkdir(parents=True, exist_ok=True)
    req.write_text(ctx.requirement, encoding="utf-8")


NOTES_FILENAMES = (Path(FE_OUTPUT_FILE).name, Path(BE_OUTPUT_FILE).name)


def _collect_stray_notes(ctx: PipelineContext) -> list[str]:
    """Move notes a developer wrote inside its own subtree (`<sub>/.agents/*` or a top-level
    `<sub>/fe_output.md` / `be_output.md` fallback) into the root `.agents/`."""
    moved = []
    target = ctx.path(AGENTS_DIR)
    target.mkdir(parents=True, exist_ok=True)

    def _move(item: Path, label: str) -> None:
        dest = target / item.name
        if dest.exists():  # keep both: append the stray content
            dest.write_text(dest.read_text(encoding="utf-8") + "\n\n" + item.read_text(encoding="utf-8"), encoding="utf-8")
            item.unlink()
        else:
            item.replace(dest)
        moved.append(label)

    for sub in (ctx.frontend_dir, ctx.backend_dir):
        for name in NOTES_FILENAMES:
            if (sub / name).is_file():
                _move(sub / name, f"{sub.name}/{name}")
        stray = sub / AGENTS_DIR
        if not stray.is_dir():
            continue
        for item in stray.iterdir():
            if item.is_file():
                _move(item, f"{sub.name}/{AGENTS_DIR}/{item.name}")
        shutil.rmtree(stray, ignore_errors=True)
    return moved


def _kill_port_listeners(ports: list[int]) -> list[int]:
    """Stop servers QA may have left running on its private ports."""
    killed = []
    for port in ports:
        try:
            out = subprocess.run(
                ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for pid in {int(p) for p in out.split() if p.strip().isdigit()}:
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except OSError:
                pass
    return killed


def _save_artifact(ctx: PipelineContext, info: zipper.ArchiveInfo) -> dict:
    GeneratedArtifact.objects.filter(project_id=ctx.project_id).delete()
    rel_name = info.path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve()).as_posix()
    artifact = GeneratedArtifact(
        project_id=ctx.project_id,
        file_name=f"nexus_project_{ctx.project_slug}.zip",
        file_size_bytes=info.size_bytes,
        sha256_checksum=info.sha256,
        total_files_count=info.file_count,
        total_lines_of_code=info.line_count,
    )
    artifact.zip_file.name = rel_name
    artifact.save()
    return {
        "id": str(artifact.id),
        "file_name": artifact.file_name,
        "file_size_bytes": artifact.file_size_bytes,
        "sha256_checksum": artifact.sha256_checksum,
        "total_files_count": artifact.total_files_count,
        "total_lines_of_code": artifact.total_lines_of_code,
    }


def build_package(ctx: PipelineContext) -> tuple[zipper.ArchiveInfo, dict]:
    """Zip the generated root and record it as the project's artifact (replacing any old one)."""
    dest = ws.packages_dir(ctx.workspace) / f"project_{ctx.project_id}_complete.zip"
    info = zipper.build_archive(ctx.root, dest, f"{ctx.project_slug}_generated")
    return info, _save_artifact(ctx, info)


def repackage(project_id) -> dict:
    """Rebuild a completed project's zip with the current delivery files, without rerunning agents."""
    project = Project.objects.get(id=project_id)
    task = project.latest_task()
    if project.status != ProjectStatus.COMPLETED or task is None:
        raise GenerationPipelineError(f"Project {project_id} is {project.status}; only completed projects are repackaged.")
    ctx = _load_context(task.id)
    ws.packages_dir(ctx.workspace).mkdir(parents=True, exist_ok=True)
    written = generator.write_support_files(ctx)
    _, artifact = build_package(ctx)
    return {"files_written": written, **artifact}


class Pipeline:
    def __init__(self, ctx: PipelineContext, runner: AgentRunner):
        self.ctx = ctx
        self.runner = runner
        self.sink = ctx.sink

    async def run(self) -> dict:
        if self.ctx.resume:
            return await self.resume()
        await self.sink.phase(ProjectStatus.PLANNING, active_agents=[TEAM_LEAD])
        await self.sink.system(
            f"Pipeline started ({self.ctx.config.mode} mode, model {self.ctx.config.model_name}).",
            mode=self.ctx.config.mode,
        )
        await sync_to_async(_prepare_workspace)(self.ctx)
        await self.plan()
        await self.build()
        await self.verify()
        return await self.package()

    async def resume(self) -> dict:
        """Continue a failed run in place: repair from its last QA report, then re-run the QA loop."""
        problem = await sync_to_async(resume_problem)(self.ctx.root, self.ctx.requirement)
        if problem:
            raise GenerationPipelineError(problem)
        await self.sink.phase(ProjectStatus.TESTING, progress=62, active_agents=[TEAM_LEAD])
        await self.sink.system(
            f"Continuing the failed run ({self.ctx.config.mode} mode, model {self.ctx.config.model_name}): "
            f"keeping the generated code and repairing from the QA loop {self.ctx.resume_from} report.",
            mode=self.ctx.config.mode,
        )
        self.ctx.qa_dir.mkdir(parents=True, exist_ok=True)
        self.ctx.sessions_dir.mkdir(parents=True, exist_ok=True)
        await self.repair(self.ctx.resume_from, self.ctx.read(QA_REPORT_FILE), 62, 64)
        await self.verify()
        return await self.package()

    async def plan(self) -> None:
        await self.runner.run(architect.plan_job(self.ctx))
        missing = [f for f in (DDS_FILE, MANIFEST_FILE) if not self.ctx.path(f).is_file()]
        if missing:
            raise GenerationPipelineError(f"Team Lead did not produce: {', '.join(missing)}")
        await self.sink.progress(20)

    async def build(self) -> None:
        await self.sink.phase(ProjectStatus.GENERATING, active_agents=[FRONTEND_DEV, BACKEND_DEV])
        await asyncio.gather(
            self._tracked(frontend_dev.build_job(self.ctx), 25, 60),
            self._tracked(backend_dev.build_job(self.ctx), 25, 60),
        )
        await self._tidy_notes()
        await self.sink.progress(60, active_agents=[])

    async def _tracked(self, job: AgentJob, start: int, end: int) -> str:
        """Run a job while nudging progress as files land (for long parallel phases)."""
        result = await self.runner.run(job)
        await self.sink.progress(start + (end - start) // 2)
        return result

    async def _tidy_notes(self) -> None:
        moved = await sync_to_async(_collect_stray_notes)(self.ctx)
        if moved:
            await self.sink.system(f"Moved agent notes into .agents/: {', '.join(moved)}")

    async def verify(self) -> None:
        max_iter = self.ctx.config.max_qa_iterations
        if self.sink.status != ProjectStatus.TESTING:  # a resumed run is already there
            await self.sink.phase(ProjectStatus.TESTING, active_agents=[QA_TESTER])
        span = 25  # TESTING covers 65% → 90%
        for iteration in range(1, max_iter + 1):
            self.ctx.qa_iteration = iteration
            await self.sink.set_qa_iterations(iteration)
            await self.sink.log(QA_TESTER, LogType.SYSTEM, f"Starting QA Verification Loop {iteration}/{max_iter}")
            await self.sink.progress(65 + span * (iteration - 1) // max_iter, active_agents=[QA_TESTER])

            report = await checks.run_checks(self.ctx)
            try:
                self.ctx.path(QA_REPORT_FILE).unlink(missing_ok=True)
                reply = await self.runner.run(
                    qa_tester.build_job(self.ctx, iteration, report.summary(), report.ok, report.venv_python)
                )
            finally:
                await sync_to_async(_kill_port_listeners)([self.ctx.qa_backend_port, self.ctx.qa_frontend_port])

            qa_report = self.ctx.read(QA_REPORT_FILE) or reply
            first_line = next((ln.strip() for ln in qa_report.splitlines() if ln.strip()), "")
            agent_pass = "STATUS: PASS" in first_line or ("STATUS: PASS" in qa_report and "STATUS: FAIL" not in qa_report)
            if agent_pass and report.ok:
                await self.sink.log(QA_TESTER, LogType.SYSTEM, "✅ All integration checks passed!")
                return
            if agent_pass and not report.ok:
                await self.sink.log(
                    QA_TESTER, LogType.SYSTEM, "QA reported PASS but deterministic checks failed; treating as FAIL."
                )
            if iteration == max_iter:
                raise GenerationPipelineError(
                    f"QA verification failed after {max_iter} self-correction attempts. "
                    f"See .agents/qa_report.md.\n\n{qa_report[:1500]}"
                )
            end = 65 + span * iteration // max_iter
            await self.repair(iteration, qa_report, end - 5, end - 3)

    async def repair(self, iteration: int, qa_report: str, plan_pct: int, fix_pct: int) -> None:
        await self.sink.log(TEAM_LEAD, LogType.SYSTEM, f"⚠️ QA Failure detected. Initiating repair cycle {iteration}...")
        await self.sink.progress(plan_pct, active_agents=[TEAM_LEAD])
        await self.runner.run(architect.repair_job(self.ctx, iteration, qa_report))
        await self.sink.progress(fix_pct, active_agents=[FRONTEND_DEV, BACKEND_DEV])
        await asyncio.gather(
            self.runner.run(frontend_dev.repair_job(self.ctx, iteration)),
            self.runner.run(backend_dev.repair_job(self.ctx, iteration)),
        )
        await self._tidy_notes()

    async def package(self) -> dict:
        await self.sink.phase(ProjectStatus.PACKAGING, active_agents=["Packager"])
        written = await sync_to_async(generator.write_support_files)(self.ctx)
        for rel in written:
            await self.sink.file_created("Packager", rel, "generator")
        await self.sink.log("Packager", LogType.TOOL_CALL, "zipper.build_archive", {"files_written": written})
        info, artifact = await sync_to_async(build_package)(self.ctx)
        await self.sink.log(
            "Packager",
            LogType.TOOL_RESULT,
            f"📦 {artifact['file_name']}: {info.file_count} files, {info.line_count} lines, "
            f"{info.size_bytes / 1024:.1f} KB, sha256 {info.sha256[:16]}…",
            artifact,
        )
        await self.sink.complete(artifact)
        return artifact


async def run_pipeline(task_id, runner: AgentRunner | None = None) -> dict | None:
    """Run the full generation pipeline for `task_id`. Never raises for pipeline failures:
    the project is marked FAILED with `error_message` and a `pipeline_failed` event is sent."""
    ctx = None
    scrub_process_env()  # Django is configured by now; keep secrets out of agent subprocesses
    try:
        ctx = await sync_to_async(_load_context)(task_id)
        pipeline = Pipeline(ctx, runner or default_runner(ctx))
        return await pipeline.run()
    except asyncio.CancelledError:
        if ctx is not None:
            await ctx.sink.fail("Generation was cancelled.")
        raise
    except Exception as exc:
        logger.exception("Generation task %s failed", task_id)
        message = str(exc) if isinstance(exc, GenerationPipelineError) else f"{type(exc).__name__}: {exc}"
        if ctx is None:
            await sync_to_async(_mark_failed_without_context)(task_id, message)
        else:
            await ctx.sink.fail(message)
        return None
    finally:
        await sync_to_async(close_old_connections)()


def _mark_failed_without_context(task_id, message: str) -> None:
    from django.utils import timezone

    task = GenerationTask.objects.filter(id=task_id).select_related("project").first()
    if task is None:
        return
    task.current_phase = ProjectStatus.FAILED
    task.finished_at = timezone.now()
    task.save(update_fields=["current_phase", "finished_at"])
    project = task.project
    project.status = ProjectStatus.FAILED
    project.error_message = message[:5000]
    project.save(update_fields=["status", "error_message", "updated_at"])
