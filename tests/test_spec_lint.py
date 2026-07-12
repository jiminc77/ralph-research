import json
from pathlib import Path

import pytest
import yaml

from ralph_core.schemas import Config
from ralph_core.spec_lint import spec_lint
from tests.fakes.fake_seams import FakeVenueCompile, make_template_repo


def test_clean_templates_pass(tmp_path):
    root = make_template_repo(tmp_path)
    assert spec_lint(root, Config.load(root / "config.yml")) == []


@pytest.mark.parametrize(
    ("rule", "change"),
    [
        (1, "baseline"),
        (2, "primary"),
        (3, "minimum_effect"),
        (4, "split"),
        (6, "candidates"),
        (8, "policy"),
    ],
)
def test_rule_violations_reported(tmp_path, rule, change):
    root = make_template_repo(tmp_path)
    spec_path = root / "RESEARCH_SPEC.md"
    if change in {"baseline", "primary", "minimum_effect", "candidates"}:
        text = spec_path.read_text(encoding="utf-8")
        payload = text.split("```yaml", 1)[1].split("```", 1)[0]
        spec = yaml.safe_load(payload)
        if change == "baseline":
            del spec["baseline"]["command"]
        elif change == "primary":
            del spec["metrics"]["primary"]
        elif change == "minimum_effect":
            del spec["metrics"]["minimum_effect"]
        else:
            spec["candidates"]["max"] = 9
        spec_path.write_text("# Research Specification\n\n```yaml\n" + yaml.safe_dump(spec) + "```\n")
    elif change == "split":
        manifest_path = root / "data/data_manifest.lock.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["splits"]["hidden_confirmation"]
        manifest_path.write_text(json.dumps(manifest))
    else:
        (root / "DECISION_POLICY.md").write_text("# Policy\nASK choices require review.\n")
    findings = spec_lint(root, Config.load(root / "config.yml"))
    assert any(finding.rule == rule for finding in findings)


def test_rule10_venue_seam_failure(tmp_path):
    root = make_template_repo(tmp_path)
    FakeVenueCompile.ok = False
    try:
        findings = spec_lint(root, Config.load(root / "config.yml"))
    finally:
        FakeVenueCompile.ok = True
    assert any(finding.rule == 10 for finding in findings)
