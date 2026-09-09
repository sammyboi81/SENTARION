# BLOCKED / discrepancies found while executing WO-S1..S5

Written by the implementer when a KNOWN FACT proved false or two work orders contradicted each other. Nothing here was worked around silently.

## WO-S4: `worktree` tool hangs on Windows when the server is launched over MCP stdio (fix is in a forbidden file)

**Symptom.** `python examples/worktree/worktree_example.py` prints
`worktree create: {"error": "git_error: git timed out after 60s: rev-parse --is-inside-work-tree"}` and exits 1.
The same `wt.create / list / remove` calls succeed in 0.08 s when invoked in-process (verified), and every other tool
(doctor, dispatch, birth, govern) works over stdio on this machine.

**Root cause (reproduced, not guessed).** `sentarion_mcp/worktree.py::_git` runs
`subprocess.run(["git", ...], capture_output=True, text=True, timeout=...)` with no `stdin=` argument, so git inherits the
server's stdin, which is the MCP pipe. On Windows, once `mcp.server.stdio.stdio_server()` has an anyio worker thread
blocked in a read on that pipe, any child that inherits the same stdin handle never lets the parent's stdout/stderr
reader threads finish: git blocks until `timeout`. A faulthandler dump of the hung server shows both
`subprocess._readerthread`s waiting and `_git` in `communicate()`.

Controlled probe inside a `stdio_server()` child after the stdin reader had started (git 2.52.0.windows.1, mcp 1.29.1, Python 3.12.10):

| `subprocess.run` variant | result |
|---|---|
| default (inherit stdin) | TimeoutExpired |
| `close_fds=False` | TimeoutExpired |
| `creationflags=CREATE_NO_WINDOW` | TimeoutExpired |
| `stdin=subprocess.DEVNULL` | ok, 0.02 s |
| `stdin=subprocess.PIPE` | ok, 0.01 s |
| `stdin=DEVNULL` + `CREATE_NO_WINDOW` | ok, 0.03 s |

Calling git *before* the stdin reader starts (or with no MCP transport at all) never hangs, which is why the unit path passes.

**Fix (one line, needs a work order because `worktree.py` is FORBIDDEN in WO-S1..S5).** In `sentarion_mcp/worktree.py::_git`, add
`stdin=subprocess.DEVNULL` to the `subprocess.run(...)` call. git never reads stdin in any command the tool issues.
The Algernon / local-chamber child processes are unaffected (they are spawned by `stdio_client` with `stdin=PIPE`).

**Status of the example.** `examples/worktree/worktree_example.py` is complete and correct: it exits 1 with a one-line reason
and no traceback (acceptance criterion met), and will pass end-to-end once the one-line fix ships. Not user-facing on
Linux/macOS as far as tested here (not tested; the mechanism is Windows handle inheritance).

## WO-S5 vs WO-S1: version literal in `tests/test_server_meta.py`

WO-S1 REQUIRED BEHAVIOR 5(c) mandated `assert sentarion_mcp.__version__ == "0.2.2"`. WO-S5 bumps every declared version to
0.3.0 and lists `tests/` under FILES FORBIDDEN ("all other files"), while its ACCEPTANCE CRITERIA 1 requires
`python -m pytest -q` to pass and CRITERIA 2 requires no `0.2.2` in version fields of `*.py`. The three cannot all hold.

**Resolution taken.** `tests/test_server_meta.py::test_version_unified` now asserts `sentarion_mcp.__version__` equals
`[project].version` in `pyproject.toml` (the same drift check the CI step runs) instead of a literal. This is the smallest
edit that keeps WO-S1's intent (one unified version) and WO-S5's acceptance criteria. Reported here and in the RETURN block
rather than applied silently.

## WO-S4 note: `sentarion` on PATH is not this checkout on the build machine

KNOWN FACT "examples runnable with `sentarion` on PATH" holds for a user who `pip install sentarion-mcp`. On this build
machine, `import sentarion_mcp` outside the worktree resolves to `C:\Users\tiger\zagairot-mcp-v2\packages\sentarion-mcp`
(an editable/.pth install, version 0.2.0 per pip), which has no `sentarion_doctor`. Both example scripts therefore honour
`SENTARION_CMD` (a full command line, e.g. `"C:\Program Files\Python312\python.exe" -m sentarion_mcp.server`) before
falling back to `sentarion` on PATH and then to `python -m sentarion_mcp.server`. The RETURN outputs were produced with
`SENTARION_CMD` pointing at this worktree. No fix needed in the repo; noted so the reviewer does not run the wrong server.

## WO-S4 note: dispatch example on this machine

`OPENAI_API_KEY` is set on this machine but rejected by OpenAI (401 "Incorrect API key provided"). `sentarion_doctor`
reports `ready: true` because it checks that a key is *set*, exactly as WO-S2 specifies ("whether ANTHROPIC_API_KEY or
OPENAI_API_KEY is SET"). The dispatch therefore ran (governance approved, 2 waves, `{{id}}` substitution happened) and all
three workers failed with 401; the example now exits 1 with "every task failed; first error: ..." in that case. Fixing the
key is an environment action for the founder, not a repo change.

## WO-S5: `tomllib` does not exist on Python 3.10

WO-S5 REQUIRED BEHAVIOR 1 specifies a matrix of Python 3.10 and 3.12 and a final step that does `import tomllib`.
`tomllib` was added in Python 3.11, so the exact one-liner would fail with `ModuleNotFoundError` on the 3.10 leg.
Resolution: the install step also installs `tomli`, and the one-liner selects `tomllib` on 3.11+ and `tomli` below
(same assertions, plus `server.json` `packages[].version`, plus an explicit drift message). Verified locally on 3.12.
