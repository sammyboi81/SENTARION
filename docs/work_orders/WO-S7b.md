TASK: finish WO-S7. Defects 2 and 3 are done (do not touch them). Remaining, fix exactly:
1. sentarion_mcp/worktree.py: remove the trailing added blank line at EOF so `git diff sentarion_mcp/worktree.py` shows only the `stdin=subprocess.DEVNULL,` line.
4. sentarion_mcp/doctor.py fleet_provider check: when SENTARION_FLEET_PROVIDER or ALGERNON_PROVIDER forces anthropic/openai and the matching key var is absent, return ok=False, detail "<provider> forced but <VAR> is not set", and add a next_steps fix line.
5. sentarion_mcp/doctor.py: dedupe next_steps preserving order.
6. sentarion_mcp/doctor.py _scrub: only redact values with len >= 8 that do not match ^[A-Za-z]+$.
7. sentarion_mcp/quickstart.py: repo_path "." -> "<absolute path to your git repo>" and explain in `then` that the server resolves paths in its own working directory.
9. tests/test_birth_fallback.py (new): monkeypatch server.humane_session to raise HumaneNotConfigured; server.arkhive_session -> async context manager whose call_tool returns text "Error executing tool x" first, then '{"soul_id":"s1"}'; call asyncio.run(server.call_tool("sentarion_birth", {"name":"X","covenant":["a","b"]})); assert second call covenant == "a; b" and reply chain == "arkhive".
10. README.md: delete the "In detail:" paragraph under Free vs v2 (keep the table).
FILES ALLOWED: those named. FORBIDDEN: everything else. ACCEPTANCE: `python -m pytest -q` passes (28 expected). Do not commit. RETURN: per-defect confirmation + test counts.
