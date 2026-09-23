"""sentarion_birth must bear the identity on BOTH chains, and never crash when a chamber cannot answer.

Measured 2026-09-10 from a clean `pip install sentarion-mcp==0.3.0`: birth went to the local chamber only, so the
very next `remember` was refused on the hosted chain ("'probe' is not a born soul"); and when the local chamber's
chain file was unreadable the tool died with "unhandled errors in a TaskGroup" - the first two things a stranger
sees. This file is the regression net for both.
"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from mcp.types import TextContent

from sentarion_mcp import server
from sentarion_mcp.clients import HumaneNotConfigured, tool_json

try:
    ExceptionGroup  # noqa: B018 - Python 3.11+ builtin
except NameError:  # pragma: no cover - Python 3.10, where server._exc_name() only
    class ExceptionGroup(Exception):  # duck-types on .exceptions, never the real type
        def __init__(self, message, exceptions):
            super().__init__(message)
            self.exceptions = exceptions


def _text(text):
    return SimpleNamespace(content=[TextContent(type="text", text=text)])


def _birth(monkeypatch, humane, arkhive, name="Ember"):
    monkeypatch.setattr(server, "humane_session", humane)
    monkeypatch.setattr(server, "arkhive_session", arkhive)
    reply = asyncio.run(server.call_tool("sentarion_birth", {"name": name, "covenant": ["truth over comfort"]}))
    return tool_json(SimpleNamespace(content=reply))


def test_birth_lands_on_both_chains_and_names_the_cross_chain_actor(monkeypatch):
    calls = []

    class Chain:
        def __init__(self, tag, seq):
            self.tag, self.seq = tag, seq

        async def call_tool(self, name, arguments):
            calls.append((self.tag, name, arguments))
            return _text('{"soul_id": "ember-ri-%03d", "name": "Ember", "status": "BORN"}' % self.seq)

    @asynccontextmanager
    async def humane_session():
        yield Chain("humane", 1)

    @asynccontextmanager
    async def arkhive_session():
        yield Chain("arkhive", 7)          # the hosted chain is shared: its sequence differs

    out = _birth(monkeypatch, humane_session, arkhive_session)
    assert [(c[0], c[1]) for c in calls] == [("humane", "birth"), ("arkhive", "birth")]
    assert out["humane"]["soul_id"] == "ember-ri-001" and out["arkhive"]["soul_id"] == "ember-ri-007"
    assert out["born_on"] == ["humane", "arkhive"]
    # the handle that resolves on BOTH chains is the birth name, and the tool says so
    assert out["actor"] == "Ember" and "actor='Ember'" in out["next"]
    # backward compatible: chain + result still name the first chain that bore the identity
    assert out["chain"] == "humane" and out["result"]["soul_id"] == "ember-ri-001"
    assert "error" not in out


def test_a_chamber_that_cannot_open_its_chain_is_a_readable_answer_not_a_crash(monkeypatch):
    class Broken:
        async def call_tool(self, name, arguments):
            raise ExceptionGroup("unhandled errors in a TaskGroup", [RuntimeError("unable to open database file")])

    class Hosted:
        async def call_tool(self, name, arguments):
            return _text('{"soul_id": "ember-ri-003", "name": "Ember"}')

    @asynccontextmanager
    async def humane_session():
        yield Broken()

    @asynccontextmanager
    async def arkhive_session():
        yield Hosted()

    out = _birth(monkeypatch, humane_session, arkhive_session)
    assert out["humane"]["error"] == "RuntimeError" and "ARKHIVE_DB" in out["humane"]["fix"]
    assert out["born_on"] == ["arkhive"] and out["chain"] == "arkhive" and out["result"]["soul_id"] == "ember-ri-003"
    assert "error" not in out                               # one chain bore it: the identity exists


def test_no_chain_at_all_says_not_born_with_both_causes(monkeypatch):
    @asynccontextmanager
    async def humane_session():
        raise HumaneNotConfigured("no local chamber")
        yield  # pragma: no cover

    class Down:
        async def call_tool(self, name, arguments):
            raise ConnectionError("hosted down")

    @asynccontextmanager
    async def arkhive_session():
        yield Down()

    out = _birth(monkeypatch, humane_session, arkhive_session)
    assert out["humane"] == "not_configured" and out["arkhive"]["error"] == "ConnectionError"
    assert out["error"] == "not_born" and out["born_on"] == [] and out["chain"] is None and out["result"] is None
