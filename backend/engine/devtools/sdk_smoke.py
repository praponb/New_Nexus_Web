"""Live smoke test: one agent turn against the configured model through the relay.

Usage: cd backend && ../.venv/bin/python -m engine.devtools.sdk_smoke <workspace_dir>
Checks that Thought/Text/ToolCall chunks stream back and that an MCP filesystem
write lands inside the workspace.
"""

import asyncio
import collections
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus_backend.settings")
import django  # noqa: E402

django.setup()

from google.antigravity import Agent, types  # noqa: E402
from google.antigravity.connections.local.local_openai_connection_config import LocalOpenAIAgentConfig  # noqa: E402
from google.antigravity.policy import allow_all  # noqa: E402

from engine.config import load_config  # noqa: E402
from engine.llm_relay import LLMRelay  # noqa: E402


async def main(workspace: Path) -> int:
    cfg = load_config()
    workspace.mkdir(parents=True, exist_ok=True)
    target = workspace / "hello.txt"
    target.unlink(missing_ok=True)
    print(f"config: {cfg!r}", flush=True)
    extra = {"reasoning_effort": cfg.reasoning_effort} if cfg.reasoning_effort else None
    print(f"extra body keys: {list(extra or {})}", flush=True)
    taps = collections.Counter()

    def on_event(kind, payload):
        taps[kind] += 1
        if kind == "tool_result" or taps[kind] <= 2:
            print(f"  tap {kind}: {str(payload)[:100]!r}", flush=True)

    async with LLMRelay(cfg.api_base, cfg.api_key, extra_body=extra, on_event=on_event) as relay:
        config = LocalOpenAIAgentConfig(
            model=cfg.model_name,
            base_url=relay.base_url,
            system_instructions="You are a careful engineer. Use the filesystem MCP tools to write files.",
            mcp_servers=[
                types.McpStdioServer(
                    name="filesystem",
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", str(workspace)],
                )
            ],
            workspaces=[str(workspace)],
            policies=[allow_all()],
            # --restricted mirrors engine.agents.base.build_config: no builtin file tools.
            capabilities=(
                types.CapabilitiesConfig(enable_subagents=False, enabled_tools=[types.BuiltinTools.FINISH])
                if RESTRICTED
                else None
            ),
        )
        counts = collections.Counter()
        async with Agent(config) as agent:
            response = await agent.chat(
                f"Think briefly, then use the filesystem MCP server's write_file tool to create "
                f"{target} containing exactly the text: nexus smoke ok. Then reply DONE."
            )
            async for chunk in response.chunks:
                kind = type(chunk).__name__
                counts[kind] += 1
                if kind == "ToolCall":
                    print(f"  ToolCall name={chunk.name} server={chunk.server_name} args={list(chunk.args)}", flush=True)
                elif kind == "ToolResult":
                    print(f"  ToolResult name={chunk.name} error={chunk.error!r}", flush=True)
                elif counts[kind] <= 3:
                    print(f"  {kind}: {getattr(chunk, 'text', '')[:80]!r}", flush=True)
        print(f"chunk counts: {dict(counts)}; taps: {dict(taps)}; relay requests: {relay.request_count}")
    ok = target.exists() and "nexus smoke ok" in target.read_text()
    print(f"file written: {ok}")
    return 0 if ok and counts["ToolCall"] else 1


RESTRICTED = "--restricted" in sys.argv

if __name__ == "__main__":
    target_dir = next(a for a in sys.argv[1:] if not a.startswith("--"))
    sys.exit(asyncio.run(asyncio.wait_for(main(Path(target_dir).resolve()), timeout=600)))
