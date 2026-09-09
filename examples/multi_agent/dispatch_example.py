"""Dispatch three tasks through Sentarion where t3 depends on t1 and t2.

Talks to the `sentarion` MCP server over stdio with the official `mcp` client
(`pip install mcp`). Provider keys are read from your environment
(ANTHROPIC_API_KEY / OPENAI_API_KEY) or the fleet falls back to a local Ollama.
Nothing secret is embedded here.

Exit codes: 0 on success, 1 with a one-line reason when the doctor reports
`ready: false`, governance blocks the dispatch, or the server cannot be started.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import sys

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover
    print("the `mcp` Python client is missing: pip install mcp")
    sys.exit(1)

TASKS = [
    {"id": "t1", "prompt": "In three bullet points, list risks of storing session tokens in localStorage.", "depends_on": []},
    {"id": "t2", "prompt": "In three bullet points, list risks of storing session tokens in cookies.", "depends_on": []},
    {
        "id": "t3",
        "prompt": (
            "Two colleagues reported these findings. Recommend one approach in five sentences.\n\n"
            "localStorage risks:\n{{t1}}\n\nCookie risks:\n{{t2}}"
        ),
        "depends_on": ["t1", "t2"],
    },
]


def _server_params() -> StdioServerParameters:
    """SENTARION_CMD (a full command line) wins; then the `sentarion` console script; then the module,
    which is what you want when running from a checkout of the repository."""
    override = os.environ.get("SENTARION_CMD")
    if override:
        argv = [a.strip('"') for a in shlex.split(override, posix=(os.name != "nt"))]
        return StdioServerParameters(command=argv[0], args=argv[1:], env=dict(os.environ))
    cmd = shutil.which("sentarion")
    if cmd:
        return StdioServerParameters(command=cmd, args=[], env=dict(os.environ))
    return StdioServerParameters(command=sys.executable, args=["-m", "sentarion_mcp.server"], env=dict(os.environ))


def _one_line(value, limit: int) -> str:
    return " ".join(str(value).split())[:limit]


def _root_cause(e: BaseException) -> BaseException:
    """anyio wraps errors raised inside stdio_client in an ExceptionGroup; report the innermost one."""
    while getattr(e, "exceptions", None):
        e = e.exceptions[0]
    return e


def _text(result) -> str:
    return "".join(b.text for b in (result.content or []) if getattr(b, "type", "") == "text")


def _json(result):
    raw = _text(result)
    try:
        return json.loads(raw)
    except ValueError:
        return raw


async def main() -> int:
    try:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                doctor = _json(await session.call_tool("sentarion_doctor", {"timeout_s": 5}))
                if not isinstance(doctor, dict) or not doctor.get("ready"):
                    failing = [k for k, v in (doctor.get("checks") or {}).items() if not v.get("ok")] if isinstance(doctor, dict) else []
                    steps = "; ".join((doctor.get("next_steps") or [])) if isinstance(doctor, dict) else "run sentarion_doctor"
                    print(f"not ready: failing checks {failing}. Fix: {steps}")
                    return 1
                print(f"doctor: ready (sentarion-mcp {doctor.get('version')})")

                out = _json(await session.call_tool("dispatch_with_dependencies", {"tasks_json": json.dumps(TASKS)}))
    except FileNotFoundError as e:
        print(f"could not start the sentarion server: {e}. Fix: pip install sentarion-mcp")
        return 1
    except Exception as e:  # noqa: BLE001
        cause = _root_cause(e)
        print(f"dispatch failed: {type(cause).__name__}: {_one_line(cause, 200)}")
        return 1

    if not isinstance(out, dict):
        print(f"unexpected server reply: {str(out)[:200]}")
        return 1
    gov = out.get("governance") or {}
    if out.get("dispatched") is False:
        print(f"blocked by governance: {gov.get('reason', 'no reason given')}")
        return 1

    print(f"governance: {gov.get('decision')} ({gov.get('reason', '')})")
    print(f"waves: {out.get('waves')}  (wave 1 = t1, t2 in parallel; wave 2 = t3 with {{{{t1}}}} and {{{{t2}}}} filled in)")
    tasks = failed = 0
    first_error = ""
    for wave_no, wave in enumerate(out.get("results") or [], start=1):
        items = wave.get("results") if isinstance(wave, dict) else None
        if not isinstance(items, list):
            print(f"  wave {wave_no}: {_one_line(wave, 200)}")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            tasks += 1
            tid = item.get("id")
            if item.get("error") or item.get("result") is None:
                failed += 1
                err = _one_line(item.get("error") or "no result", 160)
                first_error = first_error or err
                print(f"  wave {wave_no} {tid}: error: {err}")
            else:
                res = str(item.get("result", ""))
                print(f"  wave {wave_no} {tid}: {len(res)} chars: {_one_line(res, 120)}")
    print(f"data_flow: {out.get('data_flow')}")
    print(f"summary: {tasks} tasks, {tasks - failed} succeeded, {failed} failed")
    if tasks and failed == tasks:
        print(f"every task failed; first error: {first_error}. Check the provider key or Ollama that sentarion_doctor reported.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
