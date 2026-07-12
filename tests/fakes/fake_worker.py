from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from ralph_core.schemas import DispatchOutcome, sha256_file


def _out(task, exit=0, required=True):
    timestamp = datetime.now(timezone.utc).isoformat()
    return DispatchOutcome(
        task["task_id"], task["attempt"], "fake", timestamp, timestamp, exit,
        True, True, "ok", required, "result.json",
    )


def valid(task, task_dir):
    task_dir = Path(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "artifact.txt").write_text("artifact")
    result = {
        "schema_version": "4.1",
        "task_id": task["task_id"],
        "status": "completed",
        "summary": "ok",
        "experiments": [],
        "artifacts": [{"kind": "output", "path": "artifact.txt", "sha256": sha256_file(task_dir / "artifact.txt")}],
        "findings": [],
        "limitations": [],
        "next_action": "none",
    }
    (task_dir / "result.json").write_text(json.dumps(result))
    return _out(task)


def exit0_without_result(task, task_dir):
    Path(task_dir).mkdir(parents=True, exist_ok=True)
    return _out(task)


def corrupt_artifact_hash(task, task_dir):
    outcome = valid(task, task_dir)
    (Path(task_dir) / "artifact.txt").write_text("corrupt")
    return outcome


def conflicting_replay(task, task_dir):
    outcome = valid(task, task_dir)
    path = Path(task_dir) / "result.json"
    data = json.loads(path.read_text())
    data["summary"] = "different"
    path.write_text(json.dumps(data))
    return outcome


def slow(task, task_dir):
    outcome = valid(task, task_dir)
    task_dir = Path(task_dir)
    (task_dir / f"attempt-{task['attempt']}.outcome.json").write_text(json.dumps(outcome.to_dict()))
    sentinel = os.environ.get("RALPH_FAKE_SENTINEL")
    if sentinel:
        Path(sentinel).touch()
    time.sleep(60)
    return outcome
