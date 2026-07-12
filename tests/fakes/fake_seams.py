"""Importable hermetic seams and repository fixtures for CLI/preflight tests."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


class FakeCatalog:
    def __init__(self, values=None):
        self.values = {
            "claude-fable-5": "model-fable",
            "claude-opus-4-8": "model-opus",
        } if values is None else values

    def resolve(self, alias):
        return self.values.get(alias)


class _Switch:
    ok = True

    def __call__(self, *args):
        return self.ok


class FakeGJC(_Switch):
    pass


class FakeDesign(_Switch):
    pass


class FakeVenueCompile(_Switch):
    pass


class FakeFigureFallback(_Switch):
    pass


def make_template_repo(tmp_path: Path) -> Path:
    root = Path(__file__).parents[2]
    for name in (
        "RESEARCH_SPEC.md",
        "DECISION_POLICY.md",
        "ONE_LINER.md",
        "references.bib",
        "config.yml",
    ):
        shutil.copy2(root / name, tmp_path / name)
    for name in ("data", "statistics", "venue", "schema"):
        shutil.copytree(root / name, tmp_path / name)
    config_path = tmp_path / "config.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"] = {
        "catalog": "tests.fakes.fake_seams.FakeCatalog",
        "gjc": "tests.fakes.fake_seams.FakeGJC",
        "design": "tests.fakes.fake_seams.FakeDesign",
        "figure_fallback": "tests.fakes.fake_seams.FakeFigureFallback",
        "venue_compile": "tests.fakes.fake_seams.FakeVenueCompile",
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "templates"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path
