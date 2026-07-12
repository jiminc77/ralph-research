"""Recovery for interrupted local runs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schemas import DispatchOutcome
from .supervisor import Supervisor, now


@dataclass
class RecoveryReport:
    interrupted: int = 0
    completed: int = 0
    requeued: int = 0
    failed: int = 0
    worker_terminal: int = 0
    cleaned: int = 0


def recover(run_dir, store, worker_runner=None, supervisor=None) -> RecoveryReport:
    run_dir = Path(run_dir)
    run_id = run_dir.name
    report = RecoveryReport()
    owns_lock = supervisor is None
    if owns_lock:
        supervisor = Supervisor(run_dir, worker_runner)
        supervisor.store.close()
        supervisor.store = store
        supervisor.acquire_lock()

    try:
        run = store.get_run(run_id)
        was_running = run["status"] == "running"

        if was_running:
            running_tasks = store.conn.execute(
                "SELECT task_id FROM tasks WHERE run_id=? AND status='running'", (run_id,)
            ).fetchall()
            for task in running_tasks:
                store.set_task_status(task["task_id"], "interrupted")
                store.insert_event(
                    {
                        "run_id": run_id,
                        "task_id": task["task_id"],
                        "event_type": "task_interrupted",
                        "payload_json": "{}",
                        "created_at": now(),
                    }
                )

        interrupted_tasks = store.conn.execute(
            "SELECT * FROM tasks WHERE run_id=? AND status='interrupted'", (run_id,)
        ).fetchall()
        for task in interrupted_tasks:
            report.interrupted += 1
            task_dir = run_dir / "tasks" / task["task_id"]
            outcome_path = task_dir / f"attempt-{task['attempt']}.outcome.json"
            if outcome_path.is_file():
                try:
                    outcome = DispatchOutcome.from_dict(json.loads(outcome_path.read_text()))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    outcome = None
                if outcome and (task_dir / (outcome.result_path or "result.json")).is_file():
                    supervisor.ingest_result(task["task_id"], task["attempt"], outcome)

            current = store.get_task(task["task_id"])
            if current["status"] == "completed":
                report.completed += 1
            elif current["status"] in {"failed", "blocked"}:
                report.worker_terminal += 1
            elif current["status"] == "interrupted":
                if current["attempt"] + 1 <= current["max_attempts"]:
                    store.set_task_status(
                        task["task_id"], "queued", attempt=current["attempt"] + 1
                    )
                    report.requeued += 1
                else:
                    store.set_task_status(task["task_id"], "failed")
                    report.failed += 1

        for path in (run_dir / "tasks").glob("**/*.tmp"):
            path.unlink()
            report.cleaned += 1

        if was_running:
            store.set_run_status(run_id, "running")
        return report
    finally:
        if owns_lock:
            supervisor.lock_file.close()
            supervisor.lock_file = None
