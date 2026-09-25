"""Agent runners. `LiveAgentRunner` drives the Antigravity SDK; the mock lives in mock_engine."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from google.antigravity import Agent, types

from apps.projects.models import LogType

from .agents.base import AgentJob
from .context import PipelineContext
from .llm_relay import LLMRelay

logger = logging.getLogger(__name__)

RETRYABLE_MARKERS = (
    "429",
    "503",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "overloaded",
    "connectionclosed",
    "connection closed",
    "server disconnected",
    "harness process exited unexpectedly",  # the harness dropped its WebSocket mid-turn (close 1006)
    "unexpected eof",  # the model API reset a streaming response mid-turn
    "network issue",
    "connection reset",
    "payload is not completed",
)
RETRY_PREAMBLE = """\
Note: a previous attempt at this task was interrupted by a connection failure. Files it wrote may
already be on disk. Check what exists first and finish or correct it; do not start over.

"""
WRITE_TOOLS = {"write_file", "edit_file", "create_file", "move_file"}
ARG_PREVIEW_CHARS = 2000
RESULT_PREVIEW_CHARS = 6000
THOUGHT_FLUSH_CHARS = 700
THOUGHT_MIN_CHARS = 160
_SENTENCE_END = re.compile(r"[.!?:]\s*$|\n\s*$")


class AgentRunError(RuntimeError):
    pass


def is_retryable(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in RETRYABLE_MARKERS)


def _preview_args(args: dict) -> dict:
    out = {}
    for key, value in (args or {}).items():
        if isinstance(value, str) and len(value) > ARG_PREVIEW_CHARS:
            out[key] = value[:ARG_PREVIEW_CHARS] + f"… [{len(value)} chars]"
        else:
            out[key] = value
    return out


class StreamPump:
    """Maps SDK chunks + relay taps onto AgentStepLog events for one agent turn."""

    def __init__(self, ctx: PipelineContext, agent_name: str):
        self.ctx = ctx
        self.sink = ctx.sink
        self.agent_name = agent_name
        self._thought = ""
        self._text = ""
        self.full_text: list[str] = []
        self.tool_calls = 0
        self.files_written: set[str] = set()

    async def _flush_thought(self, force: bool = False) -> None:
        buf = self._thought
        if not buf.strip():
            self._thought = ""
            return
        if force or len(buf) >= THOUGHT_FLUSH_CHARS or (len(buf) >= THOUGHT_MIN_CHARS and _SENTENCE_END.search(buf)):
            self._thought = ""
            await self.sink.log(self.agent_name, LogType.THOUGHT, buf.strip())

    async def _flush_text(self) -> None:
        if self._text.strip():
            await self.sink.log(self.agent_name, LogType.TEXT, self._text.strip())
        self._text = ""

    async def flush(self) -> None:
        await self._flush_thought(force=True)
        await self._flush_text()

    async def on_relay_event(self, kind: str, payload: dict) -> None:
        if kind == "reasoning":
            self._thought += payload.get("text", "")
            await self._flush_thought()
        elif kind == "tool_result":
            await self._flush_thought(force=True)
            content = payload.get("content", "")
            preview = content if len(content) <= RESULT_PREVIEW_CHARS else content[:RESULT_PREVIEW_CHARS] + "… [truncated]"
            await self.sink.log(
                self.agent_name,
                LogType.TOOL_RESULT,
                preview,
                {"tool_call_id": payload.get("id"), "tool": payload.get("name"), "length": len(content)},
            )

    async def on_chunk(self, chunk) -> None:
        if isinstance(chunk, types.Thought):
            self._thought += chunk.text
            await self._flush_thought()
        elif isinstance(chunk, types.Text):
            await self._flush_thought(force=True)
            self._text += chunk.text
            self.full_text.append(chunk.text)
        elif isinstance(chunk, types.ToolCall):
            await self.flush()
            await self._on_tool_call(chunk)
        elif isinstance(chunk, types.ToolResult):
            await self._flush_thought(force=True)
            body = chunk.error or (chunk.result if isinstance(chunk.result, str) else json.dumps(chunk.result, default=str))
            await self.sink.log(
                self.agent_name,
                LogType.TOOL_RESULT if not chunk.error else LogType.ERROR,
                (body or "")[:RESULT_PREVIEW_CHARS],
                {"tool": str(getattr(chunk.name, "value", chunk.name)), "tool_call_id": chunk.id},
            )

    async def _on_tool_call(self, call: types.ToolCall) -> None:
        self.tool_calls += 1
        name = str(getattr(call.name, "value", call.name))
        server = call.server_name or "builtin"
        args = call.args or {}
        target = args.get("path") or args.get("file_path") or args.get("destination") or args.get("CommandLine") or ""
        label = f"{server}.{name}" + (f" → {self.ctx.rel(target) or target}" if isinstance(target, str) and target else "")
        await self.sink.log(
            self.agent_name,
            LogType.TOOL_CALL,
            label,
            {"tool": name, "server": server, "tool_call_id": call.id, "args": _preview_args(args)},
        )
        if name in WRITE_TOOLS and isinstance(target, str) and target:
            rel = self.ctx.rel(target)
            if rel:
                self.files_written.add(rel)
                await self.sink.file_created(self.agent_name, rel, name)


class LiveAgentRunner:
    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        self.agent_timeout = float(os.environ.get("NEXUS_AGENT_TIMEOUT_SECONDS", str(45 * 60)))

    async def run(self, job: AgentJob) -> str:
        cfg = self.ctx.config
        extra_body = {"reasoning_effort": cfg.reasoning_effort} if cfg.reasoning_effort else None
        attempts = max(1, cfg.retry_attempts)
        for attempt in range(1, attempts + 1):
            pump = StreamPump(self.ctx, job.agent_name)
            try:
                async with LLMRelay(
                    cfg.api_base,
                    cfg.api_key,
                    extra_body=extra_body,
                    read_timeout=cfg.relay_read_timeout,
                    on_event=pump.on_relay_event,
                ) as relay:
                    # A fresh Agent per attempt: never reuse a session whose connection has closed (§6.4).
                    async with Agent(job.config_fn(relay.base_url)) as agent:
                        prompt = job.prompt if attempt == 1 else RETRY_PREAMBLE + job.prompt
                        response = await agent.chat(prompt)

                        async def _drain():
                            async for chunk in response.chunks:
                                await pump.on_chunk(chunk)

                        await asyncio.wait_for(_drain(), timeout=self.agent_timeout)
                await pump.flush()
                return "".join(pump.full_text)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await pump.flush()
                if attempt < attempts and is_retryable(exc):
                    delay = cfg.retry_initial_backoff * (2 ** (attempt - 1))
                    await self.ctx.sink.log(
                        job.agent_name,
                        LogType.SYSTEM,
                        f"Agent connection or model API failed ({type(exc).__name__}: {str(exc)[:200]}). "
                        f"Retrying with a fresh agent in {int(delay)}s (attempt {attempt + 1}/{attempts}).",
                        {"attempt": attempt, "retry_in": delay},
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Agent %s failed", job.agent_name)
                raise AgentRunError(f"{job.agent_name} agent failed: {type(exc).__name__}: {exc}") from exc
        raise AgentRunError(f"{job.agent_name} agent failed after {attempts} attempts")
