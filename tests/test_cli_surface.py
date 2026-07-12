import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from ralph_core.cli import main
from tests.fakes.fake_seams import make_template_repo
def test_launcher_executes_cli():
    root = Path(__file__).parents[1]
    result = subprocess.run(
        ["./ralph", "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "start" in result.stdout



def _seed_run(root: Path, status: str, run_id: str = "run-seeded") -> Path:
    run = root / "runs" / run_id
    run.mkdir(parents=True)
    database = run / "state.db"
    schema = (Path(__file__).parents[1] / "schema" / "core-v4.1-lean.sql").read_text()
    with sqlite3.connect(database) as db:
        db.executescript(schema)
        db.execute(
            "INSERT INTO runs (run_id,name,status,config_json,cost_cap_usd,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (run_id, "seed", status, "{}", 1.0, "2026-01-01T00:00:00+00:00"),
        )

    with sqlite3.connect(database) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        db.execute("SELECT status FROM runs").fetchone()
    return run


@pytest.mark.parametrize(
    ("status", "verb"),
    [
        ("running", "pause"),
        ("running", "stop"),
        ("paused", "stop"),
        ("ready", "kill"),
        ("running", "kill"),
        ("paused", "kill"),
    ],
)
def test_control_file_written_for_allowed_verbs(tmp_path, monkeypatch, status, verb):
    root = make_template_repo(tmp_path)
    run = _seed_run(root, status)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, [verb, "--run-id", run.name])
    assert result.exit_code == 0, result.output
    request = next((run / "control").glob("req-*.json"))
    payload = json.loads(request.read_text())
    assert payload["verb"] == verb
    assert payload["request_id"] == result.output.strip()


@pytest.mark.parametrize(("status", "verb"), [("paused", "pause"), ("running", "resume")])
def test_illegal_verb_state_rejected_without_file(tmp_path, monkeypatch, status, verb):
    root = make_template_repo(tmp_path)
    run = _seed_run(root, status)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, [verb, "--run-id", run.name])
    assert result.exit_code != 0 or "rejected" in result.output
    assert not (run / "control").exists() or not list((run / "control").glob("req-*.json"))


@pytest.mark.parametrize("status", ["completed", "failed", "killed"])
def test_control_terminal_run_rejected_readonly(tmp_path, monkeypatch, status):
    root = make_template_repo(tmp_path)
    run = _seed_run(root, status)
    before = (run / "state.db").read_bytes()
    monkeypatch.chdir(root)
    result = CliRunner().invoke(main, ["kill", "--run-id", run.name])
    assert result.exit_code == 0
    assert result.output.strip() == "rejected: run terminal"
    assert not (run / "control").exists()
    assert (run / "state.db").read_bytes() == before


def test_status_and_logs_are_readonly(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    run = _seed_run(root, "running")
    before = hashlib.sha256((run / "state.db").read_bytes()).hexdigest()
    monkeypatch.chdir(root)
    for command in ("status", "logs"):
        result = CliRunner().invoke(main, [command, "--run-id", run.name])
        assert result.exit_code == 0, result.output
    after = hashlib.sha256((run / "state.db").read_bytes()).hexdigest()
    assert after == before


@pytest.mark.timeout(30)
def test_resume_immutable_drift_exits_6(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    monkeypatch.chdir(root)
    start = CliRunner().invoke(main, ["start", "--yes"])
    assert start.exit_code == 0, start.output
    run = next((root / "runs").glob("run-*"))
    with sqlite3.connect(run / "state.db") as db:
        db.execute("UPDATE runs SET status='paused'")
    (root / "RESEARCH_SPEC.md").write_text("tampered")
    result = CliRunner().invoke(main, ["resume", "--run-id", run.name])
    assert result.exit_code == 6
    assert "RESEARCH_SPEC.md" in result.output


@pytest.mark.timeout(30)
def test_resume_clean_writes_control_request(tmp_path, monkeypatch):
    root = make_template_repo(tmp_path)
    monkeypatch.chdir(root)
    start = CliRunner().invoke(main, ["start", "--yes"])
    assert start.exit_code == 0, start.output
    run = next((root / "runs").glob("run-*"))
    with sqlite3.connect(run / "state.db") as db:
        db.execute("UPDATE runs SET status='paused'")
    result = CliRunner().invoke(main, ["resume", "--run-id", run.name])
    assert result.exit_code == 0, result.output
    request = next((run / "control").glob("req-*.json"))
    assert json.loads(request.read_text())["verb"] == "resume"
