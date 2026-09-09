"""Create, list and remove a git worktree through the Sentarion MCP server.

Builds a throwaway git repository in a temporary directory so nothing of yours
is touched, then calls the `worktree` tool over stdio with the official `mcp`
client (`pip install mcp`). create and remove pass the two-chamber gate; list
is read-only.

Exit codes: 0 on success, 1 with a one-line reason on any failure.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover
    print("the `mcp` Python client is missing: pip install mcp")
    sys.exit(1)


def _server_params() -> StdioServerParameters:
    """SENTARION_CMD (a full command line) wins; then the `sentarion` console script; then the module,
    which is what you want when running from a checkout of the repository."""
    override = os.environ.get("SENTARION_CMD")
    if override:
        argv = [a.strip('"') for a in shlex.split(override, posix=(os.name != "nt"))]
        return StdioServerParameters(command=argv[0], args=argv[1:], env=dict(os.environ))
    cmd = shutil.which("sentarion")
    if cmd:
        return StdioServerParameters(command=cmd, args=[], env=dict(os.environ))
    return StdioServerParameters(command=sys.executable, args=["-m", "sentarion_mcp.server"], env=dict(os.environ))


def _one_line(value, limit: int = 200) -> str:
    return " ".join(str(value).split())[:limit]


def _root_cause(e: BaseException) -> BaseException:
    """anyio wraps errors raised inside stdio_client in an ExceptionGroup; report the innermost one."""
    while getattr(e, "exceptions", None):
        e = e.exceptions[0]
    return e


def _json(result):
    raw = "".join(b.text for b in (result.content or []) if getattr(b, "type", "") == "text")
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=example@sentarion.local", "-c", "user.name=Sentarion Example", *args],
        check=True, capture_output=True, text=True, timeout=60,
    )


def _make_repo(root: str) -> str:
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", "main")
    with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# throwaway repo for the Sentarion worktree example\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


async def _call(session: ClientSession, args: dict):
    out = _json(await session.call_tool("worktree", args))
    print(f"worktree {args['action']}: {json.dumps(out, indent=2)}")
    if isinstance(out, dict) and out.get("error"):
        raise RuntimeError(out["error"])
    if isinstance(out, dict) and (out.get("created") is False or out.get("removed") is False):
        raise RuntimeError(f"governance blocked {args['action']}: {(out.get('governance') or {}).get('reason')}")
    return out


async def main() -> int:
    if not shutil.which("git"):
        print("git is not on PATH; install git first")
        return 1
    root = tempfile.mkdtemp(prefix="sentarion-wt-")
    try:
        repo = _make_repo(root)
        wt_path = os.path.join(root, "wt-example")
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                created = await _call(session, {"action": "create", "repo_path": repo, "branch": "example/scratch", "path": wt_path})
                listed = await _call(session, {"action": "list", "repo_path": repo})
                names = [w.get("branch") for w in (listed.get("worktrees") or [])]
                if not any("example/scratch" in str(n) for n in names):
                    print(f"the new worktree is missing from the list: {names}")
                    return 1
                await _call(session, {
                    "action": "remove", "repo_path": repo,
                    "worktree_path": created["worktree_path"], "force": True, "delete_branch": "example/scratch",
                })
        print("done: created, listed and removed a governed worktree; the temporary repo is deleted")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"git failed: {(e.stderr or e.stdout or '').strip().splitlines()[-1] if (e.stderr or e.stdout) else e}")
        return 1
    except FileNotFoundError as e:
        print(f"could not start the sentarion server: {e}. Fix: pip install sentarion-mcp")
        return 1
    except Exception as e:  # noqa: BLE001
        cause = _root_cause(e)
        print(f"worktree example failed: {type(cause).__name__}: {_one_line(cause)}")
        return 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
