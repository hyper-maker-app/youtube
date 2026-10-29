"""Directing and cinematography rules loader from vendored open-source skills."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "vendor"

_GROK_MASTER_PROMPT = VENDOR_DIR / "Grok-Imagine-Cinematic-Studio" / "MASTER_PROMPT.md"
_VISUAL_SKILLS_DRAMATURGY = VENDOR_DIR / "visual-skills" / "video" / "references" / "dramaturgy.md"
_VISUAL_SKILLS_VEO = VENDOR_DIR / "visual-skills" / "video" / "references" / "veo.md"
_NARRATIVE_DIRECTION = (
    VENDOR_DIR / "narrative-film-direction" / "skills" / "narrative-film-direction" / "references" / "screen-direction.md"
)


def load_grok_master_prompt() -> str:
    """Return the raw Grok Cinematic Studio master orchestrator prompt if vendored."""
    if _GROK_MASTER_PROMPT.is_file():
        return _GROK_MASTER_PROMPT.read_text(encoding="utf-8")
    return ""


def load_dramaturgy_rules() -> str:
    """Return Walter Murch Rule-of-Six and rhythm guidelines if vendored."""
    if _VISUAL_SKILLS_DRAMATURGY.is_file():
        return _VISUAL_SKILLS_DRAMATURGY.read_text(encoding="utf-8")
    return ""


def load_screen_direction_rules() -> str:
    """Return 180-degree axis and eyeline matching rules if vendored."""
    if _NARRATIVE_DIRECTION.is_file():
        return _NARRATIVE_DIRECTION.read_text(encoding="utf-8")
    return ""


def load_veo_prompt_rules() -> str:
    """Return Google Veo specific prompt structuring guidelines if vendored."""
    if _VISUAL_SKILLS_VEO.is_file():
        return _VISUAL_SKILLS_VEO.read_text(encoding="utf-8")
    return ""


def get_cinematic_guidelines() -> str:
    """Concatenate core cinematic rules for prompt compiler and LLM system context."""
    sections: list[str] = []

    screen_dir = load_screen_direction_rules()
    if screen_dir:
        sections.append(
            "=== CONTINUITY & 180-DEGREE SCREEN DIRECTION RULES ===\n"
            "- The camera must stay on one side of the action line (180-degree rule).\n"
            "- Lock motion vector: if moving screen-left, keep moving screen-left in subsequent shots.\n"
            "- Eyeline matching: characters looking off-camera must have the target object placed in the matching direction."
        )

    dramaturgy = load_dramaturgy_rules()
    if dramaturgy:
        sections.append(
            "=== WALTER MURCH RULE OF SIX (MONTAGE & PACING) ===\n"
            "- Emotion (51%) > Story (23%) > Rhythm (10%) > Eye-Trace (7%).\n"
            "- Eye-Trace Lock: Anchor the viewer's eye. The focal point at the cut in Shot N+1 must start where Shot N ended.\n"
            "- Dynamic tempo: Vary rhythm between tension buildup, detail cutaways, and climactic action."
        )

    return "\n\n".join(sections)
