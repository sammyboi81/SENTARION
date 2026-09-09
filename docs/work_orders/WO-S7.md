TASK:
Rework after independent review of the week-1 branch: fix the ten defects below exactly; nothing else.

KNOWN FACTS:
- `python -m pytest -q` currently reports 27 passed. list_tools returns 13 tools.
- Line numbers refer to the current worktree files.

FILES ALLOWED:
- sentarion_mcp/worktree.py (defect 1 only)
- sentarion_mcp/server.py (defects 2, 3)
- sentarion_mcp/doctor.py (defects 4, 5, 6)
- sentarion_mcp/quickstart.py (defect 7)
- tests/test_birth_fallback.py (new, defect 9)
- README.md (defect 10)
- docs/BLOCKED.md may be left in place (defect 8 is accepted by the orchestrator; no change).

FILES FORBIDDEN: everything else.

DEFECTS (fix each precisely):
1. sentarion_mcp/worktree.py: remove the two blank lines added at end of file so the diff against base is only the `stdin=subprocess.DEVNULL` line.
2. sentarion_mcp/server.py ~511 and ~520 (orchestrate_and_record memory outcome) and the `remember` handler (~420/427): unwrap ExceptionGroup before naming the type: `while getattr(e, "exceptions", None): e = e.exceptions[0]` then use type(e).__name__. Put the unwrapping in one small helper `_exc_name(e) -> str` in server.py and use it in all four places.
3. sentarion_mcp/server.py ~592 (dispatch_with_dependencies): wrap `resolve_waves(tasks)` in `try/except ValueError as e: return _ok({"error": str(e), "dispatched": False})` so a cycle or unknown id is a clean refusal, not an MCP error. Also update examples/multi_agent/README.md is FORBIDDEN, so leave the doc; the code fix makes its sentence true.
4. sentarion_mcp/doctor.py ~167-168: when SENTARION_FLEET_PROVIDER or ALGERNON_PROVIDER forces anthropic/openai and the matching key env var is absent, the fleet_provider check returns ok=False with detail "<provider> forced but <VAR> is not set"; add the matching fix line to the next_steps mapping.
5. sentarion_mcp/doctor.py ~190-197: dedupe next_steps preserving order.
6. sentarion_mcp/doctor.py ~50 (_scrub): only redact values with length >= 8 that are not pure ASCII words (skip values matching ^[A-Za-z]+$).
7. sentarion_mcp/quickstart.py ~60: replace repo_path "." with "<absolute path to your git repo>" and say in `then` that the path must be absolute because the server resolves it in its own working directory. Keep the quickstart tests passing (the value is still a string; the schema test does not check path existence).
9. tests/test_birth_fallback.py: monkeypatch server.humane_session to raise HumaneNotConfigured and server.arkhive_session to an async context manager whose call_tool returns a result whose text is "Error executing tool ..." on the first call and '{"soul_id":"s1"}' on the second; call `asyncio.run(server.call_tool("sentarion_birth", {"name":"X","covenant":["a","b"]}))`, assert the second call was made with covenant "a; b" and the JSON reply has chain "arkhive".
10. README.md ~89: delete the "In detail:" paragraph under Free vs v2 (keep the table).

ACCEPTANCE CRITERIA: `python -m pytest -q` passes (28 expected); `git diff --stat` shows only FILES ALLOWED.

DO NOT: touch any other function; commit.

RETURN: per-defect one-line confirmation, test command + counts.
