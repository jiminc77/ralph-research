"""Schema, configuration, and immutable value-object contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

import jsonschema
import yaml

EXIT_CODES = {
    "ok": 0,
    "spec_lint": 2,
    "preflight": 3,
    "active_lock": 4,
    "user_abort": 5,
    "immutable_drift": 6,
}
CONTROL_VERB_ALLOWED_STATES = {
    "pause": {"running"},
    "resume": {"paused"},
    "stop": {"running", "paused"},
    "kill": {"ready", "running", "paused", "stopping", "finalizing"},
}
TERMINAL_RUN_STATUSES = {"completed", "failed", "killed"}


class SchemaError(Exception):
    """Raised when an external schema or configuration contract is invalid."""


class WorkerResultError(SchemaError):
    """Raised when a worker result does not conform to its JSON schema."""


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ControlRequest:
    request_id: str
    verb: str
    issued_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ControlRequest:
        return cls(**dict(data))


@dataclass(frozen=True)
class DispatchOutcome:
    task_id: str
    attempt: int
    adapter: str
    started_at: str
    finished_at: str
    process_exit: int | None
    prompt_ack_observed: bool
    agent_end_observed: bool
    test_status: str
    required_files_ok: bool
    result_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DispatchOutcome:
        return cls(**dict(data))


@dataclass(frozen=True)
class FrozenScientificTuple:
    candidate_id: str
    source_commit: str
    base_commit: str
    config_hash: str
    checkpoint_rule: str
    seed_rule: str
    claim_families: tuple[str, ...]
    success_criterion: str
    dependency_lock_sha256: str
    dataset_hash: str
    split_hashes: Mapping[str, str]
    frozen_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["claim_families"] = list(self.claim_families)
        data["split_hashes"] = dict(self.split_hashes)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FrozenScientificTuple:
        values = dict(data)
        values["claim_families"] = tuple(values["claim_families"])
        values["split_hashes"] = dict(values["split_hashes"])
        return cls(**values)


_DOTTED_PATH = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,}$")


def _validate_dotted_path(dotted_path: str) -> None:
    if not isinstance(dotted_path, str) or not _DOTTED_PATH.fullmatch(dotted_path):
        raise SchemaError(f"invalid adapter dotted path: {dotted_path!r}")


@dataclass(frozen=True)
class AdapterHandle:
    dotted_path: str

    def resolve(self) -> Any:
        module_name, attribute = self.dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, attribute)


def load_adapter(dotted_path: str) -> AdapterHandle:
    _validate_dotted_path(dotted_path)
    return AdapterHandle(dotted_path)


class Config:
    """Validated YAML configuration with reproducible lock-file output."""

    _REQUIRED_KEYS = {"schema_version", "run", "models", "paths", "security", "adapters"}

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    @classmethod
    def load(cls, path: str | Path) -> Config:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise SchemaError("configuration must be a YAML mapping")
        missing = cls._REQUIRED_KEYS - data.keys()
        if missing:
            raise SchemaError(f"configuration missing required keys: {', '.join(sorted(missing))}")
        if not isinstance(data["schema_version"], str):
            raise SchemaError("schema_version must be a string")
        adapters = data["adapters"]
        if not isinstance(adapters, dict):
            raise SchemaError("adapters must be a mapping")
        for name, dotted_path in adapters.items():
            if not isinstance(name, str):
                raise SchemaError("adapter names must be strings")
            _validate_dotted_path(dotted_path)
        return cls(data)

    def lock(self, dest_path: str | Path) -> None:
        with Path(dest_path).open("w", encoding="utf-8") as stream:
            yaml.safe_dump(self.data, stream, sort_keys=False, allow_unicode=True)


_WORKER_RESULT_VALIDATOR: jsonschema.Draft202012Validator | None = None


def _worker_result_validator() -> jsonschema.Draft202012Validator:
    global _WORKER_RESULT_VALIDATOR
    if _WORKER_RESULT_VALIDATOR is None:
        schema_path = Path(__file__).resolve().parent.parent / "schema" / "worker-result.schema.json"
        with schema_path.open(encoding="utf-8") as stream:
            schema = json.load(stream)
        _WORKER_RESULT_VALIDATOR = jsonschema.Draft202012Validator(schema)
    return _WORKER_RESULT_VALIDATOR


def validate_worker_result(result: dict[str, Any]) -> None:
    errors = sorted(_worker_result_validator().iter_errors(result), key=lambda error: list(error.absolute_path))
    if errors:
        raise WorkerResultError(errors[0].message)
