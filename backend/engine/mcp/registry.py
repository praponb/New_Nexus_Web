"""Verified MCP server configurations.

Every server gets an explicit ``name=`` matching ``^[a-zA-Z0-9_-]+$`` (§6.4), and
every filesystem server is rooted inside the project's generated workspace (§10.2).
"""

from __future__ import annotations

from pathlib import Path

from google.antigravity import types

MCP_TIMEOUT_SECONDS = 180


def thinking() -> types.McpStdioServer:
    return types.McpStdioServer(
        name="thinking",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
        timeout_seconds=MCP_TIMEOUT_SECONDS,
    )


def filesystem(root: Path, name: str = "filesystem") -> types.McpStdioServer:
    """Note: when the client advertises MCP roots (the harness sends the agent's `workspaces`),
    server-filesystem replaces `root` with those roots. Scope access through `workspaces`."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return types.McpStdioServer(
        name=name,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(root)],
        timeout_seconds=MCP_TIMEOUT_SECONDS,
    )


def playwright(output_dir: Path) -> types.McpStdioServer:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return types.McpStdioServer(
        name="playwright",
        command="npx",
        args=["-y", "@playwright/mcp@latest", "--headless", "--isolated", "--output-dir", str(output_dir)],
        timeout_seconds=MCP_TIMEOUT_SECONDS,
    )
