"""WO-S3: orchestrate_and_record returns an honest run summary and never hides memory failures."""

import asyncio
import json
import re
from contextlib import asynccontextmanager

from mcp.types import TextContent

from sentarion_mcp import server
from sentarion_mcp.clients import HumaneNotConfigured

ALGERNON_PAYLOAD = {"results": [{"id": "a", "result": "ok"}, {"id": "b", "error": "boom"}]}


class _FakeResult:
    def __init__(self, text: str):
        self.content = [TextContent(type="text", text=text)]


class _FakeAlgernon:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return _FakeResult(json.dumps(ALGERNON_PAYLOAD))


@asynccontextmanager
async def _arkhive_down():
    raise ConnectionError("hosted chain unreachable")
    yield  # pragma: no cover


@asynccontextmanager
async def _humane_missing():
    raise HumaneNotConfigured("no local chamber")
    yield  # pragma: no cover


def _parse(content) -> dict:
    assert len(content) == 1 and content[0].type == "text"
    return json.loads(content[0].text)


def _patch_common(monkeypatch, decision: str):
    fake = _FakeAlgernon()

    async def fake_govern(action, ctx):
        return {"decision": decision, "reason": "test", "chambers": {}}

    @asynccontextmanager
    async def fake_algernon():
        yield fake

    monkeypatch.setattr(server, "govern_stub", fake_govern)
    monkeypatch.setattr(server, "algernon_session", fake_algernon)
    monkeypatch.setattr(server, "arkhive_session", _arkhive_down)
    monkeypatch.setattr(server, "humane_session", _humane_missing)
    return fake


def test_run_summary_on_approve(monkeypatch):
    fake = _patch_common(monkeypatch, "approve")
    out = _parse(asyncio.run(server.call_tool("orchestrate_and_record", {"goal": "g", "k": 2})))

    assert list(out) == ["run", "governance", "results", "summary", "memory", "v2_would_add"]
    run = out["run"]
    assert set(run) == {"run_id", "goal", "k", "actor", "started_at", "finished_at"}
    assert re.fullmatch(r"[0-9a-f]{32}", run["run_id"])
    assert run["goal"] == "g" and run["k"] == 2 and run["actor"] == "sentarion"
    for ts in (run["started_at"], run["finished_at"]):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), ts
    assert out["governance"]["decision"] == "approve"
    assert out["results"] == ALGERNON_PAYLOAD
    assert out["summary"] == {"tasks": 2, "succeeded": 1, "failed": 1}
    assert out["memory"]["arkhive"].startswith("error:")
    assert out["memory"]["humane"] == "not_configured"
    assert out["v2_would_add"] == [
        "signed run manifest",
        "typed retries",
        "SHA-bound verification evidence",
        "adversarial review gate",
    ]
    assert fake.calls == [("algernon_orchestrate", {"goal": "g", "k": 2})]


def test_block_returns_run_and_dispatched_false(monkeypatch):
    fake = _patch_common(monkeypatch, "block")
    out = _parse(asyncio.run(server.call_tool("orchestrate_and_record", {"goal": "g", "k": 2, "actor": "soul-1"})))

    assert set(out) == {"run", "governance", "dispatched"}
    assert out["dispatched"] is False
    assert out["governance"]["decision"] == "block"
    assert re.fullmatch(r"[0-9a-f]{32}", out["run"]["run_id"])
    assert out["run"]["finished_at"] is not None
    assert out["run"]["actor"] == "soul-1"
    assert fake.calls == []


def test_memory_records_include_run_id(monkeypatch):
    fake = _patch_common(monkeypatch, "approve")
    seen = []

    class _Chain:
        async def call_tool(self, name, args):
            seen.append((name, args))
            return _FakeResult("{}")

    @asynccontextmanager
    async def chain_up():
        yield _Chain()

    monkeypatch.setattr(server, "arkhive_session", chain_up)
    monkeypatch.setattr(server, "humane_session", chain_up)
    out = _parse(asyncio.run(server.call_tool("orchestrate_and_record", {"goal": "g", "k": 1})))
    assert out["memory"] == {"arkhive": "recorded", "humane": "recorded"}
    assert len(seen) == 2
    for name, args in seen:
        assert name == "remember"
        assert args["data"]["run_id"] == out["run"]["run_id"]
    assert fake.calls


def test_summary_is_zero_when_results_are_opaque():
    assert server._summarize_results("just text") == {"tasks": 0, "succeeded": 0, "failed": 0}
    assert server._summarize_results({"plan": []}) == {"tasks": 0, "succeeded": 0, "failed": 0}
    assert server._summarize_results({"results": [{"id": "x", "result": None}]}) == {"tasks": 1, "succeeded": 0, "failed": 1}
