import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import config


@pytest.fixture(autouse=True)
def _normal_mode_by_default(monkeypatch):
    monkeypatch.setattr(config, "CALIBRATION_MODE", False)
