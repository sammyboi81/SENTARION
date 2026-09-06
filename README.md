# sentarion-mcp (v0.2.2) — governed multi-agent orchestration for AI

<!-- mcp-name: io.github.sammyboi81/sentarion -->

**Install:** `pip install sentarion-mcp` · **Command:** `sentarion` · Apache-2.0 · [Hosted endpoint](https://arkhive.dondatabrain.com/sentarion/mcp)

Sentarion composes three open-source MCP servers into one governed substrate — it connects to them as an
MCP client, it does not reimplement them:

- [Algernon](https://github.com/sammyboi81/algernon) — fan-out planning/dispatch to cheap parallel workers on **your** key (or a free local Ollama, auto-detected since 0.2.2)
- [ArkHive](https://github.com/sammyboi81/arkhive) — hosted, tamper-evident audit/memory chain
- a local covenant chamber (Humane Intelligence, or the bundled `arkhive-mcp` package when Humane is not installed)

## Quick start (Claude Desktop / Claude Code / Cursor)
```json
{ "mcpServers": { "sentarion": { "command": "sentarion", "args": [],
  "env": { "ANTHROPIC_API_KEY": "sk-ant-..." } } } }
```
Leave the key out and the fleet runs on your local Ollama if one is running. Then say:
*"Use sentarion: birth yourself as Scout, then orchestrate_and_record a plan for X with k=3."*

## Tools
| tool | what it does |
|---|---|
| `sentarion_birth(name, covenant)` | earn a soul_id before acting (Law 5: born, not configured) |
| `remember / recall / verify` | dual-chain memory: local chamber + hosted ArkHive, merged newest-first, both provable |
| `govern(action, flags, rules)` | two-chamber, zero-LLM, **fail-closed** "may I?" gate |
| `orchestrate_and_record(goal, k)` | gate → Algernon plan+dispatch → auto-logged to both chains |
| `dispatch_with_dependencies(tasks_json)` | gate → waves by `depends_on`; dependents receive `{{id}}` results (data flow, new in 0.2.2) |
| `recall_and_replan(query, k)` | history-primed plan (plan only, no dispatch) |
| `cost_estimate(k, in_price, out_price)` | rough pre-dispatch cost |
| `worktree(action, repo_path, ...)` | governed git-worktree sandbox: create / list / remove |
| `sentarion_pro()` | what the paid v2 upgrade adds |

## Governance — real, wired, fail-closed
Two governors, one decision rule: a rendered veto blocks; a chamber that fails to answer never manufactures a
veto; if no chamber renders a verdict, the action is blocked. Every tool that executes work or mutates state
(`orchestrate_and_record`, `dispatch_with_dependencies`, `worktree create/remove`) passes the gate first.

## 0.2.2 — what changed (found by dogfooding)
- **Fleet config is explicit.** 0.2.1 passed the whole ambient environment to Algernon, so a stale
  `OPENAI_API_KEY` in your shell could silently override your Ollama setup (401). Now
  `SENTARION_FLEET_PROVIDER=anthropic|openai|ollama` wins, else a set key, else a local Ollama.
- **Local chamber always exists.** Without Humane installed, the bundled `arkhive-mcp` package is the local
  chamber (own chain at `~/.sentarion/local_chamber.db`). "humane_not_configured" is gone.
- **Dependencies carry data.** `{{t1}}` in a dependent prompt is replaced with task t1's result.
- **Hosted birth works** (the hosted 0.x server typed `covenant` as a string; we retry with one).
- `recall_and_replan` no longer sends an argument the hosted recall never accepted.
- Removed the unused `mcp-agent` dependency; added project URLs.

## Upgrade: Sentarion v2 (paid)
Everything above stays free forever. v2 is the in-house upgrade for teams who run this daily:
in-process composition (no subprocess per call), concurrent gate with **inferred risk flags** and stored
policies, `{{id}}` data flow with budgets + cache + retries, **signed audit manifests** for every run,
**adversarial multi-agent code review**, worktree sandbox with diff/patch/commit, real cost estimates,
MCP progress + background jobs, hosted per-key tenants. **Trial key + pricing: https://inboxaxe.com/mcp**

## Support this project
Sentarion, Algernon and ArkHive are free, open source, and built on our own hardware.
Donate: https://dondatabrain.com · Business suite: https://inboxaxe.com
