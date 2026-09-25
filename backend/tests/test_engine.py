import asyncio
import json
import stat
import zipfile
from pathlib import Path

import pytest
from aiohttp import web
from asgiref.sync import sync_to_async
from google.antigravity import types

from apps.projects.models import AgentStepLog, GeneratedArtifact, GenerationTask, LogType, Project, ProjectStatus, RequirementDoc
from engine import orchestrator
from engine.agents.base import AgentJob
from engine.llm_relay import LLMRelay
from engine.mock_engine import FAULT_FILE, MockAgentRunner
from engine.packager import zipper
from engine.runner import LiveAgentRunner, StreamPump, is_retryable

REQUIREMENT = "# Todo\n\nBuild a todo app where users add, edit, complete and delete tasks with due dates and filters."


# --------------------------------------------------------------------------- zipper
def test_zipper_excludes_build_output_and_keeps_exec_bit(tmp_path):
    src = tmp_path / "generated"
    (src / "backend").mkdir(parents=True)
    (src / "frontend" / "node_modules" / "x").mkdir(parents=True)
    (src / ".agents").mkdir()
    (src / "backend" / "manage.py").write_text("print(1)\nprint(2)\n")
    (src / "backend" / "db.sqlite3").write_bytes(b"sqlite")
    (src / "backend" / "__pycache__").mkdir()
    (src / "backend" / "__pycache__" / "m.pyc").write_bytes(b"\x00")
    (src / "frontend" / "node_modules" / "x" / "index.js").write_text("junk")
    (src / "frontend" / ".nuxt").mkdir()
    (src / "frontend" / ".nuxt" / "tsconfig.json").write_text("{}")
    (src / ".agents" / "qa_report.md").write_text("STATUS: PASS")
    script = src / "start_servers.sh"
    script.write_text("#!/usr/bin/env bash\necho hi\n")
    script.chmod(0o644)  # packager must force it executable anyway

    info = zipper.build_archive(src, tmp_path / "out" / "bundle.zip", "demo_generated")

    with zipfile.ZipFile(info.path) as zf:
        names = sorted(zf.namelist())
        assert names == ["demo_generated/backend/manage.py", "demo_generated/start_servers.sh"]
        mode = zf.getinfo("demo_generated/start_servers.sh").external_attr >> 16
        assert mode & stat.S_IXUSR
        assert zf.read("demo_generated/backend/manage.py") == b"print(1)\nprint(2)\n"
    assert info.file_count == 2
    assert info.line_count == 4
    assert info.sha256 == zipper.sha256_file(info.path) and len(info.sha256) == 64
    assert not (tmp_path / "out" / "bundle.zip.part").exists()


# --------------------------------------------------------------------------- relay
async def _fake_upstream(seen: dict):
    async def handler(request: web.Request):
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = await request.json()
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await resp.prepare(request)
        for delta in ({"reasoning_content": "Plan the "}, {"reasoning_content": "schema."}, {"content": "ok"}):
            await resp.write(f"data: {json.dumps({'choices': [{'delta': delta}]})}\n\n".encode())
        await resp.write(b"data: [DONE]\n\n")
        await resp.write_eof()
        return resp

    app = web.Application()
    app.router.add_post("/v1/chat/completions", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}/v1"


async def test_relay_injects_key_and_taps_events():
    import aiohttp

    seen: dict = {}
    events: list = []
    upstream, base = await _fake_upstream(seen)
    body = {
        "model": "kimi-k3",
        "stream": True,
        "messages": [
            {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "write_file"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "Successfully wrote"},
        ],
    }
    try:
        async with LLMRelay(base, "sk-test", extra_body={"reasoning_effort": "high"}, on_event=lambda k, p: events.append((k, p))) as relay:
            async with aiohttp.ClientSession() as session:
                for _ in range(2):  # the same tool result must only be reported once
                    async with session.post(f"{relay.base_url}/chat/completions", json=body) as resp:
                        text = await resp.text()
    finally:
        await upstream.cleanup()

    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["reasoning_effort"] == "high"
    assert "[DONE]" in text
    assert [p["text"] for k, p in events if k == "reasoning"] == ["Plan the ", "schema."] * 2
    assert [p for k, p in events if k == "tool_result"] == [{"id": "c1", "name": "write_file", "content": "Successfully wrote"}]


# --------------------------------------------------------------------------- fixtures
@pytest.fixture
def project_task(user, settings):
    settings.NEXUS_MAX_QA_ITERATIONS = 3
    project = Project.objects.create(owner=user, name="Todo Demo")
    RequirementDoc.objects.create(project=project, raw_content=REQUIREMENT, word_count=len(REQUIREMENT.split()))
    task = GenerationTask.objects.create(project=project)
    project.status = ProjectStatus.QUEUED
    project.save()
    return project, task


def _runner_factory(**kwargs):
    def make(ctx):
        return MockAgentRunner(ctx, delay=0, **kwargs)

    return make


async def _run(task, monkeypatch, runner_factory=None):
    monkeypatch.setattr(orchestrator, "default_runner", runner_factory or _runner_factory())
    return await orchestrator.run_pipeline(task.id)


# --------------------------------------------------------------------------- orchestrator
@pytest.mark.django_db(transaction=True)
async def test_mock_pipeline_completes(project_task, monkeypatch):
    project, task = project_task
    monkeypatch.delenv("NEXUS_MOCK_INJECT_FAULT", raising=False)
    artifact = await _run(task, monkeypatch)

    assert artifact is not None
    await sync_to_async(project.refresh_from_db)()
    await sync_to_async(task.refresh_from_db)()
    assert project.status == ProjectStatus.COMPLETED
    assert task.progress_percentage == 100 and task.qa_iterations == 1
    assert task.started_at and task.finished_at

    db_artifact = await sync_to_async(GeneratedArtifact.objects.get)(project=project)
    zip_path = Path(db_artifact.zip_file.path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "todo-demo_generated/start_servers.sh" in names
        assert "todo-demo_generated/backend/api/models.py" in names
        assert "todo-demo_generated/frontend/pages/index.vue" in names
        assert not any("/.agents/" in n for n in names)
        assert zf.getinfo("todo-demo_generated/start_servers.sh").external_attr >> 16 & stat.S_IXUSR
    assert db_artifact.sha256_checksum == zipper.sha256_file(zip_path)

    logs = await sync_to_async(list)(AgentStepLog.objects.filter(task=task).order_by("sequence_num"))
    seqs = [log.sequence_num for log in logs]
    assert seqs == list(range(1, len(logs) + 1))
    types_seen = {log.log_type for log in logs}
    assert {LogType.THOUGHT, LogType.TOOL_CALL, LogType.TOOL_RESULT, LogType.PHASE_CHANGE} <= types_seen
    assert {log.agent_name for log in logs} >= {"Team Lead", "Frontend Dev", "Backend Dev", "QA", "Packager"}


@pytest.mark.django_db(transaction=True)
async def test_mock_pipeline_self_corrects_injected_fault(project_task, monkeypatch):
    project, task = project_task
    monkeypatch.setenv("NEXUS_MOCK_INJECT_FAULT", "1")
    artifact = await _run(task, monkeypatch)

    assert artifact is not None
    await sync_to_async(task.refresh_from_db)()
    assert task.qa_iterations == 2
    root = project.workspace / "generated"
    assert "broken_view" not in (root / FAULT_FILE).read_text()
    assert (root / ".agents" / "repair_plan.md").exists()
    contents = await sync_to_async(list)(AgentStepLog.objects.filter(task=task).values_list("content", flat=True))
    assert any("Initiating repair cycle 1" in c for c in contents)
    assert any(c.startswith("❌ python compile") for c in contents)


class AlwaysFailQA(MockAgentRunner):
    async def _qa(self, job):
        self.ctx.path(".agents/qa_report.md").write_text("STATUS: FAIL\n\nThe page is blank.")
        return "STATUS: FAIL"


@pytest.mark.django_db(transaction=True)
async def test_pipeline_fails_after_max_qa_iterations(project_task, monkeypatch, settings):
    settings.NEXUS_MAX_QA_ITERATIONS = 2
    project, task = project_task
    monkeypatch.delenv("NEXUS_MOCK_INJECT_FAULT", raising=False)
    result = await _run(task, monkeypatch, lambda ctx: AlwaysFailQA(ctx, delay=0))

    assert result is None
    await sync_to_async(project.refresh_from_db)()
    await sync_to_async(task.refresh_from_db)()
    assert project.status == ProjectStatus.FAILED
    assert "after 2 self-correction attempts" in project.error_message
    assert task.qa_iterations == 2 and task.finished_at is not None
    assert not await sync_to_async(GeneratedArtifact.objects.filter(project=project).exists)()


@pytest.mark.django_db(transaction=True)
async def test_pipeline_fails_cleanly_without_requirement(user):
    project = await sync_to_async(Project.objects.create)(owner=user, name="Empty")
    task = await sync_to_async(GenerationTask.objects.create)(project=project)
    assert await orchestrator.run_pipeline(task.id) is None
    await sync_to_async(project.refresh_from_db)()
    assert project.status == ProjectStatus.FAILED
    assert "requirement" in project.error_message


# --------------------------------------------------------------------------- live runner pieces
class _Sink:
    def __init__(self):
        self.logs = []
        self.files = []

    async def log(self, agent, log_type, content, metadata=None):
        self.logs.append((agent, log_type, content, metadata or {}))

    async def file_created(self, agent, rel, tool=""):
        self.files.append(rel)


class _Ctx:
    def __init__(self, root: Path, sink):
        from engine.config import EngineConfig

        self.root = root
        self.sink = sink
        self.config = EngineConfig(
            mode="live", model_name="m", api_base="http://127.0.0.1:9", api_key="k", reasoning_effort="",
            max_qa_iterations=3, retry_attempts=3, retry_initial_backoff=0,
        )

    def rel(self, path):
        try:
            return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return None


async def test_stream_pump_maps_chunks(tmp_path):
    sink = _Sink()
    pump = StreamPump(_Ctx(tmp_path, sink), "Backend Dev")
    await pump.on_relay_event("reasoning", {"text": "I will write the models first. " * 10})
    await pump.on_chunk(types.ToolCall(name="write_file", server_name="filesystem-backend", args={"path": str(tmp_path / "backend/api/models.py"), "content": "x" * 5000}))
    await pump.on_chunk(types.ToolCall(name="write_file", args={"path": "/etc/passwd"}))
    await pump.on_relay_event("tool_result", {"id": "1", "name": "call_mcp_tool", "content": "Successfully wrote"})
    await pump.on_chunk(types.Text(step_index=0, text="Done."))
    await pump.flush()

    kinds = [entry[1] for entry in sink.logs]
    assert kinds == [LogType.THOUGHT, LogType.TOOL_CALL, LogType.TOOL_CALL, LogType.TOOL_RESULT, LogType.TEXT]
    assert sink.logs[1][2] == "filesystem-backend.write_file → backend/api/models.py"
    assert len(sink.logs[1][3]["args"]["content"]) < 2100
    assert sink.files == ["backend/api/models.py"]  # writes outside the root are never reported as files


def test_is_retryable():
    assert is_retryable(RuntimeError("HTTP 429 Too Many Requests"))
    assert is_retryable(RuntimeError("RESOURCE_EXHAUSTED: quota"))
    assert is_retryable(type("ConnectionClosedOK", (Exception,), {})("bye"))
    assert not is_retryable(ValueError("bad prompt"))
    assert not is_retryable(asyncio.TimeoutError())


async def test_live_runner_uses_fresh_agent_per_retry(tmp_path, monkeypatch):
    created = []

    class FakeResponse:
        def __init__(self, fail):
            self.fail = fail

        @property
        def chunks(self):
            async def gen():
                if self.fail:
                    raise RuntimeError("503 Service Unavailable")
                yield types.Text(step_index=0, text="all good")

            return gen()

    class FakeAgent:
        def __init__(self, config):
            self.config = config
            created.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def chat(self, prompt):
            return FakeResponse(fail=len(created) == 1)

    monkeypatch.setattr("engine.runner.Agent", FakeAgent)
    sink = _Sink()
    runner = LiveAgentRunner(_Ctx(tmp_path, sink))
    job = AgentJob(role="backend", agent_name="Backend Dev", prompt="go", config_fn=lambda url: {"base_url": url})
    assert await runner.run(job) == "all good"
    assert len(created) == 2 and created[0] is not created[1]
    assert created[0].config["base_url"].startswith("http://127.0.0.1:")
    assert any("Retrying with a fresh agent" in entry[2] for entry in sink.logs)


# --------------------------------------------------------------------------- sandbox policy
def test_view_file_sandbox_predicate(tmp_path):
    import inspect as _inspect

    from google.antigravity.hooks.policy import _evaluate_predicate

    from engine.agents.base import outside_roots

    root = tmp_path / "generated"
    (root / "backend").mkdir(parents=True)
    brain = tmp_path / "brain"
    brain.mkdir()
    pred = outside_roots([root, brain])
    call = lambda **args: types.ToolCall(name="view_file", args=args)  # noqa: E731

    assert pred(call(file_path=str(root / "backend" / "models.py"))) is False
    assert pred(call(file_path=f"file://{brain}/conv/mcp/thinking/schema.json")) is False
    assert pred(call(file_path=str(tmp_path / "secret.env"))) is True
    assert pred(call(file_path=str(root / ".." / "secret.env"))) is True  # traversal resolved first
    assert pred(call()) is True  # no path: fail closed
    # The SDK must hand the predicate the full ToolCall (it inspects the annotation).
    policy = type("P", (), {"when": staticmethod(pred)})()
    assert asyncio.run(_evaluate_predicate(policy, call(file_path="/etc/passwd"))) is True
    assert _inspect.signature(pred).parameters


def test_build_config_scopes_tools(tmp_path):
    from engine.agents import backend_dev

    ctx = _Ctx(tmp_path / "generated", _Sink())
    ctx.root.mkdir(parents=True)
    ctx.sessions_dir = tmp_path / ".sessions"
    ctx.qa_dir = tmp_path / ".qa"
    ctx.backend_dir = ctx.root / "backend"
    ctx.frontend_dir = ctx.root / "frontend"
    ctx.read = lambda rel, default="": default
    config = backend_dev.config(ctx, "backend")("http://127.0.0.1:1/v1")
    enabled = {t.value for t in config.capabilities.enabled_tools}
    assert enabled == {"finish", "view_file"}
    assert config.policies[0].name == "nexus-sandbox"
    assert [s.name for s in config.mcp_servers] == ["filesystem-backend", "agents-notes"]
    assert config.workspaces == [str((ctx.root / "backend").resolve())]


def test_nested_agent_notes_are_collected_and_never_zipped(tmp_path):
    from types import SimpleNamespace

    from engine.orchestrator import _collect_stray_notes

    root = tmp_path / "generated"
    (root / ".agents").mkdir(parents=True)
    (root / ".agents" / "fe_output.md").write_text("root notes")
    (root / "frontend" / ".agents").mkdir(parents=True)
    (root / "frontend" / ".agents" / "fe_output.md").write_text("stray fe notes")
    (root / "backend" / ".agents").mkdir(parents=True)
    (root / "backend" / ".agents" / "be_output.md").write_text("stray be notes")
    (root / "backend" / "manage.py").write_text("print(1)\n")
    ctx = SimpleNamespace(
        root=root,
        frontend_dir=root / "frontend",
        backend_dir=root / "backend",
        path=lambda rel: root / rel,
    )

    info_before = zipper.build_archive(root, tmp_path / "a.zip", "app")
    with zipfile.ZipFile(info_before.path) as zf:
        assert zf.namelist() == ["app/backend/manage.py"]  # nested .agents excluded too

    moved = _collect_stray_notes(ctx)
    assert sorted(moved) == ["backend/.agents/be_output.md", "frontend/.agents/fe_output.md"]
    assert (root / ".agents" / "be_output.md").read_text() == "stray be notes"
    assert (root / ".agents" / "fe_output.md").read_text() == "root notes\n\nstray fe notes"
    assert not (root / "frontend" / ".agents").exists() and not (root / "backend" / ".agents").exists()


def test_scrub_process_env_hides_secrets_but_engine_still_reads_them(monkeypatch):
    import os

    from engine import config as engine_config

    monkeypatch.setattr(engine_config, "_scrubbed", {})
    monkeypatch.setenv("MODEL_API_KEY", "sk-secret")
    monkeypatch.setenv("POSTGRES_DB", "nexus")
    removed = engine_config.scrub_process_env()
    assert {"MODEL_API_KEY", "POSTGRES_DB"} <= set(removed)
    assert "MODEL_API_KEY" not in os.environ and "POSTGRES_DB" not in os.environ
    assert engine_config.load_config().api_key == "sk-secret"
    assert engine_config.scrub_process_env() == []  # idempotent
    # restore for the rest of the session
    for key, value in engine_config._scrubbed.items():
        monkeypatch.setenv(key, value)
