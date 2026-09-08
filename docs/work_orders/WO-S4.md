TASK:
Add a runnable examples/ directory, reposition the README, and put the v2 early-access CTA in place.

WHY:
GTM plan Patch F (tested examples), Patch G (public dogfood workflow), §26 positioning ("Give your AI agents rules, memory, and receipts."), §44 week 1 (Claude Code example, Codex example, README positioning, V2 waitlist CTA).

KNOWN FACTS:
- Package installs the console script `sentarion` (pyproject [project.scripts]). Tools after WO-S1..S3: sentarion_doctor, sentarion_quickstart, sentarion_pro(topic|email), cost_estimate, sentarion_birth, remember, recall, verify, govern, orchestrate_and_record, dispatch_with_dependencies, recall_and_replan, worktree.
- Claude Code registers an MCP server with: `claude mcp add sentarion -- sentarion` (stdio) or via .mcp.json {"mcpServers":{"sentarion":{"command":"sentarion","args":[]}}}.
- Codex CLI reads MCP servers from ~/.codex/config.toml as `[mcp_servers.sentarion]\ncommand = "sentarion"\nargs = []`.
- Cursor reads .cursor/mcp.json with the same mcpServers shape as Claude.
- Ollama fleet: leave ANTHROPIC_API_KEY and OPENAI_API_KEY unset and run Ollama on 127.0.0.1:11434; set OLLAMA_MODEL to choose the model (clients.py fleet_env).
- server.json description has a 100-character cap (commit 9cc0a7d).
- The trial-key endpoint is POST https://inboxaxe.com/api/v2/mcp/trial and the in-product path is `sentarion_pro(email=...)`. There is no separate waitlist page; the CTA text is "Join v2 early access" and it points to https://inboxaxe.com/mcp and to `sentarion_pro(email=...)`.
- README today: title "sentarion-mcp (v0.2.2) — governed multi-agent orchestration for AI"; sections Quick start, Tools, Governance, 0.2.2 changes, Upgrade, Support.

UNKNOWNS:
- Whether a Python MCP client is available in every user environment; examples that need it must say `pip install mcp`.

FILES ALLOWED:
- examples/** (new)
- README.md
- server.json (ONLY the "description" string)

FILES FORBIDDEN:
- sentarion_mcp/**, tests/**, pyproject.toml, smithery.yaml, glama.json, .github/**, docs/**

CURRENT BEHAVIOR:
- No examples. README leads with jargon. CTA is a trial-key link only.

REQUIRED BEHAVIOR:
1. Create examples/README.md (index) and six subdirectories, each with a README.md and, where marked, a runnable file:
   - examples/claude_code/: README with the exact `claude mcp add` command, the .mcp.json snippet, and a 6-line transcript of prompts: doctor, birth, quickstart, govern, orchestrate_and_record k=3, recall. File `prompts.md` with those prompts verbatim.
   - examples/codex/: README with the config.toml snippet and the same prompt sequence adapted to Codex. File `config.toml.example`.
   - examples/cursor/: README with .cursor/mcp.json snippet. File `mcp.json.example`.
   - examples/ollama/: README on running the fleet on a local Ollama for free (env vars, model choice, sentarion_doctor to confirm). No runnable file.
   - examples/multi_agent/: runnable `dispatch_example.py` that uses the `mcp` Python client over stdio to start `sentarion`, call sentarion_doctor, then dispatch_with_dependencies with three tasks where t3 depends on t1 and t2 and its prompt contains `{{t1}}` and `{{t2}}`, and prints the returned summary. Must exit non-zero with a clear message if the doctor reports ready=false. README explains the wave order and the `{{id}}` data flow.
   - examples/worktree/: runnable `worktree_example.py` that creates a temporary git repo in a temp dir, calls worktree create/list/remove through the server, and prints the results. README explains why dispatched work runs in a worktree.
   - Dogfood workflow (Patch G): examples/multi_agent/claude_plans_codex_builds.md describing the Claude-plans, Codex-style-worker-implements, governance-runs, result-recorded loop using only free tools, ending with the sentence "Sentarion v2 turns this pattern into an enforced durable workflow."
2. README.md rewrite, keeping every factual claim already present and all links:
   - Line 1: `# sentarion-mcp — Give your AI agents rules, memory, and receipts.`
   - Line 3: keep the `<!-- mcp-name: io.github.sammyboi81/sentarion -->` marker.
   - One-paragraph description: "Sentarion is the open-source MCP control layer for governed multi-agent work. It governs, records, and coordinates agent work across Claude Code, Codex, Cursor, local models, and any MCP-compatible client."
   - Sections in order: Install (pip install sentarion-mcp; then run `sentarion_doctor`), Quick start (Claude Code, Codex, Cursor tabs as three short snippets linking to examples/), Tools (table incl. the new tools), Governance (unchanged text), Examples (link list), Free vs v2 (two columns from the GTM plan §24 headline items only), Join v2 early access (link https://inboxaxe.com/mcp and `sentarion_pro(email="you@company.com")`), Changelog (keep the 0.2.2 list under a "0.2.2" heading), Support (unchanged).
   - Do not claim any metric, testimonial, or dogfood result.
3. server.json description: "Give your AI agents rules, memory, and receipts. Governed multi-agent orchestration for MCP." (verify it is at most 100 characters).

DATA CONTRACT:
- none.

UX REQUIREMENTS:
- Every example is copy-paste runnable. No screenshots.

ERROR STATES:
- Runnable examples print a one-line reason and exit 1 on failure; never traceback-only.

SECURITY / PERMISSIONS:
- Examples never embed keys; they read env vars and say so.

TESTS REQUIRED:
- Run `python examples/worktree/worktree_example.py` locally and paste the output in RETURN. Run `python examples/multi_agent/dispatch_example.py`; if the doctor reports not ready on this machine, the expected exit-1 message is the acceptable result; paste it.
- `python -c "import json; d=json.load(open('server.json')); assert len(d['description'])<=100"`.

ACCEPTANCE CRITERIA:
1. All files under examples/ exist as specified; both runnable scripts execute without traceback.
2. README first line is exactly the positioning line; mcp-name marker preserved.
3. server.json description within 100 chars; nothing else in server.json changed.
4. Changed and new files are a subset of FILES ALLOWED.

DO NOT:
- invent metrics or testimonials
- add placeholder production data
- change any code under sentarion_mcp/
- commit

RETURN:
- concise implementation summary
- files changed
- example run outputs
- failures / blockers
- exact assumptions remaining
