TASK:
Add a `sentarion_quickstart` tool, give `orchestrate_and_record` an honest run summary, and make `sentarion_pro` contextual.

WHY:
GTM plan Patch C (quickstart: do not hide features behind documentation), Patch E (run summary that shows what v2 would add, naturally), Patch D (contextual upgrade discovery, no dark patterns). Today orchestrate_and_record returns two fields and swallows memory-write failures with bare `except: pass`, so a user cannot tell whether the run was recorded.

KNOWN FACTS:
- Tools are declared in `list_tools()` and dispatched in `call_tool()` in sentarion_mcp/server.py; results via `_ok(dict)`.
- orchestrate_and_record handler: gate via govern_stub, then `algernon_session()` + `algernon_orchestrate`, then two `remember` writes each wrapped in try/except that discards the error, then returns `{"governance": decision, "results": plan_and_results}`. On block it returns the decision alone (no `dispatched` key), unlike dispatch_with_dependencies which returns `{"governance": decision, "dispatched": False}`.
- Algernon's orchestrate result shape is not guaranteed; treat `plan_and_results` as opaque. If it is a dict with a `results` list, each item may have `id`, `result`, `error`.
- sentarion_pro handler returns a fixed dict (server.py) with `free_tier`, `v2_paid_upgrade.what` (8 strings), `get_a_trial_key`, `business_suite`, `donate`; with `email` it calls `_register_for_v2`.
- tests/ exists (from WO-S1 and WO-S2). pytest 9, no pytest-asyncio; use asyncio.run in sync tests.

UNKNOWNS:
- none that block implementation.

FILES ALLOWED:
- sentarion_mcp/quickstart.py (new)
- sentarion_mcp/server.py
- tests/test_quickstart.py (new)
- tests/test_run_summary.py (new)

FILES FORBIDDEN:
- clients.py, govern_stub.py, dependency_graph.py, cost_estimate.py, worktree.py, doctor.py, README.md, pyproject.toml, server.json, .github/**, examples/**, docs/**

CURRENT BEHAVIOR:
- No quickstart. Run result has no run id, timing, counts, or memory outcome. sentarion_pro is generic.

REQUIRED BEHAVIOR:
1. `sentarion_mcp/quickstart.py` exposes `EXAMPLES: dict[str, dict]` keyed by exactly: "plan_a_feature", "fan_out_research", "dispatch_dependencies", "use_a_worktree", "remember_result", "replan_from_memory". Each value has keys `goal` (one sentence), `tool` (tool name), `arguments` (a JSON-serializable dict that is a valid call for that tool per its inputSchema), `expect` (one sentence describing the result shape), `then` (one sentence on what to do next). Also `def quickstart(topic: str | None = None) -> dict`: with no topic returns `{"start_here": ["sentarion_doctor", "sentarion_birth"], "examples": EXAMPLES}`; with a topic returns `{"example": EXAMPLES[topic]}` or `{"error": "unknown topic", "topics": [...]}`.
2. Register tool "sentarion_quickstart" with description "Canonical, runnable examples for every Sentarion capability: plan a feature, fan out research, dispatch with dependencies, use a worktree, remember a result, replan from memory." and inputSchema {"type":"object","properties":{"topic":{"type":"string","enum":[the six keys]}},"required":[]}.
3. orchestrate_and_record returns:
   {
     "run": {"run_id": "<uuid4 hex>", "goal": goal, "k": k, "actor": actor, "started_at": "<ISO8601 UTC>", "finished_at": "<ISO8601 UTC>"},
     "governance": decision,
     "results": plan_and_results,
     "summary": {"tasks": int, "succeeded": int, "failed": int},   # derived from plan_and_results["results"] when it is a list of dicts: failed = items with a truthy "error" or result None; else tasks=0
     "memory": {"arkhive": "recorded" | "error: <ExceptionType>", "humane": "recorded" | "not_configured" | "error: <ExceptionType>"},
     "v2_would_add": ["signed run manifest", "typed retries", "SHA-bound verification evidence", "adversarial review gate"]
   }
   The `remember` record data must include `run_id`. On a block verdict return `{"run": {...same keys, finished_at set...}, "governance": decision, "dispatched": False}`. Never swallow an exception silently: the memory outcome must be reported.
4. sentarion_pro accepts optional `topic` (enum: "worktree", "dispatch", "govern", "memory", "review", "jobs"). With a topic, return `{"you_are_using": <one sentence about the free capability>, "v2_adds": [3-5 concrete strings for that topic], "run": "sentarion_pro(email=...) for a trial key", "free_stays_free": true}`. Without a topic keep the current return exactly. Keep the email path exactly as is. No urgency language, no countdowns, no repeated nagging text.
5. Update the sentarion_pro Tool inputSchema to add `topic` (optional). Do not change other tool schemas.

DATA CONTRACT:
- As above. `run.run_id` is the join key for future manifests.

UX REQUIREMENTS:
- Every string is plain language. No exclamation marks.

ERROR STATES:
- Unknown quickstart topic returns the error dict, never raises.

SECURITY / PERMISSIONS:
- No new network calls except the existing email trial path. Governance gate unchanged.

TESTS REQUIRED:
- tests/test_quickstart.py: every EXAMPLES entry has the five keys; each `tool` names a tool present in `asyncio.run(server.list_tools())`; each `arguments` dict includes every `required` property of that tool's inputSchema; quickstart(None) and quickstart("bogus") shapes.
- tests/test_run_summary.py: monkeypatch `server.govern_stub` to return {"decision":"approve","reason":"test","chambers":{}}, `server.algernon_session` to an async context manager yielding an object whose `call_tool` returns an object with `.content=[TextContent(type="text", text=json.dumps({"results":[{"id":"a","result":"ok"},{"id":"b","error":"boom"}]}))]`, and `server.arkhive_session`/`server.humane_session` to raise ConnectionError / HumaneNotConfigured. Call `asyncio.run(server.call_tool("orchestrate_and_record", {"goal":"g","k":2}))`, parse the JSON text, assert run.run_id is 32 hex chars, summary == {"tasks":2,"succeeded":1,"failed":1}, memory.arkhive startswith "error:", memory.humane == "not_configured". Second test: govern returns block, assert dispatched is False and run present.

ACCEPTANCE CRITERIA:
1. `python -m pytest -q` passes (all tests).
2. Changed and new files are a subset of FILES ALLOWED.
3. `asyncio.run(server.call_tool("sentarion_quickstart", {}))` returns JSON with six examples.

DO NOT:
- infer missing APIs
- add placeholder production data
- change govern_stub or any gate
- change schema outside task
- remove existing behavior without reporting it
- commit

RETURN:
- concise implementation summary
- files changed
- tests run (command + counts)
- failures / blockers
- exact assumptions remaining
