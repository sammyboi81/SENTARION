# Sentarion in Cursor

Cursor reads MCP servers from `.cursor/mcp.json` in the project (or `~/.cursor/mcp.json` globally). The shape is the same as Claude's `.mcp.json` (also in [mcp.json.example](mcp.json.example)):

```json
{ "mcpServers": { "sentarion": { "command": "sentarion", "args": [] } } }
```

Cursor starts `sentarion` over stdio with your environment, so `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is read from there. If Cursor does not inherit your shell environment on your platform, add an `env` object next to `args` with the variable name only where you keep the value, never in a committed file.

Then, in Cursor's agent chat:

1. `Run sentarion_doctor and tell me what to fix.`
2. `Birth yourself with sentarion_birth as Pilot and keep the soul_id as actor.`
3. `Show the sentarion_quickstart for plan_a_feature.`
4. `Use govern before you edit anything: action "edit src/", flags ["may_edit_files"].`
5. `orchestrate_and_record the goal "list the three riskiest files in this repo and why" with k=3.`
6. `recall the last 5 records for your actor.`

The tool results are identical across Claude Code, Codex and Cursor; see [../claude_code/](../claude_code/) for what each returns.
