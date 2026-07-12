import json
import sqlite3

import pytest
from click.testing import CliRunner

from ralph_core.cli import main
from ralph_core.preflight import Preflight
from ralph_core.schemas import Config
from tests.fakes.fake_seams import FakeGJC, make_template_repo


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


def test_preflight_check_order_matches_spec(tmp_path):
    root = make_template_repo(tmp_path)
    report = Preflight(root, Config.load(root / "config.yml")).run()
    assert [check.name for check in report.checks] == [
        "config/spec schema",
        "repository state",
        "dependencies",
        "dataset",
        "disk free",
        "WAL probe",
        "model aliases",
        "GJC smoke",
        "design smoke",
        "venue compile",
    ]
