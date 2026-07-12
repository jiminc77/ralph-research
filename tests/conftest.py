from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def repo_factory(tmp_path: Path):
    def create(name: str = "repo") -> Path:
        path = tmp_path / name
        path.mkdir()
        return path

    return create
