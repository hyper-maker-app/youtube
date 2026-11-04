"""Ensure repo-root, tools/, and archive/legacy_tools/ are importable for studio_core consumers."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_TOOLS = _ROOT / "tools"
_ARCHIVE = _ROOT / "archive" / "legacy_tools"


def ensure_import_paths() -> Path:
    """Insert repo root + tools/ + archive/legacy_tools on sys.path (idempotent). Return studio root."""
    tools_s = str(_TOOLS)
    root_s = str(_ROOT)
    archive_s = str(_ARCHIVE)
    if tools_s not in sys.path:
        sys.path.insert(0, tools_s)
    if _ARCHIVE.is_dir() and archive_s not in sys.path:
        sys.path.insert(0, archive_s)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    return _ROOT


STUDIO_ROOT = _ROOT
