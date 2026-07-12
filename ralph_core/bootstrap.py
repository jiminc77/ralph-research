"""Git repository bootstrap helpers."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Sequence


class RepoStateError(Exception):
    """Raised when repository state violates bootstrap requirements."""


def _git(root: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _branch(root: Path) -> str:
    result = _git(root, ["branch", "--show-current"])
    return result.stdout.strip() or "main"


def _dirty(root: Path) -> bool:
    return bool(_git(root, ["status", "--porcelain"]).stdout.strip())


def ensure_repo(root: Path, require_clean_start: bool = True) -> dict[str, bool | str]:
    root = Path(root)
    git_dir = root / ".git"
    initialized = not git_dir.exists()
    if initialized:
        root.mkdir(parents=True, exist_ok=True)
        init = _git(root, ["init", "-b", "main"], check=False)
        if init.returncode != 0:
            _git(root, ["init"])
            _git(root, ["checkout", "-B", "main"])
    elif require_clean_start and _dirty(root):
        raise RepoStateError(f"repository is dirty: {root}")
    return {"initialized": initialized, "branch": _branch(root), "dirty": _dirty(root)}


def commit_all(root: Path, message: str) -> None:
    """Stage all non-ignored changes and commit them with a local identity fallback."""
    root = Path(root)
    _git(root, ["add", "-A"])
    if _git(root, ["diff", "--cached", "--quiet"], check=False).returncode == 0:
        return
    name = _git(root, ["config", "--get", "user.name"], check=False)
    email = _git(root, ["config", "--get", "user.email"], check=False)
    args = ["commit", "-m", message]
    if not name.stdout.strip() or not email.stdout.strip():
        args = ["-c", "user.name=ralph", "-c", "user.email=ralph@local", *args]
    _git(root, args)
