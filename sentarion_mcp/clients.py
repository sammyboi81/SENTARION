"""
Thin MCP client wrappers around the three real, already-published servers:

  - Algernon (algernon-mcp on PyPI, github.com/sammyboi81/algernon)
      tools: algernon_plan, algernon_dispatch, algernon_orchestrate
  - ArkHive (github.com/sammyboi81/arkhive, hosted at
      https://arkhive.dondatabrain.com/mcp)
      tools: birth, remember, recall, verify, govern
  - Humane Intelligence (local covenant server)
      tools: birth, remember, recall, verify, govern (zero-LLM rule gate)

Sentarion does not reimplement any of them — it connects to all three as an
MCP client and composes their tools. ArkHive is the hosted tamper-evident
chain; Humane is the local covenant/identity gate; Algernon is the fan-out
muscle. The `govern` gate is fail-closed (see govern_stub.py).

Configuration (env vars, all optional):
  ARKHIVE_MCP_URL         hosted ArkHive endpoint (default: the public one)
  SENTARION_ALGERNON_CMD  full path/command for the Algernon server
  SENTARION_HUMANE_CMD    command for the Humane server (e.g. a python.exe)
  SENTARION_HUMANE_ARGS   args for the Humane command, JSON array or
                          whitespace-separated (e.g. the server.py path)
"""

from __future__ import annotations

import json
import os
import shutil
import site
import sys
import sysconfig
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

ARKHIVE_URL = os.getenv("ARKHIVE_MCP_URL", "https://arkhive.dondatabrain.com/mcp")

_EXE = ".exe" if sys.platform == "win32" else ""


def _resolve_algernon() -> list[str]:
    """Find the Algernon server executable without trusting PATH alone.

    0.1.x spawned the bare name `algernon`, which raised WinError 2 whenever
    pip's --user Scripts directory was not on PATH. Resolution order:
      1. SENTARION_ALGERNON_CMD env override
      2. shutil.which("algernon")
      3. the user-scheme scripts dir (pip install --user)
      4. the scripts dir next to the running interpreter
      5. any site-packages sibling Scripts/bin dir
    """
    override = os.getenv("SENTARION_ALGERNON_CMD")
    if override:
        return [override]

    found = shutil.which("algernon")
    if found:
        return [found]

    candidates = []
    try:
        candidates.append(sysconfig.get_path("scripts", f"{os.name}_user"))
    except KeyError:
        pass
    candidates.append(sysconfig.get_path("scripts"))
    candidates.append(os.path.join(os.path.dirname(sys.executable), "Scripts"))
    candidates.append(os.path.join(os.path.dirname(sys.executable), "bin"))
    for pkg_dir in site.getsitepackages() + [site.getusersitepackages()]:
        candidates.append(os.path.join(os.path.dirname(pkg_dir), "Scripts"))

    for d in candidates:
        if not d:
            continue
        exe = os.path.join(d, "algernon" + _EXE)
        if os.path.isfile(exe):
            return [exe]

    # Last resort: hand the bare name to the OS and let the error surface.
    return ["algernon"]


def _resolve_humane() -> list[str] | None:
    """Build the Humane server command from env config. None = not configured."""
    cmd = os.getenv("SENTARION_HUMANE_CMD")
    raw_args = os.getenv("SENTARION_HUMANE_ARGS", "")
    if not cmd:
        found = shutil.which("humane-intelligence") or shutil.which("humane-mcp")
        return [found] if found else None
    if raw_args.strip().startswith("["):
        args = json.loads(raw_args)
    else:
        args = raw_args.split()
    return [cmd, *args]


@asynccontextmanager
async def algernon_session():
    """Launches the local Algernon MCP process (installed via `pip install algernon-mcp`)."""
    argv = _resolve_algernon()
    params = StdioServerParameters(
        command=argv[0], args=argv[1:], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def arkhive_session():
    """Connects to the hosted ArkHive MCP server over streamable HTTP."""
    async with streamablehttp_client(ARKHIVE_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


class HumaneNotConfigured(RuntimeError):
    """Raised when a Humane-dependent tool runs with no Humane server configured."""


@asynccontextmanager
async def humane_session():
    """Launches the local Humane Intelligence MCP process (covenant gate)."""
    argv = _resolve_humane()
    if not argv:
        raise HumaneNotConfigured(
            "Humane server not configured: set SENTARION_HUMANE_CMD "
            "(and SENTARION_HUMANE_ARGS) or put `humane-intelligence` on PATH."
        )
    params = StdioServerParameters(
        command=argv[0], args=argv[1:], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def tool_text(result) -> str:
    """Flatten an MCP tool result's text content blocks into one string."""
    raw = ""
    for block in getattr(result, "content", []) or []:
        if getattr(block, "type", "") == "text":
            raw += block.text
    return raw


def tool_json(result):
    """Parse a tool result's text as JSON, falling back to the raw string."""
    raw = tool_text(result)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def tool_records(result) -> list[dict]:
    """Parse a recall-style result into a list of dict records.

    Tolerates three shapes the upstream chains actually emit:
      * a single JSON array of objects,
      * concatenated JSON objects (ArkHive hosted),
      * newline-delimited JSON objects.
    Anything unparseable yields an empty list rather than raising.
    """
    raw = tool_text(result).strip()
    if not raw:
        return []
    # Shape 1: a proper JSON array (or a lone object).
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            return [data]
    except (json.JSONDecodeError, ValueError):
        pass
    # Shapes 2 & 3: stream concatenated / newline-delimited objects.
    records: list[dict] = []
    decoder = json.JSONDecoder()
    i, n = 0, len(raw)
    while i < n:
        while i < n and raw[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        try:
            obj, end = decoder.raw_decode(raw, i)
        except (json.JSONDecodeError, ValueError):
            break
        if isinstance(obj, dict):
            records.append(obj)
        i = end
    return records


def record_ts(rec: dict) -> str:
    """Best-effort timestamp key across chains (ArkHive 'ts', Humane 'timestamp'/'ts')."""
    return str(rec.get("ts") or rec.get("timestamp") or "")
