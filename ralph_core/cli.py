"""Click command surface for Ralph."""
from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
from pathlib import Path

import click

from .preflight import Preflight
from .resolver import ModelResolver
from .schemas import (
    CONTROL_VERB_ALLOWED_STATES,
    EXIT_CODES,
    TERMINAL_RUN_STATUSES,
    Config,
    canonical_json,
    sha256_file,
)
from .spec_lint import spec_lint


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _run_root(root, cfg):
    return root / cfg.data["paths"].get("runs_dir", "runs")


def _runs(root, cfg):
    base = _run_root(root, cfg)
    return sorted((path for path in base.glob("run-*") if path.is_dir()), key=lambda path: path.name)


def _run(root, cfg, run_id):
    if run_id:
        return _run_root(root, cfg) / run_id
    runs = _runs(root, cfg)
    return runs[-1] if runs else None


def _catalog(root, config):
    return Preflight(root, config).seam("catalog")


def _readonly_db(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _control(root, cfg, verb, run_id):
    run = _run(root, cfg, run_id)
    if not run:
        raise click.ClickException("no run found")
    with _readonly_db(run / "state.db") as db:
        status = db.execute(
            "SELECT status FROM runs WHERE run_id=?", (run.name,)
        ).fetchone()[0]
    if status in TERMINAL_RUN_STATUSES:
        click.echo("rejected: run terminal")
        return
    if status not in CONTROL_VERB_ALLOWED_STATES[verb]:
        raise click.ClickException(f"rejected: {verb} not allowed in {status}")
    request_id = secrets.token_hex(13).upper()
    control = run / "control"
    control.mkdir(exist_ok=True)
    (control / "processed").mkdir(exist_ok=True)
    target = control / f"req-{request_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        canonical_json(
            {"request_id": request_id, "verb": verb, "issued_at": _now()}
        ),
        encoding="utf-8",
    )
    os.replace(temporary, target)
    click.echo(request_id)


@click.group()
def main():
    pass


@main.command()
@click.option("--yes", is_flag=True)
@click.option("--config", type=click.Path(path_type=Path), default=Path("config.yml"))
@click.option("--name", default=None)
def start(yes, config, name):
    root = config.resolve().parent
    cfg = Config.load(config)
    findings = spec_lint(root, cfg)
    if findings:
        for finding in findings:
            click.echo(str(finding), err=True)
        raise click.exceptions.Exit(EXIT_CODES["spec_lint"])
    report = Preflight(root, cfg).run()
    if report.first_failure:
        click.echo(f"preflight failed: {report.first_failure}", err=True)
        raise click.exceptions.Exit(EXIT_CODES["preflight"])
    try:
        models = ModelResolver(cfg.data["models"], _catalog(root, cfg)).resolve_all()
    except Exception as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(EXIT_CODES["preflight"])
    cfg.lock(root / "config.lock.yml")
    run_id = (
        f"run-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        f"-{secrets.token_hex(5).upper()}"
    )
    run = _run_root(root, cfg) / run_id
    for child in ("control/processed", "tasks", "artifacts", "logs"):
        (run / child).mkdir(parents=True, exist_ok=True)
    schema = Path(__file__).resolve().parent.parent / "schema" / "core-v4.1-lean.sql"
    conn = sqlite3.connect(run / "state.db")
    conn.executescript(schema.read_text())
    conn.execute(
        "INSERT INTO runs (run_id,name,status,config_json,cost_cap_usd,created_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            run_id,
            name or cfg.data["run"]["name"],
            "ready",
            canonical_json(cfg.data),
            cfg.data["run"]["defaults"]["budget"]["cost_cap_usd"],
            _now(),
        ),
    )
    conn.commit()
    conn.close()
    inputs = [
        "config.lock.yml",
        "RESEARCH_SPEC.md",
        "DECISION_POLICY.md",
        "ONE_LINER.md",
        "data/data_manifest.lock.json",
        "statistics/statistical_protocol.lock.json",
        "venue/venue_profile.lock.yml",
        "figures/paperfigure/source.lock.json",
    ]
    immutable = {
        relative: sha256_file(root / relative)
        for relative in inputs
        if (root / relative).is_file()
    }
    tool_versions = {}
    for name, command in (
        ("python", ["python", "--version"]),
        ("git", ["git", "--version"]),
    ):
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        tool_versions[name] = (completed.stdout or completed.stderr).strip()
    runtime = {
        "run_id": run_id,
        "created_at": _now(),
        "resolved_models": models,
        "schema_sha256": {
            "core-v4.1-lean.sql": sha256_file(schema),
            "worker-result.schema.json": sha256_file(schema.parent / "worker-result.schema.json"),
        },
        "immutable_inputs": immutable,
        "tool_versions": tool_versions,
        "dependency_lock_sha256": sha256_file(root / "uv.lock"),
        "gjc_protocol": cfg.data.get("gjc_protocol"),
    }
    (run / "runtime.lock.json").write_text(
        json.dumps(runtime, sort_keys=True), encoding="utf-8"
    )
    click.echo(f"ready: {run_id}")
    if not yes:
        answer = click.prompt("Press Enter to continue (n to abort)", default="", show_default=False)
        if answer.strip().lower() in {"n", "no"}:
            shutil.rmtree(run)
            raise click.exceptions.Exit(EXIT_CODES["user_abort"])


@main.command()
@click.option("--config", type=click.Path(path_type=Path), default=Path("config.yml"))
@click.option("--run-id", default=None)
def resume(config, run_id):
    root = config.resolve().parent
    cfg = Config.load(config)
    run = _run(root, cfg, run_id)
    if not run:
        raise click.ClickException("no run found")
    runtime = json.loads((run / "runtime.lock.json").read_text())
    for relative, digest in runtime["immutable_inputs"].items():
        if not (root / relative).is_file() or sha256_file(root / relative) != digest:
            click.echo(f"immutable drift: {relative}", err=True)
            raise click.exceptions.Exit(EXIT_CODES["immutable_drift"])
    _control(root, cfg, "resume", run_id)


for _verb in ("pause", "stop", "kill"):
    def command(run_id, config, verb=_verb):
        cfg = Config.load(config)
        _control(config.resolve().parent, cfg, verb, run_id)

    command.__name__ = _verb
    main.command(name=_verb)(
        click.option("--config", type=click.Path(path_type=Path), default=Path("config.yml"))(
            click.option("--run-id", default=None)(command)
        )
    )


@main.command()
@click.option("--config", type=click.Path(path_type=Path), default=Path("config.yml"))
@click.option("--run-id", default=None)
def status(config, run_id):
    cfg = Config.load(config)
    run = _run(config.resolve().parent, cfg, run_id)
    if not run:
        raise click.ClickException("no run found")
    with _readonly_db(run / "state.db") as db:
        cursor = db.execute("SELECT * FROM runs LIMIT 1")
        click.echo(dict(zip([column[0] for column in cursor.description], cursor.fetchone())))


@main.command()
@click.option("--config", type=click.Path(path_type=Path), default=Path("config.yml"))
@click.option("--run-id", default=None)
@click.option("--task", default=None)
def logs(config, run_id, task):
    cfg = Config.load(config)
    run = _run(config.resolve().parent, cfg, run_id)
    if not run:
        raise click.ClickException("no run found")
    sql = "SELECT event_type,payload_json,created_at FROM events"
    if task:
        sql += " WHERE task_id=?"
    sql += " ORDER BY event_seq DESC LIMIT 20"
    with _readonly_db(run / "state.db") as db:
        for row in db.execute(sql, (task,) if task else ()):
            click.echo(" | ".join(str(value) for value in row))
if __name__ == "__main__":
    main()
