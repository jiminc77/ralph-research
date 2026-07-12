"""Local run supervisor and durable result ingestion."""
from __future__ import annotations

import fcntl
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import (
    CONTROL_VERB_ALLOWED_STATES,
    DispatchOutcome,
    EXIT_CODES,
    WorkerResultError,
    canonical_json,
    sha256_file,
    validate_worker_result,
)
from .state import IngestConflictError, StateStore


class ActiveLockError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Supervisor:
    def __init__(self, run_dir, worker_runner=None):
        self.run_dir = Path(run_dir)
        self.run_id = self.run_dir.name
        self.store = StateStore(self.run_dir / "state.db")
        self.worker_runner = worker_runner
        self.lock_file = None

    def event(self, event_type, payload=None, task_id=None) -> None:
        self.store.insert_event(
            {
                "run_id": self.run_id,
                "task_id": task_id,
                "event_type": event_type,
                "payload_json": canonical_json(payload or {}),
                "created_at": now(),
            }
        )

    def acquire_lock(self) -> None:
        lock_path = self.run_dir.parent / ".active.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise ActiveLockError(str(lock_path))
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self.lock_file = handle

    def assume_lock_held(self) -> None:
        """Record the caller's explicit assertion that it owns the active lock."""
        self.lock_file = True

    def _require_lock(self) -> None:
        if self.lock_file is None:
            raise RuntimeError("active lock must be held")


    def start(self) -> None:
        self._require_lock()
        run = self.store.get_run(self.run_id)
        if run["status"] != "ready":
            raise RuntimeError("run is not ready")
        self.store.set_run_status(self.run_id, "running")
        self.event("run_started")

    def poll_control(self) -> None:
        control = self.run_dir / "control"
        processed = control / "processed"
        processed.mkdir(parents=True, exist_ok=True)
        transitions = {"pause": "paused", "resume": "running", "stop": "stopping", "kill": "killed"}
        for path in sorted(control.glob("*.json")):
            try:
                request = json.loads(path.read_text())
                verb = request["verb"]
                request_id = request["request_id"]
            except Exception:
                request = {}
                verb = ""
                request_id = None
            prior = None
            if request_id:
                prior = self.store.conn.execute(
                    "SELECT 1 FROM events WHERE run_id=? AND event_type='control_ack' "
                    "AND payload_json LIKE ?",
                    (self.run_id, f'%"request_id":"{request_id}"%'),
                ).fetchone()
            run = self.store.get_run(self.run_id)
            accepted = (
                not prior
                and verb in CONTROL_VERB_ALLOWED_STATES
                and run["status"] in CONTROL_VERB_ALLOWED_STATES.get(verb, set())
            )
            if accepted:
                self.store.set_run_status(self.run_id, transitions[verb])
            self.event(
                "control_ack",
                {
                    "request_id": request_id,
                    "verb": verb,
                    "verdict": "accepted" if accepted else "rejected",
                    "duplicate": bool(prior),
                },
            )
            path.rename(processed / path.name)

    def ingest_result(self, task_id, attempt, outcome) -> bool:
        task = self.store.get_task(task_id)
        if attempt != task["attempt"]:
            self.event("ingest_rejected", {"reason": "attempt_mismatch"}, task_id)
            return False
        if outcome.task_id != task_id:
            self.event("ingest_failed", {"reason": "outcome task mismatch"}, task_id)
            return False
        if outcome.attempt != attempt:
            self.event("ingest_failed", {"reason": "outcome attempt mismatch"}, task_id)
            return False
        if not outcome.agent_end_observed:
            self.event("ingest_failed", {"reason": "agent end not observed"}, task_id)
            return False
        task_dir = self.run_dir / "tasks" / task_id
        result_file = (task_dir / (outcome.result_path or "result.json")).resolve()
        try:
            result_file.relative_to(task_dir.resolve())
        except ValueError:
            self.event("ingest_failed", {"reason": "result path escapes task"}, task_id)
            return False
        if outcome.process_exit == 0 and not result_file.exists():
            self.store.set_task_status(task_id, "failed", error_code="exit0_without_result")
            self.event("ingest_failed", {"reason": "exit0_without_result"}, task_id)
            return False
        if not result_file.exists():
            self.event("ingest_failed", {"reason": "missing_result"}, task_id)
            return False
        try:
            result = json.loads(result_file.read_text())
            validate_worker_result(result)
            if result["task_id"] != task_id:
                raise WorkerResultError("task mismatch")
            if result["status"] == "failed":
                self.store.set_task_status(
                    task_id, "failed", error_code="worker_reported_failure"
                )
                self.event("worker_reported_failure", {}, task_id)
                return False
            if result["status"] == "blocked":
                self.store.set_task_status(task_id, "blocked")
                self.event("worker_reported_blocked", {}, task_id)
                return False
            artifacts = []
            for artifact in result["artifacts"]:
                file_path = (task_dir / artifact["path"]).resolve()
                file_path.relative_to(task_dir.resolve())
                if not file_path.is_file() or sha256_file(file_path).lower() != artifact["sha256"].lower():
                    raise WorkerResultError("artifact hash mismatch")
                artifacts.append((artifact, file_path))
            if outcome.process_exit != 0 or not outcome.required_files_ok:
                raise WorkerResultError("unsuccessful dispatch")
        except Exception as exc:
            self.event("ingest_failed", {"reason": str(exc)}, task_id)
            return False

        try:
            self.store.conn.execute("BEGIN IMMEDIATE")
            existing = self.store.get_task(task_id)
            payload = canonical_json(result)
            if existing["result_json"] is not None:
                if existing["result_json"] != payload:
                    raise IngestConflictError(task_id)
                self.store.conn.rollback()
                return True
            self.store.conn.execute(
                "UPDATE tasks SET status='completed',result_json=?,finished_at=? WHERE task_id=?",
                (payload, now(), task_id),
            )
            for artifact, file_path in artifacts:
                self.store.conn.execute(
                    "INSERT INTO artifacts "
                    "(artifact_id,run_id,task_id,kind,relpath,sha256,size_bytes,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()), self.run_id, task_id, artifact["kind"], artifact["path"],
                        artifact["sha256"], file_path.stat().st_size, now(),
                    ),
                )
            for experiment in result["experiments"]:
                experiment_id = experiment["experiment_id"]
                self.store.conn.execute(
                    "INSERT INTO experiments "
                    "(experiment_id,run_id,task_id,purpose,status,data_split,source_commit,config_hash,"
                    "aggregate_json,guards_json,seeds_json,manifest_relpath,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        experiment_id, self.run_id, task_id, experiment["purpose"], experiment["status"],
                        experiment["data_split"], result.get("source_commit"), experiment["config_hash"],
                        canonical_json(experiment["aggregate"]), canonical_json(experiment["guards"]),
                        canonical_json(experiment["seeds"]), experiment["manifest"], now(),
                    ),
                )
                for name, value in experiment["aggregate"].items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        self.store.conn.execute(
                            "INSERT INTO metrics "
                            "(metric_id,run_id,experiment_id,name,split,value,is_primary,created_at) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (
                                str(uuid4()), self.run_id, experiment_id, name,
                                experiment["data_split"], value, int(name == "primary"), now(),
                            ),
                        )
            self.store.conn.commit()
        except IngestConflictError:
            self.store.conn.rollback()
            self.store.set_task_status(task_id, "blocked", error_code="ingest_conflict")
            self.event("ingest_conflict", {}, task_id)
            raise
        except Exception:
            self.store.conn.rollback()
            raise
        (task_dir / f".ingested-attempt-{attempt}").touch()
        self.event("result_ingested", {"attempt": attempt}, task_id)
        return True

    def run_once(self) -> None:
        self._require_lock()
        self.start()
        tasks = self.store.conn.execute(
            "SELECT * FROM tasks WHERE run_id=? AND status='queued'", (self.run_id,)
        ).fetchall()
        for task in tasks:
            task_id = task["task_id"]
            task_dir = self.run_dir / "tasks" / task_id
            self.store.set_task_status(task_id, "running")
            outcome = self.worker_runner(task, task_dir) if self.worker_runner else None
            if outcome:
                (task_dir / f"attempt-{task['attempt']}.outcome.json").write_text(
                    canonical_json(outcome.to_dict())
                )
                self.ingest_result(task_id, task["attempt"], outcome)
            self.poll_control()


def main() -> None:
    run_dir = Path(sys.argv[1])
    worker = None
    dotted = os.getenv("RALPH_FAKE_WORKER")
    if dotted:
        module, name = dotted.rsplit(".", 1)
        worker = getattr(importlib.import_module(module), name)
    supervisor = Supervisor(run_dir, worker)
    try:
        supervisor.acquire_lock()
        supervisor.run_once()
    except ActiveLockError:
        print("another supervisor holds the active lock", file=sys.stderr)
        sys.exit(EXIT_CODES["active_lock"])


if __name__ == "__main__":
    main()
