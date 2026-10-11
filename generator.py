"""Deprecated compatibility surface for screenplay-only code.

External service clients were removed from this module. New application code imports
from :mod:`services.script_engine` and resolves all remote work through ``providers``.
"""

from services.script_engine import Beat, BeatEngine, Script, Shot, annotate_words, optimize_for_flow

__all__ = ["Beat", "BeatEngine", "Script", "Shot", "annotate_words", "optimize_for_flow"]
