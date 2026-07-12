"""Hermetic preflight checks, executed in stable order."""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
from typing import Any

from .bootstrap import RepoStateError, ensure_repo
from .resolver import ModelResolver, ResolverError
from .schemas import sha256_file


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    checks: list[PreflightCheck]
    first_failure: str | None


class Preflight:
    def __init__(self, repo_root: str | Path, config: Any, seams: dict[str, Any] | None = None):
        self.root = Path(repo_root)
        self.config = config
        self.cfg = config.data if hasattr(config, "data") else config
        self.seams = seams or {}

    def seam(self, name: str):
        value = self.seams.get(name)
        if value is not None:
            return value
        dotted = self.cfg.get("adapters", {}).get(name)
        if not dotted:
            return None
        module, attribute = dotted.rsplit(".", 1)
        value = getattr(importlib.import_module(module), attribute)
        return value() if isinstance(value, type) else value

    def _call(self, name: str, *args):
        try:
            seam = self.seam(name)
            if seam is None:
                return True
            value = seam(*args) if callable(seam) else True
            if isinstance(value, (list, tuple)):
                return not value
            return bool(value)
        except Exception:
            return False

    def run(self) -> PreflightReport:
        checks: list[PreflightCheck] = []

        def check(name, action):
            try:
                result = action()
                ok, detail = result if isinstance(result, tuple) else (bool(result), "ok")
            except Exception as exc:
                ok, detail = False, str(exc)
            checks.append(PreflightCheck(name, "passed" if ok else "failed", detail))

        check(
            "config/spec schema",
            lambda: (
                isinstance(self.cfg, dict) and bool(self.cfg.get("schema_version")),
                "configuration validated",
            ),
        )

        def repo():
            try:
                ensure_repo(self.root)
                return True, "repository clean"
            except RepoStateError as exc:
                return False, str(exc)

        check("repository state", repo)

        def deps():
            missing = [name for name in ("python", "git") if not shutil.which(name)]
            if missing:
                return False, "missing: " + ", ".join(missing)
            versions = {}
            for name, command in (
                ("python", ["python", "--version"]),
                ("git", ["git", "--version"]),
            ):
                completed = subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                versions[name] = (completed.stdout or completed.stderr).strip()
            for name in ("latex", "chromium"):
                if self.seam(name) is not None and not self._call(name):
                    return False, f"{name} unavailable"
            return True, f"python={versions['python']}; git={versions['git']}"

        check("dependencies", deps)
        def sandbox():
            if not self.cfg.get("security", {}).get("sandbox_required"):
                return True, "not required"
            if self.seam("sandbox") is None:
                return False, "sandbox seam unavailable"
            return self._call("sandbox"), "sandbox seam"

        check("sandbox", sandbox)

        def dataset():
            manifest = json.loads(
                (self.root / self.cfg["paths"]["data_manifest"]).read_text()
            )
            splits = manifest.get("splits", {})
            if not {"search_dev", "hidden_confirmation"} <= set(splits):
                return False, "required splits missing"
            dataset = manifest.get("dataset", {})
            dataset_path = dataset.get("path")
            dataset_sha256 = dataset.get("sha256")
            if dataset_path:
                target = self.root / dataset_path
                if not target.is_file():
                    return False, f"dataset missing: {dataset_path}"
                if dataset_sha256:

                    if sha256_file(target) != dataset_sha256:
                        return False, f"dataset hash mismatch: {dataset_path}"
            return True, "manifest and splits verified"

        check("dataset", dataset)
        threshold = self.cfg.get("run", {}).get("defaults", {}).get(
            "disk_free_bytes", 1_000_000_000
        )
        check(
            "disk free",
            lambda: (shutil.disk_usage(self.root).free >= threshold, f"threshold={threshold}"),
        )

        def wal():
            runs = self.root / self.cfg.get("paths", {}).get("runs_dir", "runs")
            runs.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=runs, suffix=".db", delete=False) as handle:
                path = Path(handle.name)
            try:
                conn = sqlite3.connect(path)
                mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                conn.close()
                return mode.lower() == "wal", f"journal_mode={mode}"
            finally:
                path.unlink(missing_ok=True)
                path.with_name(path.name + "-wal").unlink(missing_ok=True)
                path.with_name(path.name + "-shm").unlink(missing_ok=True)

        check("WAL probe", wal)

        def models():
            catalog = self.seam("catalog")
            if catalog is None:
                return False, "catalog seam unavailable"
            try:
                ModelResolver(self.cfg["models"], catalog).resolve_all()
                return True, "aliases resolved"
            except ResolverError as exc:
                return False, str(exc)

        check("model aliases", models)
        check("GJC smoke", lambda: (self._call("gjc"), "GJC seam"))
        design_ok = self._call("design")
        if design_ok:
            checks.append(PreflightCheck("design smoke", "passed", "design seam"))
        elif self.seam("figure_fallback") is not None and self._call("figure_fallback"):
            checks.append(
                PreflightCheck(
                    "design smoke",
                    "passed",
                    "design unavailable; local fallback verified",
                )
            )
        else:
            checks.append(PreflightCheck("design smoke", "failed", "design and fallback unavailable"))
        check(
            "venue compile",
            lambda: (
                self._call("venue_compile", self.root / self.cfg["paths"]["venue_profile"]),
                "venue seam",
            ),
        )
        failure = next((item.name for item in checks if item.status == "failed"), None)
        return PreflightReport(checks, failure)
