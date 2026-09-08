TASK:
Add MCP server instructions, fix the sentarion_birth fallback NameError, unify the package version, and stop tracking built wheels.

WHY:
Clients receive no usage guidance today (Patch A of the GTM plan). The ArkHive birth fallback crashes on the default install path because `tool_text` is used but never imported. Three different version strings confuse users. Tracked `dist/` wheels bloat the repo.

KNOWN FACTS:
- Repo: this worktree (branch week1-oss-patches, base 6e227e6). Package dir: sentarion_mcp/. Raw MCP SDK `Server` is used (server.py line 46 and 89); NOT FastMCP.
- `mcp.server.Server.__init__` accepts `instructions: str | None` and `version: str | None` (verified in the installed SDK), and `app.create_initialization_options()` (server.py line 487) forwards them to clients.
- server.py line 275 calls `tool_text(result)`; the import block at server.py lines 50-58 imports only tool_json, tool_records, record_ts. `tool_text` is defined in clients.py line 184.
- Versions: pyproject.toml line 3 = "0.2.2"; sentarion_mcp/__init__.py line 3 = "0.1.0"; server.json version = "0.2.2".
- dist/ contains six tracked build artifacts (git ls-files dist/); .gitignore lacks `dist/`.
- There is no tests/ directory and no pytest config. `python -m pytest` (pytest 9) is available.

UNKNOWNS:
- none

FILES ALLOWED:
- sentarion_mcp/server.py
- sentarion_mcp/__init__.py
- .gitignore
- dist/ (git rm --cached only; do not delete files from disk)
- tests/__init__.py, tests/test_server_meta.py (new)
- pyproject.toml (ONLY to add a `[tool.pytest.ini_options]` block with `testpaths = ["tests"]`; do not change version or dependencies)

FILES FORBIDDEN:
- everything else (clients.py, govern_stub.py, dependency_graph.py, cost_estimate.py, worktree.py, README.md, server.json, smithery.yaml, glama.json, .github/**, docs/**)

CURRENT BEHAVIOR:
- `Server("sentarion-mcp")` with no instructions. Birth fallback raises NameError. Version strings disagree.

REQUIRED BEHAVIOR:
1. In server.py define a module constant `INSTRUCTIONS` (a plain string, at most 1800 characters) and construct the server as `app = Server("sentarion-mcp", version=__version__, instructions=INSTRUCTIONS)`. The text must, in this order and in plain language: (a) say what Sentarion is in one sentence: "Sentarion gives your AI agents rules, memory, and receipts: a governed, fail-closed orchestration layer over Algernon (dispatch), ArkHive (hosted tamper-evident memory) and a local covenant chamber."; (b) tell the agent to call `sentarion_birth` once to obtain a soul_id and pass it as `actor`; (c) tell the agent to call `govern` before any action that sends, deletes, spends, deploys or edits files, and that a `block` verdict is final and must not be worked around; (d) tell the agent never to invent tool results, chain records or capabilities: if a chain reports `not_configured` or `error`, say so to the user; (e) explain `dispatch_with_dependencies`: tasks_json is an array of {id, prompt, depends_on}; `{{id}}` in a prompt is replaced with the result of that task; (f) explain the free/paid boundary in one sentence: everything in this server is free and Apache-2.0; `sentarion_pro` describes the paid v2 control plane and never changes free behavior.
2. Add `tool_text` to the import list from `.clients` in server.py so the fallback at line 275 works.
3. Set `__version__ = "0.2.2"` in sentarion_mcp/__init__.py and import it in server.py (`from . import __version__`).
4. Add `dist/` and `build/` to .gitignore and run `git rm -r --cached dist` so the six artifacts are untracked (files stay on disk).
5. Create tests/__init__.py (empty) and tests/test_server_meta.py with pytest tests that: (a) import sentarion_mcp.server and assert `INSTRUCTIONS` contains the substrings "rules, memory, and receipts", "sentarion_birth", "govern", "{{id}}", "Apache-2.0"; (b) assert `len(INSTRUCTIONS) <= 1800`; (c) assert `sentarion_mcp.__version__ == "0.2.2"`; (d) assert `from sentarion_mcp.server import tool_text` works; (e) call `app.create_initialization_options()` and assert `.instructions == INSTRUCTIONS` and `.server_version == "0.2.2"`.

DATA CONTRACT:
- none (no runtime data shape changes).

UX REQUIREMENTS:
- INSTRUCTIONS is plain prose paragraphs, no markdown headers, no marketing adjectives.

ERROR STATES:
- none new.

SECURITY / PERMISSIONS:
- Do not add network calls. Do not change govern_stub or any gate.

TESTS REQUIRED:
- `python -m pytest -q` passes from the worktree root.
- `python -c "import sentarion_mcp.server"` succeeds.

ACCEPTANCE CRITERIA:
1. `python -m pytest -q` passes every test in tests/test_server_meta.py.
2. Changed and new files are a subset of FILES ALLOWED; dist/ artifacts show as deleted from the index.
3. `grep -n "tool_text" sentarion_mcp/server.py` shows it in the import block.

DO NOT:
- infer missing APIs
- add placeholder production data
- redesign unrelated screens
- change schema outside task
- remove existing behavior without reporting it
- change any tool inputSchema or behavior
- commit (leave changes uncommitted; the orchestrator commits after review)

RETURN:
- concise implementation summary
- files changed
- tests run (exact command + pass/fail counts)
- failures / blockers
- exact assumptions remaining
