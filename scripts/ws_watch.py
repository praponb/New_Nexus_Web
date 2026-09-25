#!/usr/bin/env python3
"""Watch a project's live generation stream and assert it behaves.

Usage:
  ws_watch.py --project <uuid> --token <access-jwt> [--ws-base ws://localhost:8000]
              [--timeout 3600] [--require THOUGHT,TOOL_CALL] [--quiet]

Exits 0 when `pipeline_complete` arrives and every required log type was seen,
1 on `pipeline_failed` or missing log types, 2 on timeout / connection errors.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter

import websockets

COLORS = {"THOUGHT": "\033[35m", "TOOL_CALL": "\033[36m", "TOOL_RESULT": "\033[90m", "ERROR": "\033[31m", "SYSTEM": "\033[33m"}
RESET = "\033[0m"


def fmt(log: dict) -> str:
    color = COLORS.get(log["log_type"], "")
    content = log["content"].replace("\n", " ⏎ ")
    if len(content) > 160:
        content = content[:157] + "..."
    return f"{color}#{log['sequence_num']:>4} [{log['agent_name']:<12}] {log['log_type']:<12} {content}{RESET}"


async def watch(args) -> int:
    url = f"{args.ws_base.rstrip('/')}/ws/projects/{args.project}/logs/?token={args.token}"
    required = {t.strip() for t in args.require.split(",") if t.strip()}
    seen_types: Counter = Counter()
    seen_seq: set[int] = set()
    files: set[str] = set()
    last_seq = 0
    deadline = time.monotonic() + args.timeout
    reconnects = 0

    while time.monotonic() < deadline:
        try:
            async with websockets.connect(
                url + (f"&after={last_seq}" if last_seq else ""),
                origin=args.origin,
                open_timeout=20,
                max_size=16 * 1024 * 1024,
            ) as ws:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    event = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
                    etype, data = event.get("type"), event.get("data") or {}
                    logs = data.get("logs", []) if etype == "history" else [data] if etype == "log_event" else []
                    for log in logs:
                        if log["sequence_num"] in seen_seq:
                            continue
                        seen_seq.add(log["sequence_num"])
                        last_seq = max(last_seq, log["sequence_num"])
                        seen_types[log["log_type"]] += 1
                        if not args.quiet:
                            print(fmt(log), flush=True)
                    if etype == "file_created":
                        files.add(data["path"])
                    elif etype == "phase_update" and not args.quiet:
                        print(f"--- phase {data.get('current_phase')} {data.get('progress_percentage')}% "
                              f"agents={data.get('active_agents')} files={data.get('files_created_count')}", flush=True)
                    status = data.get("status") if etype == "phase_update" else None
                    if etype == "pipeline_complete" or (status == "COMPLETED" and data.get("snapshot")):
                        missing = required - set(seen_types)
                        print(f"\nPIPELINE COMPLETE. log types={dict(seen_types)} files_streamed={len(files)} "
                              f"reconnects={reconnects}")
                        if data.get("artifact"):
                            print(f"artifact: {json.dumps(data['artifact'])}")
                        if missing:
                            print(f"MISSING required log types: {sorted(missing)}", file=sys.stderr)
                            return 1
                        return 0
                    if etype == "pipeline_failed" or (status == "FAILED" and data.get("snapshot")):
                        print(f"\nPIPELINE FAILED: {data.get('error_message')}", file=sys.stderr)
                        return 1
        except asyncio.TimeoutError:
            break
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            code = getattr(exc, "code", None) or getattr(getattr(exc, "rcvd", None), "code", None)
            if code in (4401, 4404):
                print(f"Server rejected the socket (close code {code}).", file=sys.stderr)
                return 2
            reconnects += 1
            if reconnects > 20:
                print(f"Giving up after {reconnects} reconnects: {exc}", file=sys.stderr)
                return 2
            await asyncio.sleep(min(10, reconnects))
    print("Timed out waiting for the pipeline to finish.", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--ws-base", default="ws://localhost:8000")
    parser.add_argument("--origin", default="http://localhost:3000")
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--require", default="THOUGHT,TOOL_CALL")
    parser.add_argument("--quiet", action="store_true")
    return asyncio.run(watch(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
