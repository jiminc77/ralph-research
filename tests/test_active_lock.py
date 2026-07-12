import subprocess
import sys
import time

import pytest

from ralph_core.supervisor import ActiveLockError, Supervisor


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
