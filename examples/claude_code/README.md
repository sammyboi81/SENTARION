# Sentarion in Claude Code

## Register the server

One command, stdio transport:

```bash
claude mcp add sentarion -- sentarion
```

Or add it to the project's `.mcp.json` so every teammate gets it:

```json
{ "mcpServers": { "sentarion": { "command": "sentarion", "args": [] } } }
```

Provider keys are read from your shell environment (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`). Leave both unset and run a local Ollama to use the fleet for free; see [../ollama/](../ollama/).

## The six-prompt walk

Say these to Claude Code in order (also in [prompts.md](prompts.md)):

1. `Use sentarion: run sentarion_doctor and tell me what, if anything, I need to fix.`
2. `Use sentarion: birth yourself as Scout with the covenant ["never send", "never delete", "ask before spending"] and keep the soul_id as your actor.`
3. `Use sentarion: show me the quickstart for dispatch_dependencies.`
4. `Use sentarion: ask govern whether you may "delete the build directory" with flags ["deletes_files"].`
5. `Use sentarion: orchestrate_and_record the goal "outline a README for this repo in three sections" with k=3 and your soul_id as actor, then tell me the run_id, the summary, and whether both chains recorded it.`
6. `Use sentarion: recall the last 5 records for your actor and list them newest first.`

What each one returns:

- `sentarion_doctor`: a `ready` flag, one check per dependency, and `next_steps`.
- `sentarion_birth`: a `soul_id`; Claude passes it as `actor` from then on.
- `sentarion_quickstart`: a valid, runnable call for that capability.
- `govern`: `approve` or `block`; a block is final and the server instructions tell Claude not to work around it.
- `orchestrate_and_record`: a `run` block with `run_id`, the governance verdict, Algernon's results, a `summary` (tasks, succeeded, failed) and a `memory` block that says `recorded`, `not_configured` or `error: <type>` per chain.
- `recall`: records from both chains merged newest first.

In Sentarion v2 the same run also produces a signed manifest and SHA-bound verification evidence; nothing above changes.
