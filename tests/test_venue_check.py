from pathlib import Path
import shutil

import pytest
import yaml

from venue.check import check_profile


def test_valid_profile_passes(tmp_path):
    root = Path(__file__).parents[1]
    shutil.copytree(root / "venue", tmp_path / "venue")
    assert check_profile(tmp_path / "venue" / "venue_profile.lock.yml") == []


@pytest.mark.parametrize("problem", ["missing_template", "unknown_engine"])
def test_missing_template_and_unknown_engine_reported(tmp_path, problem):
    root = Path(__file__).parents[1]
    shutil.copytree(root / "venue", tmp_path / "venue")
    profile_path = tmp_path / "venue" / "venue_profile.lock.yml"
    profile = yaml.safe_load(profile_path.read_text())
    if problem == "missing_template":
        profile["template"] = "venue/templates/missing"
        expected = "template directory missing"
    else:
        profile["engine"] = "unknown-tex"
        expected = "unknown venue engine"
    profile_path.write_text(yaml.safe_dump(profile))
    assert any(expected in finding for finding in check_profile(profile_path))
