from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from ralph_core.bootstrap import RepoStateError, commit_all, ensure_repo


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, stdout=subprocess.PIPE).stdout


def test_ensure_repo_initializes_fresh_directory_on_main(repo_factory) -> None:
    root = repo_factory()
    state = ensure_repo(root)
    assert state == {"initialized": True, "branch": "main", "dirty": False}
    assert (root / ".git").is_dir()


def test_ensure_repo_is_noop_for_clean_repository(repo_factory) -> None:
    root = repo_factory()
    ensure_repo(root)
    assert ensure_repo(root) == {"initialized": False, "branch": "main", "dirty": False}


def test_ensure_repo_rejects_dirty_existing_repository(repo_factory) -> None:
    root = repo_factory()
    ensure_repo(root)
    (root / "untracked.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(RepoStateError):
        ensure_repo(root, require_clean_start=True)


def test_commit_all_uses_local_identity_fallback(repo_factory, monkeypatch) -> None:
    root = repo_factory()
    ensure_repo(root)
    isolated_home = root / "home"
    isolated_home.mkdir()
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(isolated_home / "global.gitconfig"))
    (root / "tracked.txt").write_text("content", encoding="utf-8")
    commit_all(root, "initial commit")
    assert git(root, "log", "-1", "--format=%an <%ae>").strip() == "ralph <ralph@local>"
