from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def tmp_home(tmp_path: Path) -> Path:
    home = tmp_path / "luna-home"
    home.mkdir(parents=True)
    return home
