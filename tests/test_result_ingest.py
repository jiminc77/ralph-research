from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from dataclasses import replace

import pytest

from ralph_core.schemas import sha256_file
from ralph_core.state import IngestConflictError, StateStore
from ralph_core.supervisor import Supervisor
from tests.fakes.fake_worker import corrupt_artifact_hash, exit0_without_result, valid


def seeded(tmp_path, task_ids=("t",)):
    run = tmp_path / "runs" / "r"
    for task_id in task_ids:
        (run / "tasks" / task_id).mkdir(parents=True, exist_ok=True)
    store = StateStore(run / "state.db")
    store.apply_schema("schema/core-v4.1-lean.sql")
    timestamp = datetime.now(timezone.utc).isoformat()
    store.insert_run({"run_id": "r", "name": "r", "status": "ready", "config_json": "{}", "cost_cap_usd": 1, "created_at": timestamp})
    for task_id in task_ids:
        store.insert_task({"task_id": task_id, "run_id": "r", "stage": "S0", "role": "x", "status": "queued", "created_at": timestamp})
    return run, store


def events(store, task_id):
    return [row["event_type"] for row in store.conn.execute("SELECT event_type FROM events WHERE task_id=?", (task_id,))]


def test_concurrent_ingest_integrity(tmp_path):
    run, store = seeded(tmp_path, ("one", "two"))
    for task_id in ("one", "two"):
        task = store.get_task(task_id)
        outcome = valid(task, run / "tasks" / task_id)
        artifact = run / "tasks" / task_id / "artifact.txt"
        unique_artifact = artifact.with_name(f"{task_id}.txt")
        artifact.rename(unique_artifact)
        result = json.loads((run / "tasks" / task_id / "result.json").read_text())
        result["artifacts"][0]["path"] = unique_artifact.name
        result["artifacts"][0]["sha256"] = sha256_file(unique_artifact)
        result["experiments"] = [{"experiment_id": f"e-{task_id}", "purpose": "baseline", "status": "completed", "data_split": "train", "config_hash": "cfg", "seeds": [1], "aggregate": {"primary": 1.0}, "guards": {}, "manifest": "m.json"}]
        (run / "tasks" / task_id / "result.json").write_text(json.dumps(result))
        (run / "tasks" / task_id / "outcome.json").write_text(json.dumps(outcome.to_dict()))

    def ingest(task_id):
        local = Supervisor(run)
        outcome = local.worker_runner
        from ralph_core.schemas import DispatchOutcome
        return local.ingest_result(task_id, 0, DispatchOutcome.from_dict(json.loads((run / "tasks" / task_id / "outcome.json").read_text())))

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(ingest, ("one", "two")))
    assert [store.get_task(task_id)["status"] for task_id in ("one", "two")] == ["completed", "completed"]
    assert store.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert store.conn.execute("SELECT count(*) FROM experiments").fetchone()[0] == 2
    assert store.conn.execute("SELECT count(*) FROM metrics").fetchone()[0] == 2


def test_exit0_without_result_not_completed(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    assert not Supervisor(run).ingest_result("t", 0, exit0_without_result(task, run / "tasks" / "t"))
    assert store.get_task("t")["status"] == "failed"
    assert store.get_task("t")["error_code"] == "exit0_without_result"
    assert "ingest_failed" in events(store, "t")


def test_duplicate_ingest_noop_and_conflict_rejected(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    outcome = valid(task, run / "tasks" / "t")
    supervisor = Supervisor(run)
    assert supervisor.ingest_result("t", 0, outcome)
    assert supervisor.ingest_result("t", 0, outcome)
    assert store.conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 1
    path = run / "tasks" / "t" / "result.json"
    data = json.loads(path.read_text())
    data["summary"] = "different"
    path.write_text(json.dumps(data))
    with pytest.raises(IngestConflictError):
        supervisor.ingest_result("t", 0, outcome)
    assert store.get_task("t")["status"] == "blocked"
    assert "ingest_conflict" in events(store, "t")


def test_stale_attempt_rejected(tmp_path):
    run, store = seeded(tmp_path)
    store.set_task_status("t", "queued", attempt=1)
    assert not Supervisor(run).ingest_result("t", 0, valid(store.get_task("t"), run / "tasks" / "t"))
    assert "ingest_rejected" in events(store, "t")


def test_artifact_hash_mismatch_not_completed(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    assert not Supervisor(run).ingest_result("t", 0, corrupt_artifact_hash(task, run / "tasks" / "t"))
    assert store.get_task("t")["status"] != "completed"
    assert "ingest_failed" in events(store, "t")


def test_artifact_path_traversal_rejected(tmp_path):
    run, store = seeded(tmp_path)
    task_dir = run / "tasks" / "t"
    outcome = valid(store.get_task("t"), task_dir)
    (run / "tasks" / "escape.txt").write_text("escape")
    result = {"schema_version": "4.1", "task_id": "t", "status": "completed", "summary": "ok", "experiments": [], "artifacts": [{"kind": "output", "path": "../escape.txt", "sha256": sha256_file(run / "tasks" / "escape.txt")}], "findings": [], "limitations": [], "next_action": "none"}
    (task_dir / "result.json").write_text(json.dumps(result))
    assert not Supervisor(run).ingest_result("t", 0, outcome)
    assert store.conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 0
    assert "ingest_failed" in events(store, "t")


def test_experiments_and_metrics_recorded(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    outcome = valid(task, run / "tasks" / "t")
    path = run / "tasks" / "t" / "result.json"
    result = json.loads(path.read_text())
    result["experiments"] = [{"experiment_id": "experiment-1", "purpose": "baseline", "status": "completed", "data_split": "train", "config_hash": "config", "seeds": [1], "aggregate": {"primary": 0.72, "latency": 1.2}, "guards": {}, "manifest": "manifest.json"}]
    path.write_text(json.dumps(result))
    assert Supervisor(run).ingest_result("t", 0, outcome)
    experiment = store.conn.execute("SELECT * FROM experiments WHERE experiment_id='experiment-1'").fetchone()
    assert (experiment["purpose"], experiment["data_split"]) == ("baseline", "train")
    metrics = {row["name"]: row for row in store.conn.execute("SELECT * FROM metrics")}
    assert metrics["primary"]["is_primary"] == 1 and metrics["primary"]["value"] == 0.72
    assert metrics["latency"]["is_primary"] == 0 and metrics["latency"]["value"] == 1.2


def test_failed_status_result_marks_task_failed(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    outcome = valid(task, run / "tasks" / "t")
    path = run / "tasks" / "t" / "result.json"
    result = json.loads(path.read_text())
    result["status"] = "failed"
    path.write_text(json.dumps(result))

    assert not Supervisor(run).ingest_result("t", 0, outcome)
    task = store.get_task("t")
    assert (task["status"], task["error_code"]) == ("failed", "worker_reported_failure")
    assert "worker_reported_failure" in events(store, "t")
    assert store.conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 0
    assert store.get_task("t")["result_json"] is None


def test_blocked_status_result_marks_task_blocked(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    outcome = valid(task, run / "tasks" / "t")
    path = run / "tasks" / "t" / "result.json"
    result = json.loads(path.read_text())
    result["status"] = "blocked"
    path.write_text(json.dumps(result))

    assert not Supervisor(run).ingest_result("t", 0, outcome)
    assert store.get_task("t")["status"] == "blocked"
    assert "worker_reported_blocked" in events(store, "t")
    assert store.conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 0
    assert store.get_task("t")["result_json"] is None


@pytest.mark.parametrize(
    "outcome_change",
    [
        lambda outcome: replace(outcome, task_id="other"),
        lambda outcome: replace(outcome, attempt=1),
    ],
)
def test_outcome_task_or_attempt_mismatch_rejected(tmp_path, outcome_change):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    outcome = outcome_change(valid(task, run / "tasks" / "t"))

    assert not Supervisor(run).ingest_result("t", 0, outcome)
    assert store.get_task("t")["status"] != "completed"
    assert "ingest_failed" in events(store, "t")


def test_no_agent_end_not_completed(tmp_path):
    run, store = seeded(tmp_path)
    task = store.get_task("t")
    outcome = replace(
        valid(task, run / "tasks" / "t"),
        prompt_ack_observed=True,
        agent_end_observed=False,
    )

    assert not Supervisor(run).ingest_result("t", 0, outcome)
    assert store.get_task("t")["status"] != "completed"
    assert "ingest_failed" in events(store, "t")
