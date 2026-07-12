import os
import signal
import subprocess
import sys
import time

import pytest

from ralph_core.recovery import recover
from tests.test_result_ingest import seeded


@pytest.mark.timeout(30)
def test_sigkill_midrun_recovers_interrupted_then_completed(tmp_path):
    run, store = seeded(tmp_path)
    sentinel = tmp_path / "worker-ready"
    env = {**os.environ, "RALPH_FAKE_WORKER": "tests.fakes.fake_worker.slow", "RALPH_FAKE_SENTINEL": str(sentinel)}
    started = time.monotonic()
    child = subprocess.Popen([sys.executable, "-m", "ralph_core.supervisor", str(run)], cwd=".", env=env)
    try:
        deadline = time.monotonic() + 10
        while not sentinel.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sentinel.exists()
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
    assert time.monotonic() - started < 30
    assert store.get_task("t")["status"] == "running"
    report = recover(run, store)
    assert report.interrupted == 1 and report.completed == 1
    assert store.get_task("t")["status"] == "completed"
    events = [row["event_type"] for row in store.conn.execute("SELECT event_type FROM events WHERE task_id='t' ORDER BY event_seq")]
    assert events.index("task_interrupted") < events.index("result_ingested")


def test_incomplete_result_requeues_with_attempt_bump(tmp_path):
    run, store = seeded(tmp_path)
    store.set_run_status("r", "running")
    store.set_task_status("t", "running")
    store.conn.execute("UPDATE tasks SET max_attempts=2 WHERE task_id='t'")
    store.conn.commit()
    report = recover(run, store)
    assert report.requeued == 1
    task = store.get_task("t")
    assert (task["status"], task["attempt"]) == ("queued", 1)


def test_exhausted_attempts_fail(tmp_path):
    run, store = seeded(tmp_path)
    store.set_run_status("r", "running")
    store.set_task_status("t", "running", attempt=1)
    report = recover(run, store)
    assert report.failed == 1
    assert store.get_task("t")["status"] == "failed"
