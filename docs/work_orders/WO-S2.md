TASK:
Add a `sentarion_doctor` MCP tool that reports the health of every dependency Sentarion relies on, without ever raising or printing secrets.

WHY:
Patch B of the GTM plan: onboarding fails silently today (wrong Algernon path, no Ollama, no key, hosted ArkHive unreachable). A doctor makes the first run succeed.

KNOWN FACTS:
- Raw MCP SDK `Server` with a hand-written Tool list in `list_tools()` (server.py) and an if/elif dispatcher in `call_tool()`. Results are returned via `_ok(payload)` which JSON-encodes a dict.
- Dependency resolution lives in clients.py: `_resolve_algernon()` returns an argv list (lines 44-82); `_resolve_humane()` returns an argv list or None (lines 85-104); `_ollama_up(base) -> bool` (lines 107-112); `fleet_env()` (lines 115-135); `ARKHIVE_URL` constant (line 39, env ARKHIVE_MCP_URL). Sessions `algernon_session()`, `arkhive_session()`, `humane_session()` are async context managers yielding an initialized `ClientSession` with `.list_tools()`.
- Env names that matter (names only, never print values): ANTHROPIC_API_KEY, OPENAI_API_KEY, SENTARION_FLEET_PROVIDER, ALGERNON_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL, ARKHIVE_MCP_URL, SENTARION_ALGERNON_CMD, SENTARION_HUMANE_CMD, SENTARION_HUMANE_ARGS, ARKHIVE_DB.
- Package version is `sentarion_mcp.__version__` (set by WO-S1). PyPI JSON endpoint for the upgrade check: https://pypi.org/pypi/sentarion-mcp/json, field `info.version`.
- `shutil.which("git")` detects git.
- httpx is a declared dependency. pytest 9 is available; pytest-asyncio is NOT assumed (use asyncio.run inside sync tests).

UNKNOWNS:
- Whether the hosted ArkHive endpoint is reachable from the test machine at test time. Tests must monkeypatch and never hit the network.

FILES ALLOWED:
- sentarion_mcp/doctor.py (new)
- sentarion_mcp/server.py (ONLY: import doctor, add one Tool entry to list_tools, add one `if name == "sentarion_doctor":` branch to call_tool)
- tests/test_doctor.py (new)

FILES FORBIDDEN:
- clients.py, govern_stub.py, dependency_graph.py, cost_estimate.py, worktree.py, README.md, pyproject.toml, server.json, .github/**, examples/**, docs/**

CURRENT BEHAVIOR:
- No health/self-check exists.

REQUIRED BEHAVIOR:
1. `sentarion_mcp/doctor.py` exposes `async def run_doctor(timeout_s: float = 3.0) -> dict` returning exactly this shape (keys always present):
   {
     "version": "<sentarion_mcp.__version__>",
     "upgrade_available": <str version or null>,
     "checks": {
       "git":            {"ok": bool, "detail": str},
       "algernon":       {"ok": bool, "detail": str},   # resolved argv[0] exists on disk or on PATH, AND session initializes, AND list_tools contains algernon_orchestrate
       "local_chamber":  {"ok": bool, "detail": str},   # _resolve_humane() not None, AND session initializes, AND list_tools contains govern
       "arkhive_hosted": {"ok": bool, "detail": str},   # arkhive_session initializes within timeout AND list_tools contains remember
       "fleet_provider": {"ok": bool, "detail": str},   # which provider fleet_env() would select: anthropic|openai|ollama|none, with reason; ok=false only for none
       "ollama":         {"ok": bool, "detail": str},   # _ollama_up(OLLAMA_BASE_URL or default)
       "api_key":        {"ok": bool, "detail": str}    # whether ANTHROPIC_API_KEY or OPENAI_API_KEY is SET (never the value); ok=true also when ollama is up
     },
     "ready": bool,        # true iff git, algernon, local_chamber and (api_key or ollama) are ok
     "next_steps": [str]   # one plain-language fix per failing check, e.g. "pip install algernon-mcp" or "start Ollama or set ANTHROPIC_API_KEY"
   }
   Every check is wrapped so that no exception escapes; a failure becomes ok=false with the exception type in detail. Network/subprocess checks use asyncio.wait_for with timeout_s. Import the helpers from `.clients` at module level as names on the doctor module so tests can monkeypatch `doctor._resolve_algernon`, `doctor._resolve_humane`, `doctor._ollama_up`, `doctor.arkhive_session`, `doctor.algernon_session`, `doctor.humane_session`, and `doctor._fetch_pypi_version`.
2. `_fetch_pypi_version(timeout_s) -> str | None` GETs https://pypi.org/pypi/sentarion-mcp/json with httpx; `upgrade_available` is that version when it differs from `__version__`, else null; on any error null.
3. Register the tool in server.py: name "sentarion_doctor", description "Check that everything Sentarion needs is present and reachable (git, Algernon, local chamber, hosted ArkHive, fleet provider, Ollama, API key) and say exactly what to fix. Read-only; never prints secrets.", inputSchema {"type":"object","properties":{"timeout_s":{"type":"number","default":3}},"required":[]}. Handler: `return _ok(await run_doctor(float(arguments.get("timeout_s", 3.0))))`.
4. Secret hygiene: never include the value of any env var whose name contains KEY, TOKEN, SECRET or PASSWORD in any returned string. Add a helper `_present(name) -> bool` and use it.

DATA CONTRACT:
- As in REQUIRED BEHAVIOR 1. Keys stable; consumers may rely on `ready` and `next_steps`.

UX REQUIREMENTS:
- `detail` strings are one short sentence, actionable.

ERROR STATES:
- Every dependency missing: ready=false, all checks present, next_steps populated, no exception.

SECURITY / PERMISSIONS:
- Read-only. No governance gate needed. Only launch the Algernon and local-chamber MCP processes that clients.py already launches, and only for initialize + list_tools.

TESTS REQUIRED (tests/test_doctor.py):
- test_shape_all_failing: monkeypatch `doctor._resolve_algernon` to return ["/nonexistent/algernon"], `doctor._resolve_humane` to return None, `doctor.arkhive_session` to an async context manager that raises ConnectionError, `doctor._ollama_up` to return False, `doctor._fetch_pypi_version` to return None, and delenv the key vars (raising=False). Assert every key above exists, ready is False, next_steps is a non-empty list.
- test_secret_never_leaks: same monkeypatches plus monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-TESTSECRET123"); assert "TESTSECRET123" not in json.dumps(asyncio.run(run_doctor(0.5))).
- test_tool_registered: import sentarion_mcp.server, run `asyncio.run(server.list_tools())`, assert a tool named "sentarion_doctor" exists.

ACCEPTANCE CRITERIA:
1. `python -m pytest -q` passes (all tests, including those from WO-S1).
2. Changed and new files are a subset of FILES ALLOWED.
3. Running `python -c "import asyncio, json; from sentarion_mcp.doctor import run_doctor; print(json.dumps(asyncio.run(run_doctor(3.0)), indent=1))"` on this machine prints the full shape without a traceback (report `ready` and which checks failed; do not fix the environment).

DO NOT:
- infer missing APIs
- add placeholder production data
- redesign unrelated screens
- change schema outside task
- remove existing behavior without reporting it
- commit

RETURN:
- concise implementation summary
- files changed
- tests run (command + counts)
- the real doctor output on this machine
- failures / blockers
- exact assumptions remaining
