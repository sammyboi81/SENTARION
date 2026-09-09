# Dispatched work runs in a worktree

## Why

Fleet workers and implementer agents edit files. If they edit the checkout you are sitting in, a bad run can overwrite uncommitted work, and you cannot tell afterwards which changes were yours and which were the agent's. This is the exact failure Sentarion's `worktree` tool exists to prevent (its docstring cites the incident that motivated it).

A git worktree is a second working directory backed by the same repository, on its own branch. Work done there:

- never touches the primary checkout,
- is a normal branch, so you review it with `git diff` and merge or discard it,
- can be removed in one governed call when you are done.

## The tool

`worktree(action, repo_path, ...)`:

| action | governed | arguments |
|---|---|---|
| `create` | yes (`mutates_repo`, `creates_branch`) | `branch` (required), `base` (default `HEAD`), `path` (optional explicit directory) |
| `list` | no (read-only) | none |
| `remove` | yes (`mutates_repo`, `deletes_files`) | `worktree_path` (required), `force`, `delete_branch` |

`create` returns `{governance, worktree_path, branch, base}`. Without `path`, the worktree is created as a sibling of the repo named `wt-<branch>`. If governance blocks, the result is `{governance, created: false}` and nothing changed.

All git calls are argv lists with a timeout, never shell strings, so a crafted branch name cannot inject a command.

## Run it

```bash
pip install sentarion-mcp mcp
python examples/worktree/worktree_example.py
```

The script creates a throwaway git repository in a temporary directory, then through the server calls `worktree create`, `worktree list`, and `worktree remove` (with `delete_branch`), printing each result, and deletes the temporary directory at the end. It exits 1 with a one-line reason if git is missing, the server cannot start, or governance blocks a step.

In Sentarion v2 the same tool also produces a diff of the worktree, applies a reviewed patch into it, and commits from it; create, list and remove stay as they are.
