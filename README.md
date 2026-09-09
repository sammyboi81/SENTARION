# sentarion-mcp — Give your AI agents rules, memory, and receipts.

<!-- mcp-name: io.github.sammyboi81/sentarion -->

**Install:** `pip install sentarion-mcp` · **Command:** `sentarion` · Apache-2.0 · [Hosted endpoint](https://arkhive.dondatabrain.com/sentarion/mcp)

Sentarion is the open-source MCP control layer for governed multi-agent work. It governs, records, and coordinates agent work across Claude Code, Codex, Cursor, local models, and any MCP-compatible client.

It composes three open-source MCP servers into one governed substrate — it connects to them as an MCP client, it does not reimplement them:

- [Algernon](https://github.com/sammyboi81/algernon) — fan-out planning/dispatch to cheap parallel workers on **your** key (or a free local Ollama, auto-detected since 0.2.2)
- [ArkHive](https://github.com/sammyboi81/arkhive) — hosted, tamper-evident audit/memory chain
- a local covenant chamber (Humane Intelligence, or the bundled `arkhive-mcp` package when Humane is not installed)

## Install

```bash
pip install sentarion-mcp
```

Then, from any MCP client, run `sentarion_doctor`. It checks git, Algernon, the local chamber, hosted ArkHive, the fleet provider, Ollama and your API key, reports `ready: true` when a run will work, and lists one fix per missing piece. It never prints a secret.

## Quick start

**Claude Code** ([examples/claude_code/](examples/claude_code/))
```bash
claude mcp add sentarion -- sentarion
```
or in `.mcp.json`:
```json
{ "mcpServers": { "sentarion": { "command": "sentarion", "args": [] } } }
```

**Codex** ([examples/codex/](examples/codex/)) — in `~/.codex/config.toml`:
```toml
[mcp_servers.sentarion]
command = "sentarion"
args = []
```

**Cursor** ([examples/cursor/](examples/cursor/)) — in `.cursor/mcp.json`:
```json
{ "mcpServers": { "sentarion": { "command": "sentarion", "args": [] } } }
```

Provider keys come from your environment: set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`), or leave both out and the fleet runs on your local Ollama if one is running ([examples/ollama/](examples/ollama/)). Then say:
*"Use sentarion: run sentarion_doctor, birth yourself as Scout, then orchestrate_and_record a plan for X with k=3."*

## Tools
| tool | what it does |
|---|---|
| `sentarion_doctor(timeout_s)` | read-only health check of every dependency, with one plain fix per failing check; never prints secrets |
| `sentarion_quickstart(topic)` | canonical, runnable example calls for every capability |
| `sentarion_birth(name, covenant)` | earn a soul_id before acting (Law 5: born, not configured) |
| `remember / recall / verify` | dual-chain memory: local chamber + hosted ArkHive, merged newest-first, both provable |
| `govern(action, flags, rules)` | two-chamber, zero-LLM, **fail-closed** "may I?" gate |
| `orchestrate_and_record(goal, k)` | gate → Algernon plan+dispatch → auto-logged to both chains; returns a `run_id`, a tasks/succeeded/failed summary and the memory outcome per chain |
| `dispatch_with_dependencies(tasks_json)` | gate → waves by `depends_on`; dependents receive `{{id}}` results (data flow, new in 0.2.2) |
| `recall_and_replan(query, k)` | history-primed plan (plan only, no dispatch) |
| `cost_estimate(k, in_price, out_price)` | rough pre-dispatch cost |
| `worktree(action, repo_path, ...)` | governed git-worktree sandbox: create / list / remove |
| `sentarion_pro(topic, email)` | what the paid v2 upgrade adds to the capability you are using; with an email, requests a trial key |

## Governance — real, wired, fail-closed
Two governors, one decision rule: a rendered veto blocks; a chamber that fails to answer never manufactures a
veto; if no chamber renders a verdict, the action is blocked. Every tool that executes work or mutates state
(`orchestrate_and_record`, `dispatch_with_dependencies`, `worktree create/remove`) passes the gate first.

## Examples
- [examples/README.md](examples/README.md) — index
- [examples/claude_code/](examples/claude_code/) — register in Claude Code and walk six prompts
- [examples/codex/](examples/codex/) — the same from the Codex CLI
- [examples/cursor/](examples/cursor/) — register in Cursor
- [examples/ollama/](examples/ollama/) — run the fleet on a local Ollama for free
- [examples/multi_agent/](examples/multi_agent/) — `dispatch_example.py` (dependency waves with `{{id}}` data flow) and the [Claude-plans / Codex-builds loop](examples/multi_agent/claude_plans_codex_builds.md)
- [examples/worktree/](examples/worktree/) — `worktree_example.py` (create / list / remove through the server)

## Free vs v2
| free, Apache-2.0, forever | Sentarion v2 (paid) |
|---|---|
| local MCP server, standard MCP client compatibility | durable jobs and background execution |
| Algernon orchestration and dependency dispatch with `{{id}}` data flow | phase-gate workflow engine with role enforcement and structured task contracts |
| ArkHive integration and the local chamber; remember / recall / verify | signed run manifests and SHA-bound verification evidence |
| birth / identity; two-chamber fail-closed governance | inferred risk flags and a stored policy store |
| worktree create / list / remove | worktree diff / patch / commit, repository leases, repo truth snapshots |
| local Ollama fleet; rough cost estimates | budgets and hard ceilings, retries, cache, advanced cost ledger |
| single-user usage, basic audit events | adversarial code review, GitHub/CI workflow, team tenancy, hosted history, deployment gates |

## Join v2 early access
Trial key + pricing: **https://inboxaxe.com/mcp** — or, from any client that has Sentarion loaded, call `sentarion_pro(email="you@company.com")` and a 14-day v2 key is requested for that address. Nothing is sent unless you supply an email.

## Changelog

### 0.3.0
- **Server instructions.** The MCP `initialize` response now carries usage guidance (birth first, govern before acting, never invent results, `{{id}}` data flow, free vs paid).
- **`sentarion_doctor`.** Read-only health check of git, Algernon, the local chamber, hosted ArkHive, fleet provider, Ollama and API key, with one fix per failing check; never prints secrets.
- **`sentarion_quickstart`.** Six canonical, runnable example calls, one per capability.
- **Run summary.** `orchestrate_and_record` returns a `run` block with `run_id` and timing, a tasks/succeeded/failed `summary`, and a `memory` outcome per chain (`recorded`, `not_configured`, or `error: <type>`) instead of swallowing write failures.
- **Contextual `sentarion_pro`.** Optional `topic` (worktree, dispatch, govern, memory, review, jobs) returns what v2 adds to the capability you are using; the no-argument and email paths are unchanged.
- **`examples/`.** Claude Code, Codex, Cursor, Ollama, multi-agent dispatch and worktree examples, plus the Claude-plans / Codex-builds workflow.
- **Tests + CI.** `tests/` with pytest; a GitHub Actions job runs them on Python 3.10 and 3.12 and fails on version drift.
- **Birth fallback fix.** The ArkHive birth fallback no longer raises `NameError` (`tool_text` was not imported).
- **Version unification.** `pyproject.toml`, `sentarion_mcp.__version__` and `server.json` now agree; built wheels are no longer tracked.

### 0.2.2 — what changed (found by dogfooding)
- **Fleet config is explicit.** 0.2.1 passed the whole ambient environment to Algernon, so a stale
  `OPENAI_API_KEY` in your shell could silently override your Ollama setup (401). Now
  `SENTARION_FLEET_PROVIDER=anthropic|openai|ollama` wins, else a set key, else a local Ollama.
- **Local chamber always exists.** Without Humane installed, the bundled `arkhive-mcp` package is the local
  chamber (own chain at `~/.sentarion/local_chamber.db`). "humane_not_configured" is gone.
- **Dependencies carry data.** `{{t1}}` in a dependent prompt is replaced with task t1's result.
- **Hosted birth works** (the hosted 0.x server typed `covenant` as a string; we retry with one).
- `recall_and_replan` no longer sends an argument the hosted recall never accepted.
- Removed the unused `mcp-agent` dependency; added project URLs.

## Support this project
Sentarion, Algernon and ArkHive are free, open source, and built on our own hardware.
Donate: https://dondatabrain.com · Business suite: https://inboxaxe.com
