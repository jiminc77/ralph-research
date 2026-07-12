import hashlib
import json
import sqlite3
import subprocess
import yaml

import pytest
from click.testing import CliRunner

from ralph_core.cli import main
from ralph_core.preflight import Preflight
from ralph_core.schemas import Config
from tests.fakes.fake_seams import (
    FakeDesign,
    FakeFigureFallback,
    FakeGJC,
    FakeSandbox,
    make_template_repo,
)


@pytest.mark.timeout(30)
def test_start_full_sequence_with_fake_seams_reaches_durable_ready(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["start", "--yes"])
    assert result.exit_code == 0, result.output
    assert (root / "config.lock.yml").is_file()
    run = next((root / "runs").glob("run-*"))
    with sqlite3.connect(run / "state.db") as db:
        status = db.execute("SELECT status FROM runs").fetchone()[0]
    assert status == "ready"
    runtime = json.loads((run / "runtime.lock.json").read_text())
    assert runtime["resolved_models"]["reviewer"]["alias"] == "claude-opus-4-8"
    assert set(runtime["schema_sha256"]) == {
        "core-v4.1-lean.sql",
        "worker-result.schema.json",
    }
    assert runtime["tool_versions"]["python"].startswith("Python ")
    assert runtime["tool_versions"]["git"].startswith("git version ")
    assert runtime["dependency_lock_sha256"] == hashlib.sha256(
        (root / "uv.lock").read_bytes()
    ).hexdigest()
    assert runtime["gjc_protocol"] == 2
    expected = {
        "config.lock.yml",
        "RESEARCH_SPEC.md",
        "DECISION_POLICY.md",
        "ONE_LINER.md",
        "data/data_manifest.lock.json",
        "statistics/statistical_protocol.lock.json",
        "venue/venue_profile.lock.yml",
    }
    assert expected <= set(runtime["immutable_inputs"])


@pytest.mark.timeout(30)
def test_failing_seam_exits_3_naming_first_failing_check(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    FakeGJC.ok = False
    monkeypatch.chdir(root)
    try:
        result = CliRunner().invoke(main, ["start", "--yes"])
    finally:
        FakeGJC.ok = True
    assert result.exit_code == 3
    assert "GJC smoke" in result.output
    assert not list((root / "runs").glob("run-*/state.db"))


@pytest.mark.timeout(30)
def test_dirty_repo_fails_preflight(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    (root / "mess.txt").write_text("untracked")
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["start", "--yes"])
    assert result.exit_code == 3
    assert "repository state" in result.output


@pytest.mark.timeout(30)
def test_abort_without_yes_exits_5_and_removes_run(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["start"], input="n\n")
    assert result.exit_code == 5
    assert not list((root / "runs").glob("run-*"))


def test_wal_probe_check_in_report(tmp_path):
    root = make_template_repo(tmp_path)
    report = Preflight(root, Config.load(root / "config.yml")).run()
    assert any(check.name == "WAL probe" and check.status == "passed" for check in report.checks)

def test_sandbox_required_failure_blocks_start(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    FakeSandbox.ok = False
    monkeypatch.chdir(root)
    try:
        result = CliRunner().invoke(main, ["start", "--yes"])
    finally:
        FakeSandbox.ok = True
    assert result.exit_code == 3
    assert "sandbox" in result.output


def test_unsandboxed_fallback_blocks_start(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    config_path = root / "config.yml"
    config = Config.load(config_path).data
    config["security"]["allow_unsandboxed"] = True
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    subprocess.run(["git", "add", "config.yml"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "allow unsandboxed"], cwd=root, check=True)
    report = Preflight(root, Config.load(config_path)).run()
    sandbox = next(check for check in report.checks if check.name == "sandbox")
    assert sandbox.detail == "unsandboxed fallback denied"
    monkeypatch.chdir(root)

    result = CliRunner().invoke(main, ["start", "--yes"])

    assert result.exit_code == 3
    assert "sandbox" in result.output


def test_sandbox_not_required_passes(tmp_path):
    root = make_template_repo(tmp_path)
    config_path = root / "config.yml"
    config = Config.load(config_path).data
    config["security"]["sandbox_required"] = False

    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    report = Preflight(root, Config.load(config_path)).run()
    sandbox = next(check for check in report.checks if check.name == "sandbox")
    assert sandbox.status == "passed"
    assert sandbox.detail == "not required"


def test_design_failure_with_fallback_passes_with_limitation(tmp_path):
    root = make_template_repo(tmp_path)
    FakeDesign.ok = False
    try:
        report = Preflight(root, Config.load(root / "config.yml")).run()
    finally:
        FakeDesign.ok = True
    design = next(check for check in report.checks if check.name == "design smoke")
    assert design.status == "passed"
    assert design.detail == "design unavailable; local fallback verified"


def test_design_and_fallback_failure_fails(tmp_path):
    root = make_template_repo(tmp_path)
    FakeDesign.ok = False
    FakeFigureFallback.ok = False
    try:
        report = Preflight(root, Config.load(root / "config.yml")).run()
    finally:
        FakeDesign.ok = True
        FakeFigureFallback.ok = True
    design = next(check for check in report.checks if check.name == "design smoke")
    assert design.status == "failed"
    assert report.first_failure == "design smoke"


def test_dataset_hash_mismatch_fails(tmp_path):
    root = make_template_repo(tmp_path)
    dataset_path = root / "data" / "dataset.bin"
    dataset_path.write_bytes(b"dataset")
    manifest_path = root / "data" / "data_manifest.lock.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dataset"]["path"] = "data/dataset.bin"
    manifest["dataset"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    report = Preflight(root, Config.load(root / "config.yml")).run()
    dataset = next(check for check in report.checks if check.name == "dataset")
    assert dataset.status == "failed"
    assert dataset.detail == "dataset hash mismatch: data/dataset.bin"




def test_preflight_check_order_matches_spec(tmp_path):
    root = make_template_repo(tmp_path)
    report = Preflight(root, Config.load(root / "config.yml")).run()
    assert [check.name for check in report.checks] == [
        "config/spec schema",
        "repository state",
        "dependencies",
        "sandbox",
        "dataset",
        "disk free",
        "WAL probe",
        "model aliases",
        "GJC smoke",
        "design smoke",
        "venue compile",
    ]
