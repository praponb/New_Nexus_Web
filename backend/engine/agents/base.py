"""Shared agent plumbing: the job description passed to runners and SDK config building."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from google.antigravity import types
from google.antigravity.connections.local.local_openai_connection_config import LocalOpenAIAgentConfig
from google.antigravity.policy import allow_all, deny

from ..context import AGENTS_DIR, PipelineContext

# The harness materialises MCP tool schemas as files under this directory and expects the model
# to read them with the builtin view_file tool, so view_file stays enabled but path-scoped.
HARNESS_BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"
_PATH_ARGS = ("file_path", "AbsolutePath", "path", "uri")

TEAM_LEAD = "Team Lead"
FRONTEND_DEV = "Frontend Dev"
BACKEND_DEV = "Backend Dev"
QA_TESTER = "QA"


@dataclass
class AgentJob:
    """One agent turn. `role` drives the mock runner; `config_fn`/`prompt` drive the live one."""

    role: str  # architect | frontend | backend | qa | architect_repair | frontend_repair | backend_repair
    agent_name: str
    prompt: str
    config_fn: Callable[[str], LocalOpenAIAgentConfig]
    extra: dict = field(default_factory=dict)


SHARED_RULES = """\
Operating rules (non-negotiable):
- You work fully autonomously. Never ask the user questions; make sensible, documented assumptions.
- Your working directory on disk is: {root}
  Every path you pass to a tool MUST be absolute; relative paths are rejected. All code goes
  under that directory. The only other files you may write are the notes/summary files you are
  explicitly asked to write, at the exact absolute path given. Never touch anything else.
- Write every file with the filesystem MCP tools (write_file / edit_file / create_directory).
  Write complete, working file contents: no placeholders, no "TODO: implement", no elided code.
- Keep going until your whole assignment is written, then reply with a short summary.
"""

# Developer agents are rooted in their own subtree; build_config also exposes the notes directory.
DEV_NOTES_RULE = """\
- Your `{server}` server can write two directories: your working directory above, and the
  notes directory {notes}. Write notes/summary files there with absolute paths
  ({notes}/<file>.md), never inside your working directory.
"""


def outside_roots(allowed: list[Path]):
    """Policy predicate: True (→ deny) when a file tool targets a path outside `allowed`."""
    roots = [Path(r).resolve() for r in allowed]

    def _outside(call: types.ToolCall) -> bool:
        raw = call.canonical_path or next((call.args.get(k) for k in _PATH_ARGS if call.args.get(k)), "")
        if not isinstance(raw, str) or not raw.strip():
            return True  # fail closed
        path = Path(raw.strip().removeprefix("file://")).expanduser().resolve()
        return not any(path == root or root in path.parents for root in roots)

    return _outside


def build_config(
    ctx: PipelineContext,
    base_url: str,
    *,
    session: str,
    system_instructions: str,
    mcp_servers: list[types.McpServerConfig],
    workspace: Path | None = None,
    allow_commands: bool = False,
) -> LocalOpenAIAgentConfig:
    enabled = [types.BuiltinTools.FINISH, types.BuiltinTools.VIEW_FILE]
    run_command_config = None
    root = (workspace or ctx.root).resolve()
    notes_dir = (ctx.root / AGENTS_DIR).resolve()
    # The harness advertises `workspaces` as MCP roots, and server-filesystem REPLACES its
    # command-line directories with them. A developer rooted in its own subtree therefore needs
    # the notes directory listed here, or every write to .agents/ is denied.
    workspaces = [root] if notes_dir == root or root in notes_dir.parents else [root, notes_dir]
    sandbox = deny(
        types.BuiltinTools.VIEW_FILE.value,
        when=outside_roots([*workspaces, HARNESS_BRAIN_DIR]),
        name="nexus-sandbox",
        reason="Reads are limited to the project workspace.",
    )
    if allow_commands:
        enabled.append(types.BuiltinTools.RUN_COMMAND)
        run_command_config = types.RunCommandConfig(enable_daemons=True, timeout_seconds=900, enable_sandbox=True)
    save_dir = ctx.sessions_dir / session
    save_dir.mkdir(parents=True, exist_ok=True)
    return LocalOpenAIAgentConfig(
        model=ctx.config.model_name,
        base_url=base_url,
        system_instructions=system_instructions,
        capabilities=types.CapabilitiesConfig(
            enable_subagents=False,
            enabled_tools=enabled,
            run_command_config=run_command_config,
        ),
        mcp_servers=mcp_servers,
        workspaces=[str(w) for w in workspaces],
        policies=[sandbox, allow_all()],
        save_dir=str(save_dir),
    )
