from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path

from .config import EngineConfig
from .events import EventSink

AGENTS_DIR = ".agents"
DDS_FILE = f"{AGENTS_DIR}/dds_output.md"
MANIFEST_FILE = f"{AGENTS_DIR}/manifest.json"
FE_OUTPUT_FILE = f"{AGENTS_DIR}/fe_output.md"
BE_OUTPUT_FILE = f"{AGENTS_DIR}/be_output.md"
QA_REPORT_FILE = f"{AGENTS_DIR}/qa_report.md"
REPAIR_PLAN_FILE = f"{AGENTS_DIR}/repair_plan.md"
REQUIREMENT_FILE = f"{AGENTS_DIR}/user_requirement.md"


def resume_problem(root: Path, requirement: str) -> str | None:
    """Why a failed run in `root` can't be continued in place, or None if it can."""
    if not all((root / f).is_file() for f in (DDS_FILE, MANIFEST_FILE, QA_REPORT_FILE)):
        return "Nothing to continue: the last run never reached QA. Start a full generation instead."
    try:
        saved = (root / REQUIREMENT_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        saved = None
    if saved != requirement:
        return "The requirement changed since the last run. Start a full generation instead."
    return None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class PipelineContext:
    task_id: str
    project_id: str
    project_name: str
    project_slug: str
    project_description: str
    workspace: Path  # MEDIA_ROOT/workspaces/{user}/{project}
    root: Path  # workspace/generated — the generated app root, agents' "./"
    requirement: str
    config: EngineConfig
    sink: EventSink
    qa_iteration: int = 0
    resume: bool = False  # skip plan/build and repair from the last QA report
    resume_from: int = 0  # QA loop the resumed run's report came from
    qa_backend_port: int = field(default_factory=free_port)
    qa_frontend_port: int = field(default_factory=free_port)

    @property
    def frontend_dir(self) -> Path:
        return self.root / "frontend"

    @property
    def backend_dir(self) -> Path:
        return self.root / "backend"

    @property
    def qa_dir(self) -> Path:
        """Scratch space for QA tooling (venvs, logs); outside the generated root, never zipped."""
        return self.workspace / ".qa"

    @property
    def sessions_dir(self) -> Path:
        return self.workspace / ".sessions"

    def path(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str, default: str = "") -> str:
        p = self.path(rel)
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, IsADirectoryError):
            return default

    def rel(self, path: str | Path) -> str | None:
        """Return `path` relative to the generated root, or None if it lies outside."""
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        try:
            return p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return None
