"""Local auth-injecting relay for OpenAI-compatible model APIs.

The Antigravity SDK's OpenAI path (``LocalOpenAIAgentConfig``) only forwards a
``base_url`` to the harness; it cannot send an API key. Moonshot requires
``Authorization: Bearer <key>``, so the engine points agents at this relay on
127.0.0.1, which adds the header and streams the upstream response back.
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Awaitable, Callable

import aiohttp
from aiohttp import web

logger = logging.getLogger(__name__)

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "content-encoding",
    "authorization",
}


class LLMRelay:
    """``async with LLMRelay(base, key) as relay: relay.base_url -> http://127.0.0.1:<port>/v1``"""

    def __init__(
        self,
        upstream_base: str,
        api_key: str,
        *,
        extra_body: dict | None = None,
        timeout: float = 900,
        on_event: Callable[[str, dict], Awaitable[None] | None] | None = None,
    ):
        """`on_event(kind, payload)` receives taps the harness does not surface as chunks:

        - ("reasoning", {"text": delta}) for `reasoning_content` deltas in the model's reply
        - ("tool_result", {"id", "name", "content"}) for each tool message sent back to the model
        """
        self.upstream_base = upstream_base.rstrip("/")
        self._on_event = on_event
        self._seen_tool_ids: set[str] = set()
        self._api_key = api_key
        self._extra_body = extra_body or {}
        self._timeout = aiohttp.ClientTimeout(total=timeout, sock_read=timeout)
        self._runner: web.AppRunner | None = None
        self._session: aiohttp.ClientSession | None = None
        self.port: int | None = None
        self.request_count = 0

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    async def __aenter__(self) -> "LLMRelay":
        self._session = aiohttp.ClientSession(timeout=self._timeout, auto_decompress=True)
        app = web.Application(client_max_size=64 * 1024 * 1024)
        app.router.add_route("*", "/v1/{tail:.*}", self._forward)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]  # noqa: SLF001
        logger.info("LLM relay listening on %s -> %s", self.base_url, self.upstream_base)
        return self

    async def __aexit__(self, *exc):
        if self._runner:
            await self._runner.cleanup()
        if self._session:
            await self._session.close()

    async def _forward(self, request: web.Request) -> web.StreamResponse:
        self.request_count += 1
        url = f"{self.upstream_base}/{request.match_info['tail']}"
        if request.query_string:
            url += f"?{request.query_string}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
        headers["Authorization"] = f"Bearer {self._api_key}"
        body = await request.read()
        if body and request.content_type == "application/json":
            body = await self._inspect_request(body)

        assert self._session is not None
        try:
            upstream = await self._session.request(request.method, url, headers=headers, data=body)
        except aiohttp.ClientError as exc:
            logger.warning("LLM relay upstream error: %s", exc)
            return web.json_response({"error": {"message": f"relay upstream error: {exc}"}}, status=502)

        async with upstream:
            if upstream.status >= 400:
                logger.warning("LLM upstream %s %s -> %s", request.method, url, upstream.status)
            response = web.StreamResponse(status=upstream.status, reason=upstream.reason)
            for key, value in upstream.headers.items():
                if key.lower() not in _HOP_BY_HOP:
                    response.headers[key] = value
            await response.prepare(request)
            is_sse = "text/event-stream" in upstream.headers.get("Content-Type", "")
            pending = b""
            collected = bytearray()
            async for chunk in upstream.content.iter_any():
                await response.write(chunk)
                if self._on_event is None or upstream.status >= 400:
                    continue
                if is_sse:
                    pending += chunk
                    *lines, pending = pending.split(b"\n")
                    for line in lines:
                        await self._tap_sse_line(line)
                else:
                    collected.extend(chunk)
            if collected:
                await self._tap_json_body(bytes(collected))
            await response.write_eof()
            return response

    async def _emit(self, kind: str, payload: dict) -> None:
        if self._on_event is None:
            return
        try:
            result = self._on_event(kind, payload)
            if inspect.isawaitable(result):
                await result
        except Exception:  # a broken listener must never break the model stream
            logger.exception("LLM relay event listener failed")

    async def _inspect_request(self, body: bytes) -> bytes:
        try:
            payload = json.loads(body)
        except ValueError:
            return body
        if not isinstance(payload, dict):
            return body
        await self._tap_tool_results(payload.get("messages") or [])
        if self._extra_body:
            for key, value in self._extra_body.items():
                payload.setdefault(key, value)
            return json.dumps(payload).encode()
        return body

    async def _tap_tool_results(self, messages: list) -> None:
        names: dict[str, str] = {}
        for message in messages:
            if not isinstance(message, dict):
                continue
            for call in message.get("tool_calls") or []:
                if isinstance(call, dict) and call.get("id"):
                    names[call["id"]] = (call.get("function") or {}).get("name", "")
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "tool":
                continue
            call_id = message.get("tool_call_id") or ""
            if not call_id or call_id in self._seen_tool_ids:
                continue
            self._seen_tool_ids.add(call_id)
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            await self._emit(
                "tool_result", {"id": call_id, "name": names.get(call_id, ""), "content": str(content or "")}
            )

    async def _tap_sse_line(self, line: bytes) -> None:
        line = line.strip()
        if not line.startswith(b"data:"):
            return
        data = line[5:].strip()
        if not data or data == b"[DONE]":
            return
        try:
            event = json.loads(data)
        except ValueError:
            return
        for choice in event.get("choices") or []:
            delta = choice.get("delta") or {}
            text = delta.get("reasoning_content") or delta.get("reasoning")
            if text:
                await self._emit("reasoning", {"text": text})

    async def _tap_json_body(self, body: bytes) -> None:
        try:
            event = json.loads(body)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        for choice in event.get("choices") or []:
            message = choice.get("message") or {}
            text = message.get("reasoning_content") or message.get("reasoning")
            if text:
                await self._emit("reasoning", {"text": text})
