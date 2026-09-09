# Claude plans, a Codex-style worker builds, governance runs, the result is recorded

This is the loop we use on our own repositories with only the free tools. One agent (Claude Code here) owns the plan and the review; a second agent or fleet worker (Codex, or any Algernon worker) does the implementation; Sentarion sits between them so nothing executes ungoverned and nothing finishes unrecorded.

## Roles

- **Planner (Claude Code)**: reads the repository, writes a work order per task (files allowed, files forbidden, required behavior, tests, acceptance criteria), and reviews what comes back.
- **Implementer (Codex CLI, or Algernon workers via `dispatch_with_dependencies`)**: implements exactly one work order inside a git worktree and returns a report.
- **Sentarion**: births both agents, gates every mutating step through `govern`, runs the fleet, and writes each outcome to both memory chains.

## The loop

1. **Health**: the planner runs `sentarion_doctor`; if `ready` is false it stops and reports `next_steps`.
2. **Identity**: each agent calls `sentarion_birth` once with its covenant (for an implementer: never push to main, never edit outside the worktree, never delete without a work order). The returned `soul_id` is its `actor` from then on.
3. **Sandbox**: the planner calls `worktree` with `action: create` and a branch name. Governance approves or blocks it. The implementer only ever works in `worktree_path`.
4. **Plan**: the planner writes the work orders as files in the worktree, or as the `prompt` of tasks in a `tasks_json` array with `depends_on` so an integration task runs after its parts and receives them through `{{id}}`.
5. **Gate**: before any step that edits, deletes, spends or deploys, the acting agent calls `govern` with honest flags (`may_edit_files`, `deletes_files`, `outbound`, `spends`). A `block` verdict ends that step; it is not retried under another name.
6. **Build**: the implementer runs the work order (in Codex: the prompt sequence in [../codex/](../codex/); in a fleet: `dispatch_with_dependencies`). Tests are written and run inside the worktree.
7. **Review**: the planner reads the diff and the implementer's report against the acceptance criteria. Unmet criteria go back as a new, smaller work order.
8. **Record**: the planner calls `remember` with `actor`, `action: "work_order_done"` and `data` containing the work-order id, the worktree branch, the commit SHA if any, and the test counts. `orchestrate_and_record` does this automatically for fleet runs and returns `run.run_id` plus a `memory` block that says whether each chain actually recorded it.
9. **Verify**: `verify` confirms both chains are intact before anything merges.
10. **Clean up**: `worktree` with `action: remove` (governed) once the branch is merged or abandoned.

## What you get from the free tools

- a soul_id per agent, so every record names who acted
- a fail-closed gate before each mutating step
- a worktree so the live checkout is never touched by a worker
- wave-ordered dispatch with real data flow between tasks
- a run_id and a tasks/succeeded/failed summary per fleet run
- a tamper-evident record on both chains, with `verify` to prove it

## What is on you in the free tier

- writing the work orders and keeping them small
- reading the diff yourself
- deciding when a run may retry
- keeping the loop going across sessions

Sentarion v2 turns this pattern into an enforced durable workflow.
