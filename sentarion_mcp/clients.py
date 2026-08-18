"""
Thin MCP client wrappers around the two real, already-published servers:

  - Algernon (algernon-mcp on PyPI, github.com/sammyboi81/algernon)
      tools: algernon_plan, algernon_dispatch, algernon_orchestrate
  - ArkHive (github.com/sammyboi81/arkhive, hosted at
      https://arkhive.dondatabrain.com/mcp)
      tools: birth, remember, recall, verify, govern

Sentarion does not reimplement either server — it connects to both as an
MCP client and composes their tools. The `govern` gate is wired for real
(fail-closed) in govern_stub.py.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

ARKHIVE_URL = os.getenv("ARKHIVE_MCP_URL", "https://arkhive.dondatabrain.com/mcp")


@asynccontextmanager
async def algernon_session():
    """Launches the local Algernon MCP process (installed via `pip install algernon-mcp`)."""
    params = StdioServerParameters(command="algernon", args=[], env=dict(os.environ))
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
