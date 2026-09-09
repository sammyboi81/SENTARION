import subprocess
import types

import pytest

import sentarion_mcp.worktree as worktree


def test__git_passes_devnull(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, capture_output=False, text=False, timeout=None, stdin=None):
        seen['stdin'] = stdin
        # emulate CompletedProcess
        cp = types.SimpleNamespace()
        cp.returncode = 0
        cp.stdout = 'true\n'
        cp.stderr = ''
        return cp

    monkeypatch.setattr(worktree, 'subprocess', types.SimpleNamespace(run=fake_run, DEVNULL=subprocess.DEVNULL))

    repo = tmp_path / 'd'
    repo.mkdir()
    out = worktree._git(str(repo), 'rev-parse', '--is-inside-work-tree')
    assert out == 'true'
    assert seen['stdin'] is subprocess.DEVNULL


def test__git_real_call(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    # init a git repo
    subprocess.run(['git', 'init', str(repo)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out = worktree._git(str(repo), 'rev-parse', '--is-inside-work-tree', timeout=5)
    assert out.strip() == 'true'
