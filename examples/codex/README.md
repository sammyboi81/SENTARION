# Sentarion in the Codex CLI

## Register the server

Codex reads MCP servers from `~/.codex/config.toml`. Add this block (also in [config.toml.example](config.toml.example)):

```toml
[mcp_servers.sentarion]
command = "sentarion"
args = []
```

Codex launches `sentarion` over stdio and inherits your shell environment, so `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is picked up from there. With neither set and a local Ollama running, the fleet runs on Ollama; see [../ollama/](../ollama/).

## The six-prompt walk

Codex exposes the tools under the `sentarion` server name; name the tool you want:

1. `Call sentarion.sentarion_doctor and summarise the checks that are not ok, with their next_steps.`
2. `Call sentarion.sentarion_birth with name "Builder" and covenant ["never push to main", "never delete files outside the worktree"]. Use the returned soul_id as actor from now on.`
3. `Call sentarion.sentarion_quickstart with topic "use_a_worktree" and show me the arguments.`
4. `Call sentarion.govern with action "force-push to main" and flags ["irreversible"]. If the decision is block, stop and tell me why.`
5. `Call sentarion.orchestrate_and_record with goal "propose three small refactors for this repository", k=3 and the soul_id as actor. Report run.run_id, summary and memory.`
6. `Call sentarion.recall with limit 5 and the soul_id as actor. List the records newest first.`

The result shapes are the same as in [../claude_code/](../claude_code/): the server, not the client, decides them.
