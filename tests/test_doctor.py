"""WO-S2: sentarion_doctor never raises, never leaks secrets, and is registered.

Everything is monkeypatched; these tests never touch the network or spawn a process.
"""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from sentarion_mcp import doctor

KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SENTARION_FLEET_PROVIDER", "ALGERNON_PROVIDER")
CHECK_KEYS = ("git", "algernon", "local_chamber", "arkhive_hosted", "fleet_provider", "ollama", "api_key")


@asynccontextmanager
async def _unreachable():
    raise ConnectionError("hosted chain unreachable")
    yield  # pragma: no cover


def _all_failing(monkeypatch):
    monkeypatch.setattr(doctor, "_resolve_algernon", lambda: ["/nonexistent/algernon"])
    monkeypatch.setattr(doctor, "_resolve_humane", lambda: None)
    monkeypatch.setattr(doctor, "arkhive_session", _unreachable)
    monkeypatch.setattr(doctor, "_ollama_up", lambda base: False)
    monkeypatch.setattr(doctor, "_fetch_pypi_version", lambda timeout_s: None)
    for var in KEY_VARS:
        monkeypatch.delenv(var, raising=False)


def test_shape_all_failing(monkeypatch):
    _all_failing(monkeypatch)
    out = asyncio.run(doctor.run_doctor(0.5))

    assert set(out) == {"version", "upgrade_available", "checks", "ready", "next_steps"}
    assert out["version"] == doctor.__version__
    assert out["upgrade_available"] is None
    assert set(out["checks"]) == set(CHECK_KEYS)
    for name in CHECK_KEYS:
        check = out["checks"][name]
        assert set(check) == {"ok", "detail"}
        assert isinstance(check["ok"], bool)
        assert isinstance(check["detail"], str) and check["detail"]
    assert out["ready"] is False
    assert isinstance(out["next_steps"], list) and out["next_steps"]
    # git may legitimately be present on the test machine; everything else must fail here.
    for name in ("algernon", "local_chamber", "arkhive_hosted", "fleet_provider", "ollama", "api_key"):
        assert out["checks"][name]["ok"] is False, name
    json.dumps(out)  # must be JSON-serializable


def test_secret_never_leaks(monkeypatch):
    _all_failing(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TESTSECRET123")
    out = asyncio.run(doctor.run_doctor(0.5))
    assert "TESTSECRET123" not in json.dumps(out)
    assert out["checks"]["api_key"]["ok"] is True
    assert out["checks"]["fleet_provider"]["ok"] is True


def test_upgrade_available_when_pypi_differs(monkeypatch):
    _all_failing(monkeypatch)
    monkeypatch.setattr(doctor, "_fetch_pypi_version", lambda timeout_s: "99.0.0")
    out = asyncio.run(doctor.run_doctor(0.5))
    assert out["upgrade_available"] == "99.0.0"


def test_tool_registered():
    from sentarion_mcp import server

    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert "sentarion_doctor" in names
    tool = next(t for t in tools if t.name == "sentarion_doctor")
    assert tool.inputSchema["properties"]["timeout_s"]["default"] == 3
    assert tool.inputSchema["required"] == []


def test_present_reads_env_without_returning_it(monkeypatch):
    monkeypatch.setenv("SOME_TOKEN", "abc")
    assert doctor._present("SOME_TOKEN") is True
    monkeypatch.delenv("SOME_TOKEN")
    assert doctor._present("SOME_TOKEN") is False


@pytest.mark.parametrize("timeout", [0.5, 3.0])
def test_never_raises_with_broken_helpers(monkeypatch, timeout):
    def _boom():
        raise RuntimeError("resolver exploded")

    monkeypatch.setattr(doctor, "_resolve_algernon", _boom)
    monkeypatch.setattr(doctor, "_resolve_humane", _boom)
    monkeypatch.setattr(doctor, "arkhive_session", _unreachable)
    monkeypatch.setattr(doctor, "_ollama_up", lambda base: (_ for _ in ()).throw(ValueError("x")))
    monkeypatch.setattr(doctor, "_fetch_pypi_version", lambda timeout_s: None)
    out = asyncio.run(doctor.run_doctor(timeout))
    assert out["ready"] is False
    assert "RuntimeError" in out["checks"]["algernon"]["detail"]
    assert "ValueError" in out["checks"]["ollama"]["detail"]
