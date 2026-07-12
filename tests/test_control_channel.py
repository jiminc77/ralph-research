import json
from datetime import datetime, timezone

import pytest

from ralph_core.schemas import CONTROL_VERB_ALLOWED_STATES
from ralph_core.state import StateStore
from ralph_core.supervisor import Supervisor


STATUSES = ("ready", "running", "paused", "stopping", "finalizing", "completed", "failed", "killed")
TRANSITIONS = {"pause": "paused", "resume": "running", "stop": "stopping", "kill": "killed"}


def seeded(tmp_path, status="running"):
    run = tmp_path / "runs" / "r"
    (run / "control").mkdir(parents=True)
    store = StateStore(run / "state.db")
    store.apply_schema("schema/core-v4.1-lean.sql")
    store.insert_run({"run_id": "r", "name": "r", "status": status, "config_json": "{}", "cost_cap_usd": 1, "created_at": datetime.now(timezone.utc).isoformat()})
    return run, store


@pytest.mark.parametrize("verb", sorted(CONTROL_VERB_ALLOWED_STATES))
@pytest.mark.parametrize("status", STATUSES)
def test_verb_state_matrix(tmp_path, verb, status):
    run, store = seeded(tmp_path, status)
    path = run / "control" / "request.json"
    path.write_text(json.dumps({"request_id": f"{verb}-{status}", "verb": verb, "issued_at": "now"}))
    Supervisor(run).poll_control()
    accepted = status in CONTROL_VERB_ALLOWED_STATES[verb]
    assert store.get_run("r")["status"] == (TRANSITIONS[verb] if accepted else status)
    event = store.conn.execute("SELECT payload_json FROM events WHERE event_type='control_ack'").fetchone()
    assert json.loads(event["payload_json"])["verdict"] == ("accepted" if accepted else "rejected")
    assert (run / "control" / "processed" / "request.json").exists()


def test_duplicate_request_id_idempotent(tmp_path):
    run, store = seeded(tmp_path)
    control = run / "control"
    (control / "first.json").write_text(json.dumps({"request_id": "same", "verb": "pause", "issued_at": "now"}))
    Supervisor(run).poll_control()
    (control / "second.json").write_text(json.dumps({"request_id": "same", "verb": "resume", "issued_at": "now"}))
    Supervisor(run).poll_control()
    assert store.get_run("r")["status"] == "paused"
    acks = [json.loads(row["payload_json"]) for row in store.conn.execute("SELECT payload_json FROM events WHERE event_type='control_ack' ORDER BY event_seq")]
    assert len(acks) == 2 and acks[1]["duplicate"] and acks[1]["verdict"] == "rejected"


def test_request_on_terminal_run_rejected_with_event(tmp_path):
    run, store = seeded(tmp_path, "completed")
    (run / "control" / "terminal.json").write_text(json.dumps({"request_id": "terminal", "verb": "kill", "issued_at": "now"}))
    Supervisor(run).poll_control()
    assert store.get_run("r")["status"] == "completed"
    event = store.conn.execute("SELECT payload_json FROM events WHERE event_type='control_ack'").fetchone()
    assert json.loads(event["payload_json"])["verdict"] == "rejected"
