"""
Git worktree skill — isolated sandboxes for orchestrated work.

Directly answers the rogue-incident hardening item "workers should not have
live write access": instead of dispatching Algernon waves against a live
checkout, create a throwaway git worktree, let the work happen there, then
review/merge/discard. A worktree is a second working directory backed by the
same repo, on its own branch — mutations never touch the primary checkout.

Mutating actions (create, remove) are governed by the two-chamber gate at the
server layer. `list` is read-only and ungated.

All git calls are argv lists (never shell strings) with a timeout, so nothing
here is injectable through a crafted branch name or path.
"""

from __future__ import annotations

import os
import subprocess


class GitError(RuntimeError):
    pass


def _git(repo_path: str, *args: str, timeout: int = 60) -> str:
    if not os.path.isdir(repo_path):
        raise GitError(f"repo_path is not a directory: {repo_path}")
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise GitError(f"git not found on PATH: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git timed out after {timeout}s: {' '.join(args)}") from e
    if proc.returncode != 0:
        raise GitError((proc.stderr or proc.stdout or "git failed").strip())
    return proc.stdout.strip()


def _assert_repo(repo_path: str) -> None:
    inside = _git(repo_path, "rev-parse", "--is-inside-work-tree")
    if inside.strip() != "true":
        raise GitError(f"not a git work tree: {repo_path}")


def create(repo_path: str, branch: str, base: str | None = None,
           path: str | None = None) -> dict:
    """Create a new worktree on a fresh branch off `base` (default: HEAD).

    Returns {worktree_path, branch, base}. The worktree dir must not exist yet.
    """
    _assert_repo(repo_path)
    if not branch or "/" in branch.strip("/") and branch.startswith("/"):
        raise GitError(f"invalid branch name: {branch!r}")
    base_ref = base or "HEAD"

    if path:
        wt_path = os.path.abspath(path)
    else:
        parent = os.path.dirname(os.path.abspath(repo_path.rstrip("/\\")))
        safe = branch.replace("/", "-")
        wt_path = os.path.join(parent, f"wt-{safe}")

    if os.path.exists(wt_path):
        raise GitError(f"worktree path already exists: {wt_path}")

    # -b creates the branch; fails loudly if the branch already exists.
    _git(repo_path, "worktree", "add", "-b", branch, wt_path, base_ref, timeout=120)
    return {"worktree_path": wt_path, "branch": branch, "base": base_ref}


def list_worktrees(repo_path: str) -> list[dict]:
    """List existing worktrees (porcelain-parsed). Read-only."""
    _assert_repo(repo_path)
    out = _git(repo_path, "worktree", "list", "--porcelain")
    trees: list[dict] = []
    cur: dict = {}
    for line in out.splitlines():
        if not line.strip():
            if cur:
                trees.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            cur["path"] = line[len("worktree "):]
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):]
        elif line.strip() in ("bare", "detached", "locked"):
            cur[line.strip()] = True
    if cur:
        trees.append(cur)
    return trees


def remove(repo_path: str, worktree_path: str, force: bool = False,
           delete_branch: str | None = None) -> dict:
    """Remove a worktree (and optionally delete its branch).

    `force` allows removal of a worktree with uncommitted changes.
    """
    _assert_repo(repo_path)
    args = ["worktree", "remove", worktree_path]
    if force:
        args.append("--force")
    _git(repo_path, *args, timeout=120)

    branch_deleted = None
    if delete_branch:
        _git(repo_path, "branch", "-D", delete_branch, timeout=60)
        branch_deleted = delete_branch

    # Tidy administrative files for any now-missing worktrees.
    _git(repo_path, "worktree", "prune", timeout=60)
    return {"removed": worktree_path, "branch_deleted": branch_deleted}
