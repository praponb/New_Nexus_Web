"""Deterministic pre-QA checks: real signals the QA agent reasons from.

Levels (NEXUS_QA_CHECKS): "off", "fast" (manifest/layout + py_compile), "full" (fast +
isolated venv with `manage.py check`, `makemigrations --check`, `migrate`, then
`npm install` + `nuxi build`). Live runs default to "full", mock runs to "fast".
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from apps.projects.models import LogType

from .agents.base import QA_TESTER
from .context import MANIFEST_FILE, PipelineContext

REQUIRED_FILES = [
    "backend/manage.py",
    "backend/requirements.txt",
    "frontend/package.json",
    "frontend/nuxt.config.ts",
    "frontend/app.vue",
]
OUTPUT_TAIL_CHARS = 4000
# Only these host variables reach the generated app's processes.
_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "SHELL")


@dataclass
class CheckResult:
    name: str
    ok: bool
    output: str = ""
    skipped: bool = False


@dataclass
class CheckReport:
    results: list[CheckResult] = field(default_factory=list)
    venv_python: str = "python3"

    @property
    def ok(self) -> bool:
        return all(r.ok or r.skipped for r in self.results)

    def summary(self) -> str:
        if not self.results:
            return "- (no deterministic checks were run)"
        lines = []
        for r in self.results:
            state = "SKIPPED" if r.skipped else ("PASSED" if r.ok else "FAILED")
            lines.append(f"- [{state}] {r.name}")
            if not r.ok and not r.skipped and r.output:
                body = r.output.strip()[-OUTPUT_TAIL_CHARS:]
                lines.append("  ```\n" + "\n".join("  " + ln for ln in body.splitlines()) + "\n  ```")
        return "\n".join(lines)


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}
    env.update(extra)
    return env


async def run_cmd(args: list[str], cwd: Path, env: dict, timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=str(cwd), env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, f"Timed out after {int(timeout)}s: {' '.join(args)}"
    return proc.returncode or 0, out.decode("utf-8", errors="replace")


def check_level(ctx: PipelineContext) -> str:
    default = "full" if ctx.config.is_live else "fast"
    return os.environ.get("NEXUS_QA_CHECKS", default).lower()


def _manifest_paths(ctx: PipelineContext) -> tuple[list[str], str | None]:
    raw = ctx.read(MANIFEST_FILE)
    if not raw.strip():
        return [], "manifest.json is missing or empty"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], f"manifest.json is not valid JSON: {exc}"
    files = data.get("files", []) if isinstance(data, dict) else data
    paths = []
    for item in files or []:
        path = item.get("path") if isinstance(item, dict) else item
        if isinstance(path, str) and path.strip():
            paths.append(path.strip().lstrip("./"))
    return paths, None


async def run_checks(ctx: PipelineContext) -> CheckReport:
    level = check_level(ctx)
    report = CheckReport()
    if level == "off":
        return report
    sink = ctx.sink

    async def record(result: CheckResult) -> CheckResult:
        report.results.append(result)
        await sink.log(
            QA_TESTER,
            LogType.TOOL_RESULT,
            f"{'✅' if result.ok else ('⏭️' if result.skipped else '❌')} {result.name}"
            + ("" if result.ok or not result.output else f"\n{result.output.strip()[-OUTPUT_TAIL_CHARS:]}"),
            {"check": result.name, "ok": result.ok, "skipped": result.skipped},
        )
        return result

    async def announce(name: str, command: str = "") -> None:
        await sink.log(QA_TESTER, LogType.TOOL_CALL, f"check: {name}", {"check": name, "command": command})

    # 1. Layout + manifest -------------------------------------------------------------
    await announce("project layout & manifest")
    missing = [p for p in REQUIRED_FILES if not ctx.path(p).is_file()]
    manifest_paths, manifest_error = _manifest_paths(ctx)
    missing += [p for p in manifest_paths if p not in missing and not ctx.path(p).exists()]
    problems = ([manifest_error] if manifest_error else []) + [f"missing: {p}" for p in missing]
    await record(CheckResult("project layout & manifest", not problems, "\n".join(problems)))

    # 2. Python syntax -----------------------------------------------------------------
    if ctx.backend_dir.is_dir():
        await announce("python compile (backend)", "python -m compileall -q backend")
        code, out = await run_cmd(
            [sys.executable, "-m", "compileall", "-q", "-x", r"(\.venv|node_modules)", "backend"],
            ctx.root,
            clean_env(PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(ctx.qa_dir / "pycache")),
            120,
        )
        await record(CheckResult("python compile (backend)", code == 0, out))

    if level != "full":
        return report

    # 3. Backend in an isolated venv ---------------------------------------------------
    venv = ctx.qa_dir / "venv"
    py = venv / "bin" / "python"
    report.venv_python = str(py)
    env = clean_env(PYTHONDONTWRITEBYTECODE="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    if ctx.path("backend/requirements.txt").is_file():
        await announce("backend: install requirements", "pip install -r requirements.txt")
        out = ""
        code = 0
        if not py.exists():
            code, out = await run_cmd([sys.executable, "-m", "venv", str(venv)], ctx.qa_dir, env, 300)
        if code == 0:
            code, out = await run_cmd(
                [str(py), "-m", "pip", "install", "-q", "-r", "requirements.txt"], ctx.backend_dir, env, 900
            )
        installed = await record(CheckResult("backend: install requirements", code == 0, out))
        if installed.ok:
            db_env = dict(env, DJANGO_DEBUG="true")
            for name, args in (
                ("backend: manage.py check", ["manage.py", "check"]),
                ("backend: makemigrations --check", ["manage.py", "makemigrations", "--check", "--dry-run"]),
                ("backend: migrate (sqlite)", ["manage.py", "migrate", "--noinput"]),
            ):
                await announce(name, " ".join(["python", *args]))
                code, out = await run_cmd([str(py), *args], ctx.backend_dir, db_env, 300)
                await record(CheckResult(name, code == 0, out))

    # 4. Frontend install + build ------------------------------------------------------
    if ctx.path("frontend/package.json").is_file():
        npm_env = clean_env(npm_config_cache=str(ctx.qa_dir / "npm-cache"), NUXT_TELEMETRY_DISABLED="1", CI="1")
        await announce("frontend: npm install", "npm install")
        code, out = await run_cmd(
            ["npm", "install", "--no-fund", "--no-audit", "--fetch-retries=5", "--fetch-timeout=60000"],
            ctx.frontend_dir,
            npm_env,
            1200,
        )
        installed = await record(CheckResult("frontend: npm install", code == 0, out))
        if installed.ok:
            await announce("frontend: nuxi build", "npx nuxi build")
            code, out = await run_cmd(["npx", "nuxi", "build"], ctx.frontend_dir, npm_env, 900)
            await record(CheckResult("frontend: nuxi build", code == 0, out))
    return report
