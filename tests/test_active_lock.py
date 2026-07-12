import subprocess
import sys
import time

import pytest

from ralph_core.supervisor import ActiveLockError, Supervisor
from tests.test_result_ingest import seeded


@pytest.mark.timeout(30)
def test_second_supervisor_denied(tmp_path):
    run = tmp_path / "runs" / "r"
    run.mkdir(parents=True)
    sentinel = tmp_path / "locked"
    code = (
        "from pathlib import Path; import time; from ralph_core.supervisor import Supervisor; "
        f"s=Supervisor(Path({str(run)!r})); s.acquire_lock(); Path({str(sentinel)!r}).touch(); time.sleep(60)"
    )
    child = subprocess.Popen([sys.executable, "-c", code], cwd=".")
    try:
        deadline = time.monotonic() + 10
        while not sentinel.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sentinel.exists()
        with pytest.raises(ActiveLockError):
            Supervisor(run).acquire_lock()
    finally:
        child.terminate()
        child.wait(timeout=10)


def test_same_process_second_acquire_denied(tmp_path):
    run = tmp_path / "runs" / "r"
    run.mkdir(parents=True)
    first = Supervisor(run)
    first.acquire_lock()
    with pytest.raises(ActiveLockError):
        Supervisor(run).acquire_lock()
def test_supervisor_main_exits_4_when_lock_held(tmp_path):
    run, _ = seeded(tmp_path)
    supervisor = Supervisor(run)
    supervisor.acquire_lock()

    result = subprocess.run(
        [sys.executable, "-m", "ralph_core.supervisor", str(run)],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 4
    assert "Traceback" not in result.stderr


def test_run_once_requires_lock(tmp_path):
    run = tmp_path / "runs" / "r"
    run.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="active lock must be held"):
        Supervisor(run).run_once()
