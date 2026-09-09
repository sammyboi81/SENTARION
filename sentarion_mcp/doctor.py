"""
sentarion_doctor — a read-only health check for everything Sentarion depends on.

Reports, without ever raising and without ever printing a secret value:
  git, Algernon (dispatch), the local covenant chamber, hosted ArkHive, the fleet
  provider Algernon would use, a local Ollama, and whether an API key is set.

Helpers from .clients are bound as module-level names so tests can monkeypatch
`doctor._resolve_algernon`, `doctor._resolve_humane`, `doctor._ollama_up`,
`doctor.arkhive_session`, `doctor.algernon_session`, `doctor.humane_session`
and `doctor._fetch_pypi_version` without touching the network or spawning anything.
"""

from __future__ import annotations

import asyncio
import builtins
import os
import re
import shutil

import httpx

from . import __version__
from .clients import (  # noqa: F401  (re-exported for monkeypatching)
    ARKHIVE_URL,
    _ollama_up,
    _resolve_algernon,
    _resolve_humane,
    algernon_session,
    arkhive_session,
    humane_session,
)

PYPI_JSON_URL = "https://pypi.org/pypi/sentarion-mcp/json"
DEFAULT_OLLAMA = "http://127.0.0.1:11434"

_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def _present(name: str) -> bool:
    """True when the env var is set to a non-empty value. Never returns the value."""
    return bool(os.environ.get(name))


def _scrub(text: str) -> str:
    """Remove the value of any secret-looking env var from a string, as a last line of defence."""
    out = str(text)
    for name, value in os.environ.items():
        upper = name.upper()
        if (
            value
            and len(value) >= 8
            and any(m in upper for m in _SECRET_MARKERS)
            and re.fullmatch(r"[A-Za-z]+", value) is None
        ):
            out = out.replace(value, f"<{name}>")
    return out


_EXC_GROUP = getattr(builtins, "BaseExceptionGroup", None)  # Python 3.11+; absent on 3.10


def _fail_detail(prefix: str, exc: BaseException) -> str:
    if _EXC_GROUP is not None and isinstance(exc, _EXC_GROUP) and exc.exceptions:
        return _fail_detail(prefix, exc.exceptions[0])
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    detail = f"{prefix} ({type(exc).__name__}"
    if msg:
        detail += f": {msg[:100]}"
    return _scrub(detail + ")")


def _fetch_pypi_version(timeout_s: float) -> str | None:
    """Latest published version of sentarion-mcp, or None on any error."""
    try:
        r = httpx.get(PYPI_JSON_URL, timeout=timeout_s, follow_redirects=True)
        if r.status_code != 200:
            return None
        v = (r.json().get("info") or {}).get("version")
        return str(v) if v else None
    except Exception:  # noqa: BLE001
        return None


async def _probe_session(session_factory, required_tool: str) -> tuple[bool, str]:
    """Open a session, list its tools, and confirm `required_tool` is offered."""
    async with session_factory() as session:
        listed = await session.list_tools()
        names = [t.name for t in getattr(listed, "tools", []) or []]
    if required_tool in names:
        return True, f"reachable and offers {required_tool} ({len(names)} tools)"
    return False, f"reachable but does not offer {required_tool}"


async def _guarded(coro, timeout_s: float, what: str) -> tuple[bool, str]:
    """Run a probe with a timeout; any failure becomes (False, detail) and never escapes."""
    try:
        return await asyncio.wait_for(coro, timeout_s)
    except asyncio.TimeoutError:
        return False, f"{what} did not answer within {timeout_s:g}s (TimeoutError)"
    except asyncio.CancelledError:
        raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:  # noqa: BLE001
        return False, _fail_detail(f"{what} failed", e)


def _exists_on_disk_or_path(cmd: str) -> bool:
    return os.path.isfile(cmd) or shutil.which(cmd) is not None


async def _check_git() -> tuple[bool, str]:
    path = shutil.which("git")
    if path:
        return True, f"git found at {path}"
    return False, "git is not on PATH"


async def _check_algernon(timeout_s: float) -> tuple[bool, str]:
    try:
        argv = _resolve_algernon()
    except Exception as e:  # noqa: BLE001
        return False, _fail_detail("could not resolve the Algernon command", e)
    if not argv or not _exists_on_disk_or_path(argv[0]):
        name = os.path.basename(argv[0]) if argv else "algernon"
        return False, f"Algernon executable not found ({name}); pip install algernon-mcp"
    ok, detail = await _guarded(_probe_session(algernon_session, "algernon_orchestrate"), timeout_s, "Algernon")
    return ok, detail if not ok else f"Algernon {detail}"


async def _check_local_chamber(timeout_s: float) -> tuple[bool, str]:
    try:
        argv = _resolve_humane()
    except Exception as e:  # noqa: BLE001
        return False, _fail_detail("could not resolve the local chamber command", e)
    if not argv:
        return False, "no local chamber: pip install arkhive-mcp or set SENTARION_HUMANE_CMD"
    ok, detail = await _guarded(_probe_session(humane_session, "govern"), timeout_s, "local chamber")
    return ok, detail if not ok else f"local chamber {detail}"


async def _check_arkhive_hosted(timeout_s: float) -> tuple[bool, str]:
    ok, detail = await _guarded(_probe_session(arkhive_session, "remember"), timeout_s, "hosted ArkHive")
    return ok, detail if not ok else f"hosted ArkHive {detail}"


async def _ollama_probe(base: str) -> tuple[bool, str]:
    up = bool(await asyncio.to_thread(_ollama_up, base))
    if up:
        return True, f"Ollama is answering at {base}"
    return False, f"Ollama is not answering at {base}"


async def _check_ollama(timeout_s: float) -> tuple[bool, str]:
    base = os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA
    return await _guarded(_ollama_probe(base), timeout_s, "Ollama probe")


async def _pypi_version(timeout_s: float) -> str | None:
    try:
        return await asyncio.wait_for(asyncio.to_thread(_fetch_pypi_version, timeout_s), timeout_s + 0.5)
    except asyncio.CancelledError:
        raise
    except BaseException:  # noqa: BLE001
        return None


def _fleet_provider(ollama_ok: bool) -> tuple[bool, str]:
    forced = (os.environ.get("SENTARION_FLEET_PROVIDER") or os.environ.get("ALGERNON_PROVIDER") or "").lower()
    anthropic, openai = _present("ANTHROPIC_API_KEY"), _present("OPENAI_API_KEY")
    if forced == "anthropic" and not anthropic:
        return False, "anthropic forced but ANTHROPIC_API_KEY is not set"
    if forced == "openai" and not openai:
        return False, "openai forced but OPENAI_API_KEY is not set"
    if forced in ("anthropic", "openai", "ollama"):
        return True, f"{forced} (forced by SENTARION_FLEET_PROVIDER or ALGERNON_PROVIDER)"
    if anthropic and openai:
        return True, "anthropic (ANTHROPIC_API_KEY and OPENAI_API_KEY are both set; set SENTARION_FLEET_PROVIDER to force one)"
    if anthropic:
        return True, "anthropic (ANTHROPIC_API_KEY is set)"
    if openai:
        return True, "openai (OPENAI_API_KEY is set)"
    if ollama_ok:
        return True, "ollama (no API key set and a local Ollama is answering)"
    return False, "none (no API key set and no local Ollama answering)"


def _api_key(ollama_ok: bool) -> tuple[bool, str]:
    if _present("ANTHROPIC_API_KEY"):
        return True, "ANTHROPIC_API_KEY is set"
    if _present("OPENAI_API_KEY"):
        return True, "OPENAI_API_KEY is set"
    if ollama_ok:
        return True, "no API key set, but Ollama is up so the fleet runs locally"
    return False, "neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set and Ollama is not running"


_FIXES = {
    "git": "install git and make sure it is on PATH",
    "algernon": "pip install algernon-mcp (or set SENTARION_ALGERNON_CMD to the algernon executable)",
    "local_chamber": "pip install arkhive-mcp (or set SENTARION_HUMANE_CMD and SENTARION_HUMANE_ARGS)",
    "arkhive_hosted": "check network access to the hosted ArkHive endpoint or set ARKHIVE_MCP_URL",
    "fleet_provider": "start Ollama or set ANTHROPIC_API_KEY (or OPENAI_API_KEY)",
    "ollama": "start Ollama (or set OLLAMA_BASE_URL) to run the fleet locally for free",
    "api_key": "start Ollama or set ANTHROPIC_API_KEY",
}


async def run_doctor(timeout_s: float = 3.0) -> dict:
    """Check every dependency and say exactly what to fix. Never raises; never prints secrets."""
    timeout_s = float(timeout_s) if timeout_s and timeout_s > 0 else 3.0

    git_r, algernon_r, chamber_r, arkhive_r, ollama_r, latest = await asyncio.gather(
        _guarded(_check_git(), timeout_s, "git check"),
        _guarded(_check_algernon(timeout_s), timeout_s * 2 + 1, "Algernon check"),
        _guarded(_check_local_chamber(timeout_s), timeout_s * 2 + 1, "local chamber check"),
        _guarded(_check_arkhive_hosted(timeout_s), timeout_s * 2 + 1, "hosted ArkHive check"),
        _guarded(_check_ollama(timeout_s), timeout_s * 2 + 1, "Ollama check"),
        _pypi_version(timeout_s),
    )
    ollama_ok = bool(ollama_r[0])
    checks = {
        "git": git_r,
        "algernon": algernon_r,
        "local_chamber": chamber_r,
        "arkhive_hosted": arkhive_r,
        "fleet_provider": _fleet_provider(ollama_ok),
        "ollama": ollama_r,
        "api_key": _api_key(ollama_ok),
    }
    checks = {k: {"ok": bool(v[0]), "detail": _scrub(str(v[1]))} for k, v in checks.items()}

    ready = (
        checks["git"]["ok"]
        and checks["algernon"]["ok"]
        and checks["local_chamber"]["ok"]
        and (checks["api_key"]["ok"] or checks["ollama"]["ok"])
    )
    next_steps = []
    for name, check in checks.items():
        if check["ok"]:
            continue
        if name == "fleet_provider" and " forced but " in check["detail"]:
            provider = check["detail"].split(" forced but ", 1)[0]
            var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
            next_steps.append(f"set {var} or choose a different fleet provider")
        else:
            next_steps.append(_scrub(_FIXES[name]))
    next_steps = list(dict.fromkeys(next_steps))

    upgrade = None
    if latest and str(latest) != __version__:
        upgrade = str(latest)

    return {
        "version": __version__,
        "upgrade_available": upgrade,
        "checks": checks,
        "ready": bool(ready),
        "next_steps": next_steps,
    }
