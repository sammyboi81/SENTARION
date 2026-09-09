TASK:
Fix the Windows hang in the OSS worktree helper: git subprocesses inherit the MCP server's stdin pipe and block.

WHY:
Found by WO-S4's runnable example (docs/BLOCKED.md): on Windows, `_git` in sentarion_mcp/worktree.py lets git inherit stdin; once stdio_server's reader thread holds the pipe, `git rev-parse --is-inside-work-tree` hangs until the 60 s timeout. Probe table in BLOCKED.md: stdin=DEVNULL or PIPE → 0.02 s.

KNOWN FACTS:
- sentarion_mcp/worktree.py defines `_git(repo, *args, timeout=60) -> str` (around line 364 in the original numbering) using subprocess.run with capture_output=True and a timeout.
- Tests live in tests/; `python -m pytest -q` currently reports 25 passed.

FILES ALLOWED:
- sentarion_mcp/worktree.py (the `_git` call only)
- tests/test_worktree_stdin.py (new; justification: no worktree test exists)

FILES FORBIDDEN: everything else.

REQUIRED BEHAVIOR:
1. Add `stdin=subprocess.DEVNULL` to the subprocess.run call in `_git`. Change nothing else.
2. tests/test_worktree_stdin.py: monkeypatch subprocess.run inside worktree to capture kwargs and assert `stdin` is subprocess.DEVNULL when `_git` is called; plus one real test that runs `_git(tmp_repo, "rev-parse", "--is-inside-work-tree")` on a `git init`-ed tmp_path and returns "true" within 5 s.

ACCEPTANCE CRITERIA: `python -m pytest -q` passes (27 expected); `git diff --stat` shows only the two files.

DO NOT: touch any other function; commit.

RETURN: diff summary, test command + counts.
