"""Structural venue-profile validation without invoking TeX."""
from pathlib import Path
import yaml

KNOWN_ENGINES = {"latexmk", "pdflatex", "xelatex", "lualatex"}


def check_profile(profile_path: str | Path) -> list[str]:
    path = Path(profile_path)
    findings: list[str] = []
    if not path.is_file():
        return [f"venue profile missing: {path}"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"venue profile invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return ["venue profile must be a mapping"]
    engine = data.get("engine")
    if engine not in KNOWN_ENGINES:
        findings.append(f"unknown venue engine: {engine!r}")
    template = data.get("template")
    if not isinstance(template, str):
        return findings + ["venue profile template missing"]
    root = path.parents[1] if path.parent.name == "venue" else path.parent
    template_path = root / template
    if not template_path.is_dir():
        findings.append(f"venue template directory missing: {template_path}")
    elif not (template_path / "main.tex").is_file():
        findings.append(f"venue template main.tex missing: {template_path / 'main.tex'}")
    return findings
