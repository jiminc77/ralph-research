"""Phase-1 research-spec linting."""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LintFinding:
    rule: int
    detail: str

    def __str__(self) -> str:
        return f"rule {self.rule}: {self.detail}"


def _data(config: Any) -> dict[str, Any]:
    return config.data if hasattr(config, "data") else config


def _yaml_spec(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("```yaml", 1)
    if len(parts) != 2 or "```" not in parts[1]:
        raise ValueError("first fenced yaml block missing")
    value = yaml.safe_load(parts[1].split("```", 1)[0])
    if not isinstance(value, dict):
        raise ValueError("spec YAML must be a mapping")
    return value


def _nested(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _venue_check(root: Path, config: dict[str, Any]) -> list[str]:
    dotted = config.get("adapters", {}).get("venue_compile")
    if dotted:
        module, name = dotted.rsplit(".", 1)
        checker = getattr(importlib.import_module(module), name)
        checker = checker() if isinstance(checker, type) else checker
        result = checker(root / config["paths"]["venue_profile"])
        return list(result) if isinstance(result, (list, tuple)) else ([] if result else ["venue compile failed"])
    from venue.check import check_profile

    return check_profile(root / config["paths"]["venue_profile"])


def spec_lint(repo_root: str | Path, config: Any) -> list[LintFinding]:
    root = Path(repo_root)
    cfg = _data(config)
    findings: list[LintFinding] = []
    try:
        spec = _yaml_spec(root / "RESEARCH_SPEC.md")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [LintFinding(1, f"RESEARCH_SPEC.md invalid: {exc}")]
    metrics = spec.get("metrics", {})
    if not _nested(spec, "baseline", "command"):
        findings.append(LintFinding(1, "baseline.command required"))
    if not metrics.get("primary") or not metrics.get("direction"):
        findings.append(LintFinding(2, "metrics.primary and direction required"))
    if metrics.get("minimum_effect") is None or not metrics.get("guards"):
        findings.append(LintFinding(3, "minimum_effect and guard threshold required"))
    try:
        manifest = json.loads((root / cfg["paths"]["data_manifest"]).read_text())
    except (OSError, ValueError, KeyError):
        manifest = {}
    splits = manifest.get("splits", {})
    if not {"search_dev", "hidden_confirmation"} <= set(splits):
        findings.append(LintFinding(4, "search_dev and hidden_confirmation splits required"))
    try:
        protocol = json.loads((root / cfg["paths"]["statistical_protocol"]).read_text())
    except (OSError, ValueError, KeyError):
        protocol = {}
    if not all(protocol.get(key) for key in ("seeds", "aggregate", "selection_rule")):
        findings.append(LintFinding(5, "protocol seeds, aggregate, selection_rule required"))
    candidates = spec.get("candidates", {})
    exception = candidates.get("exception") or candidates.get("exception_flag")
    valid_range = (
        isinstance(candidates.get("min"), int)
        and candidates["min"] >= 2
        and isinstance(candidates.get("max"), int)
        and candidates["max"] <= 4
    )
    if not exception and not valid_range:
        findings.append(LintFinding(6, "candidates must be 2..4 or explicitly excepted"))
    budget = _nested(cfg, "run", "defaults", "budget") or {}
    if not all(key in budget for key in ("wall_clock_hours", "cost_cap_usd", "gpu_hour_cap")):
        findings.append(LintFinding(7, "wall-clock, cost, and compute caps required"))
    try:
        policy = (root / "DECISION_POLICY.md").read_text(encoding="utf-8").lower()
    except OSError:
        policy = ""
    if "default" not in policy and "lowest-risk" not in policy:
        findings.append(LintFinding(8, "default policy for unresolved ASKs required"))
    dataset = manifest.get("dataset", {})
    if not (dataset.get("access") or dataset.get("access_status")) or not (
        dataset.get("license") or dataset.get("license_status")
    ):
        findings.append(LintFinding(9, "dataset access and license status required"))
    try:
        venue_findings = _venue_check(root, cfg)
    except Exception as exc:
        venue_findings = [str(exc)]
    if venue_findings:
        findings.append(LintFinding(10, "; ".join(venue_findings)))
    return findings
