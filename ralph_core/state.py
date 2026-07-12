"""SQLite state access with deterministic duplicate detection."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .schemas import canonical_json


class IngestConflictError(Exception):
    pass


class StateStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._pragmas()

    def _pragmas(self) -> None:
        for sql in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA busy_timeout=5000",
        ):
            self.conn.execute(sql)

    def apply_schema(self, sql_path: str | Path) -> None:
        self.conn.executescript(Path(sql_path).read_text())
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _insert(self, table: str, row: dict[str, Any]) -> None:
        columns = list(row)
        self.conn.execute(
            f"INSERT INTO {table} ({','.join(columns)}) "
            f"VALUES ({','.join('?' for _ in columns)})",
            [row[column] for column in columns],
        )
        self.conn.commit()

    def insert_run(self, row: dict[str, Any]) -> None:
        self._insert("runs", row)

    def get_run(self, run_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()

    def set_run_status(self, run_id: str, status: str) -> None:
        self.conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
        self.conn.commit()

    def insert_task(self, row: dict[str, Any]) -> None:
        self._insert("tasks", row)

    def get_task(self, task_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()

    def set_task_status(self, task_id: str, status: str, **fields: Any) -> None:
        fields = {"status": status, **fields}
        assignments = ",".join(f"{name}=?" for name in fields)
        self.conn.execute(
            f"UPDATE tasks SET {assignments} WHERE task_id=?",
            (*fields.values(), task_id),
        )
        self.conn.commit()

    def insert_event(self, row: dict[str, Any]) -> None:
        self._insert("events", row)

    def insert_artifact(self, row: dict[str, Any]) -> None:
        self._insert("artifacts", row)

    def insert_experiment(self, row: dict[str, Any]) -> None:
        self._insert("experiments", row)

    def insert_metric(self, row: dict[str, Any]) -> None:
        self._insert("metrics", row)

    def insert_or_verify(self, table: str, key_col: str, key: str, row: dict[str, Any]) -> str:
        columns = list(row)
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                f"INSERT INTO {table} ({','.join(columns)}) "
                f"VALUES ({','.join('?' for _ in columns)})",
                [row[column] for column in columns],
            )
            self.conn.commit()
            return "inserted"
        except sqlite3.IntegrityError:
            self.conn.rollback()
            old = self.conn.execute(
                f"SELECT {','.join(columns)} FROM {table} WHERE {key_col}=?", (key,)
            ).fetchone()
            if old is not None and canonical_json(row) == canonical_json(dict(old)):
                return "duplicate"
            raise IngestConflictError(f"conflicting {table} {key}")


class ReadOnlyState:
    def __init__(self, db_path: str | Path):
        self.conn = sqlite3.connect(f"file:{Path(db_path).absolute()}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()


def wal_probe(directory: str | Path) -> bool:
    path = Path(directory) / ".wal-probe.sqlite"
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            candidate.unlink(missing_ok=True)
