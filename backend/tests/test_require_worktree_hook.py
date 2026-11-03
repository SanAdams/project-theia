"""The Claude Code PreToolUse hook that keeps sessions out of the main checkout.

Exit code 2 blocks the tool call; 0 allows it. Tests build a throwaway git repo
with a linked worktree so the real `git` behavior is what's being checked."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "claude-hooks" / "require_worktree.py"


def _clean_env():
    """Drop GIT_* vars (GIT_INDEX_FILE, GIT_DIR...) that git sets while running a commit
    hook, so subprocess git calls act on the throwaway repo, never the real one."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env=_clean_env(),
    )


def make_repo(base):
    main = base / "main"
    main.mkdir(parents=True)
    _git(main, "init", "-q", "-b", "master")
    (main / "app.py").write_text("x = 1\n")
    _git(main, "add", ".")
    _git(main, "commit", "-q", "-m", "init")
    wt = base / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feature", str(wt))
    return main, wt


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


def test_fixture_ignores_git_env_leaked_from_a_commit_hook(tmp_path, monkeypatch):
    """pre-commit runs pytest with GIT_INDEX_FILE etc. set; if the fixture inherits them
    its `git add .` rewrites the REAL repo's index instead of the throwaway one."""
    leaked = tmp_path / "leaked-index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(leaked))
    main, _ = make_repo(tmp_path / "r")
    assert (main / ".git" / "index").exists()
    assert not leaked.exists()


def run_hook(payload, env_extra=None, raw=None):
    env = {k: v for k, v in _clean_env().items() if k != "THEIA_ALLOW_MAIN_EDIT"}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def edit(path, tool="Edit", key="file_path"):
    return {"tool_name": tool, "tool_input": {key: str(path)}}


def test_blocks_edit_in_main_checkout(repo):
    main, _ = repo
    result = run_hook(edit(main / "app.py"))
    assert result.returncode == 2
    assert "git worktree add" in result.stderr


def test_blocks_creating_a_new_file_in_main_checkout(repo):
    main, _ = repo
    result = run_hook(edit(main / "new_dir" / "new.py", tool="Write"))
    assert result.returncode == 2
    assert "git worktree add" in result.stderr


def test_blocks_notebook_edit_in_main_checkout(repo):
    main, _ = repo
    result = run_hook(edit(main / "nb.ipynb", tool="NotebookEdit", key="notebook_path"))
    assert result.returncode == 2
    assert "git worktree add" in result.stderr


def test_allows_edit_in_linked_worktree(repo):
    _, wt = repo
    assert run_hook(edit(wt / "app.py")).returncode == 0


def test_allows_file_outside_any_git_repo(tmp_path):
    assert run_hook(edit(tmp_path / "notes.txt", tool="Write")).returncode == 0


def test_override_env_var_allows_main_checkout(repo):
    main, _ = repo
    result = run_hook(edit(main / "app.py"), env_extra={"THEIA_ALLOW_MAIN_EDIT": "1"})
    assert result.returncode == 0


def test_garbage_input_fails_open():
    assert run_hook(None, raw="not json").returncode == 0


def test_payload_without_a_path_is_allowed():
    assert run_hook({"tool_name": "Edit", "tool_input": {}}).returncode == 0
