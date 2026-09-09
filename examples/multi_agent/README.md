# Multi-agent dispatch with dependencies

`dispatch_with_dependencies` takes `tasks_json`, a JSON array of `{id, prompt, depends_on}`. Sentarion sorts the tasks into waves, runs each wave through Algernon's fan-out, and substitutes finished results into later prompts.

## Wave order

Given

```json
[
  {"id": "t1", "prompt": "...", "depends_on": []},
  {"id": "t2", "prompt": "...", "depends_on": []},
  {"id": "t3", "prompt": "... {{t1}} ... {{t2}} ...", "depends_on": ["t1", "t2"]}
]
```

the server runs:

- wave 1: `t1` and `t2` in parallel (nothing depends on them yet)
- wave 2: `t3`, only after both finished

A task never starts before every id in its `depends_on` has a result. Cycles and unknown ids are rejected before anything runs.

## `{{id}}` data flow

Before a wave is dispatched, every `{{id}}` in a prompt is replaced with the result text of that task from an earlier wave. `t3` above therefore sees the actual answers of `t1` and `t2`, not their ids. The result includes `"data_flow": "dependents received {{id}} substitutions from completed tasks"` to confirm this happened.

## Governance first

Dispatch can run workers that edit files, so it passes the two-chamber gate with flags `executes_tasks` and `may_edit_files` before wave 1. If the verdict is `block` the result is `{"governance": ..., "dispatched": false}` and nothing ran.

## Run it

```bash
pip install sentarion-mcp mcp
python examples/multi_agent/dispatch_example.py
```

The script:

1. starts `sentarion` over stdio (falls back to `python -m sentarion_mcp.server` when the console script is not on PATH),
2. calls `sentarion_doctor` and exits 1 with the failing checks and `next_steps` if `ready` is false,
3. dispatches the three tasks above,
4. prints the governance verdict, the number of waves, and each task's result or error.

Provider keys come from your environment; with none set and Ollama running the workers run locally (see [../ollama/](../ollama/)).

Sentarion v2 adds budgets, a result cache and typed retries to this same call; the free tool does not change. The related Claude-plans / Codex-builds loop is described in [claude_plans_codex_builds.md](claude_plans_codex_builds.md).
