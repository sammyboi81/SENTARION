# Sentarion examples

Copy-paste examples for every way people use Sentarion. Each directory has its own README; runnable files are listed next to it.

Before any of them: `pip install sentarion-mcp`, then ask your client to run `sentarion_doctor`. It reports `ready: true` when git, Algernon, the local chamber and a model provider (an API key or a local Ollama) are all in place, and lists one fix per missing piece.

| directory | what it shows | runnable file |
|---|---|---|
| [claude_code/](claude_code/) | register Sentarion in Claude Code and walk the six-prompt sequence | `prompts.md` (prompts, not a script) |
| [codex/](codex/) | the same sequence from the Codex CLI | `config.toml.example` |
| [cursor/](cursor/) | register Sentarion in Cursor | `mcp.json.example` |
| [ollama/](ollama/) | run the worker fleet on a local Ollama for free | none |
| [multi_agent/](multi_agent/) | dependency-ordered dispatch with `{{id}}` data flow, plus the Claude-plans / Codex-builds loop | `dispatch_example.py`, `claude_plans_codex_builds.md` |
| [worktree/](worktree/) | isolate dispatched work in a git worktree | `worktree_example.py` |

The two Python scripts talk to the server over stdio with the official `mcp` client: `pip install mcp` if your environment does not already have it. They read provider keys from your environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) or fall back to a local Ollama; nothing is embedded in the files.

Every example is free and Apache-2.0. Where a step would be different in Sentarion v2 (the paid control plane), the README says so in one line and nothing more.
