# sentarion-mcp (v0.1.0)

<!-- mcp-name: io.github.sammyboi81/sentarion -->

Composite MCP server wrapping [Algernon](https://pypi.org/project/algernon-mcp/)
(fan-out orchestration) and [ArkHive](https://github.com/sammyboi81/arkhive)
(governed audit/memory). Connects to both as an MCP client — does not
reimplement either.

## What's real right now
- `cost_estimate` — pre-dispatch cost prediction, grounded in Algernon's own published benchmark numbers.
- `dispatch_with_dependencies` — fan-out/fan-in wave ordering on top of Algernon's independent-task `algernon_dispatch`.
- `orchestrate_and_record` — plan+dispatch, auto-logged to ArkHive's `remember`.
- `recall_and_replan` — pulls ArkHive `recall` history into a new Algernon plan.

## Governance — real, wired, fail-closed
`govern_stub.py` now carries the REAL ArkHive `govern` client (verified against
the live GovernanceBlock engine, 2026-08-18):

- wire in: `{action, flags: [...], rules: [{trigger, action}]}`
- wire out: `{vetoed: bool, reason, engine: "zero-LLM rule gate", auditable: true}`
- verdicts are **binary** (no "pending" state exists in the engine)
- **fail-closed**: if ArkHive is unreachable, dispatch is blocked — an absent
  governor never silently approves
- a blocked `orchestrate_and_record` returns the decision and skips dispatch

## Not yet built (deferred, per the earlier feature list)
- Durable/crash-resistant execution via `mcp-agent` (Temporal-backed) — listed as a dependency in pyproject.toml but not yet wired into server.py.
- Phase-gate state machine (queue→work→review→terminal) inside ArkHive's `govern` — depends on #1 above.

## Install (once ready)
```
pip install -e .
```

## Run
```
sentarion
```
