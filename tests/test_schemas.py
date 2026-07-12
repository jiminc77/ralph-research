from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest
import yaml

from ralph_core.schemas import (
    Config,
    ControlRequest,
    DispatchOutcome,
    FrozenScientificTuple,
    SchemaError,
    WorkerResultError,
    canonical_json,
    load_adapter,
    sha256_file,
    validate_worker_result,
)

ROOT = Path(__file__).resolve().parents[1]


def valid_result() -> dict:
    return {
        "schema_version": "4.1",
        "task_id": "task-1",
        "status": "completed",
        "summary": "completed",
        "experiments": [{
            "experiment_id": "exp-1",
            "purpose": "baseline",
            "status": "completed",
            "data_split": "train",
            "config_hash": "abc",
            "seeds": [11],
            "aggregate": {"score": 1.0},
            "guards": {"passed": True},
            "manifest": "runs/exp-1.json",
        }],
        "artifacts": [{"kind": "result", "path": "runs/result.json", "sha256": "a" * 64}],
        "findings": [],
        "limitations": [],
        "next_action": "none",
    }


def test_schema_copies_are_byte_identical() -> None:
    assert sha256_file(ROOT / "schema/core-v4.1-lean.sql") == sha256_file(ROOT / "spec-bundle/schema/core-v4.1-lean.sql")
    assert sha256_file(ROOT / "schema/worker-result.schema.json") == sha256_file(ROOT / "spec-bundle/schema/worker-result.schema.json")


def test_worker_result_validation() -> None:
    validate_worker_result(valid_result())
    invalid_results = []
    wrong_version = valid_result()
    wrong_version["schema_version"] = "4.0"
    invalid_results.append(wrong_version)
    missing_key = valid_result()
    del missing_key["summary"]
    invalid_results.append(missing_key)
    additional_property = valid_result()
    additional_property["unexpected"] = True
    invalid_results.append(additional_property)
    bad_sha = valid_result()
    bad_sha["artifacts"][0]["sha256"] = "bad"
    invalid_results.append(bad_sha)
    for result in invalid_results:
        with pytest.raises(WorkerResultError):
            validate_worker_result(result)


def test_value_objects_round_trip_and_are_frozen() -> None:
    request = ControlRequest("r-1", "pause", "2026-01-01T00:00:00Z")
    outcome = DispatchOutcome("t-1", 1, "provider", "start", "end", 0, True, True, "passed", True, "result.json")
    frozen = FrozenScientificTuple("c-1", "source", "base", "config", "checkpoint", "seed", ("claim",), "success", "lock", "dataset", {"train": "hash"}, "now")
    for value in (request, outcome, frozen):
        assert type(value).from_dict(value.to_dict()) == value
        with pytest.raises(FrozenInstanceError):
            value.task_id = "changed"  # type: ignore[attr-defined]


def test_canonical_json_is_key_order_independent() -> None:
    assert canonical_json({"b": 2, "a": "é"}) == canonical_json({"a": "é", "b": 2})


def test_load_adapter_is_lazy_and_validates_syntax() -> None:
    for path in ("no_dots", "1bad.mod.Cls", "a..b"):
        with pytest.raises(SchemaError):
            load_adapter(path)
    sys.modules.pop("ralph_core.adapters.agent_sdk", None)
    handle = load_adapter("ralph_core.adapters.agent_sdk.AgentSDKProvider")
    assert "ralph_core.adapters.agent_sdk" not in sys.modules
    assert load_adapter("ralph_core.schemas.Config").resolve() is Config


def test_config_load_and_lock(tmp_path: Path) -> None:
    config = Config.load(ROOT / "config.yml")
    locked = tmp_path / "config.lock.yml"
    config.lock(locked)
    assert yaml.safe_load(locked.read_text(encoding="utf-8")) == config.data
    bad = tmp_path / "bad.yml"
    bad.write_text((ROOT / "config.yml").read_text(encoding="utf-8").replace("ralph_core.adapters.gjc_rpc.GJCAdapter", "bad_path"), encoding="utf-8")
    with pytest.raises(SchemaError):
        Config.load(bad)
