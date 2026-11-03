"""Claude Code PreToolUse hook: refuse Edit/Write/NotebookEdit in the main git checkout.

Several Claude sessions can be open on this repo at once. They share the main checkout's
files and branch, so one session switching branches or editing a file breaks the others.
Each session should work in its own linked worktree instead (see CLAUDE.md).

Exit code 2 blocks the tool call and shows stderr to Claude; 0 allows it. Any unexpected
problem (bad input, git missing) allows the call: this guardrail must never wedge a session.

Escape hatch: set THEIA_ALLOW_MAIN_EDIT=1 (e.g. in .claude/settings.local.json "env").
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BLOCK_MESSAGE = """Blocked: {path} is in the main checkout ({top}).
Other Claude sessions share this folder and its branch, so edit from your own worktree:

  git fetch && git worktree add -b deploy/<card-id>-<slug> ../theia-<card-id> origin/master

then work inside ../theia-<card-id> (see "Parallel sessions" in CLAUDE.md).
To allow main-checkout edits deliberately, set THEIA_ALLOW_MAIN_EDIT=1."""


def _target_path(payload: dict) -> Path | None:
    tool_input = payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(payload.get("cwd") or os.getcwd()) / path
    return path


def _nearest_existing_dir(path: Path) -> Path | None:
    for candidate in [path.parent, *path.parent.parents]:
        if candidate.is_dir():
            return candidate
    return None


def _git_dirs(directory: Path) -> tuple[Path, Path, str] | None:
    """(git_dir, common_dir, toplevel) for the repo containing directory, or None."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir", "--git-common-dir", "--show-toplevel"],
        cwd=directory,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    git_dir, common_dir, top = result.stdout.splitlines()[:3]
    return (
        Path(os.path.realpath(directory / git_dir)),
        Path(os.path.realpath(directory / common_dir)),
        top,
    )


def main() -> int:
    if os.environ.get("THEIA_ALLOW_MAIN_EDIT") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
        path = _target_path(payload)
        directory = _nearest_existing_dir(path) if path else None
        if directory is None:
            return 0
        dirs = _git_dirs(directory)
    except Exception:
        return 0
    if dirs is None:
        return 0  # not in a git repo
    git_dir, common_dir, top = dirs
    # In a linked worktree --git-dir is <common>/worktrees/<name>, not the common dir.
    if os.path.normcase(str(git_dir)) != os.path.normcase(str(common_dir)):
        return 0
    print(BLOCK_MESSAGE.format(path=path, top=top), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
