"""Regression coverage for the hosted ArkHive birth fallback."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from mcp.types import TextContent

from sentarion_mcp import server
from sentarion_mcp.clients import HumaneNotConfigured, tool_json


@asynccontextmanager
async def _humane_unavailable():
    raise HumaneNotConfigured("no local chamber")
    yield  # pragma: no cover


def test_birth_retries_arkhive_with_string_covenant(monkeypatch):
    calls = []

    class Arkhive:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            text = "Error executing tool x" if len(calls) == 1 else '{"soul_id":"s1"}'
            return SimpleNamespace(content=[TextContent(type="text", text=text)])

    @asynccontextmanager
    async def arkhive_session():
        yield Arkhive()

    monkeypatch.setattr(server, "humane_session", _humane_unavailable)
    monkeypatch.setattr(server, "arkhive_session", arkhive_session)

    reply = asyncio.run(server.call_tool("sentarion_birth", {"name": "X", "covenant": ["a", "b"]}))

    assert calls[1][1]["covenant"] == "a; b"
    assert tool_json(SimpleNamespace(content=reply))["chain"] == "arkhive"
