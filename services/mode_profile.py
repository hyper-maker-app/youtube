"""Production mode profiles for tri-modality pipeline.

The pipeline supports three production modes:
- ANATOMICAL: Medical/science cutaway documentary (original mode, void background)
- INCIDENT: Real-world news event animated documentary (contextual environments)
- MECHANICAL: Physics/engineering explainer (contextual environments, mannequin characters)

Every function that branches on mode uses ``mode: ModeProfile = ANATOMICAL`` so
that an omitted argument always falls back to the safe, established behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeProfile:
    """Immutable configuration bundle governing all mode-dependent pipeline behaviour."""
    name: str                              # "anatomical" | "incident" | "mechanical"
    environment_censor: bool               # True → void background enforced
    single_shot_human_anchor: bool         # True → human only in shot 1
    allowed_domains: tuple[str, ...]
    sfx_trigger_keywords: tuple[str, ...]
    max_sfx_cues: int
    environment_style: str                 # "void" | "contextual"
    character_style: str                   # "mannequin" | "role_based"
    narrator_style: str                    # "medical_eli12" | "news_narrative" | "mechanical_explainer"
    audio_bed_mood: str = "clinical_drone" # "tension_pulse" | "clinical_drone" | "mechanical_hum"


ANATOMICAL = ModeProfile(
    name="anatomical",
    environment_censor=True,
    single_shot_human_anchor=True,
    allowed_domains=("anatomical", "biological", "mechanical", "molecular",
                     "environmental", "space"),
    sfx_trigger_keywords=("fluid", "soap", "bubble", "valve", "release",
                          "pressure", "slide", "membrane", "flow", "pop", "open",
                          "crack", "snap", "click", "crunch", "tear", "stretch",
                          "compress", "burst", "bone", "cartilage", "friction",
                          "suction", "thud", "tap", "squelch", "hiss", "grind",
                          "strain", "rupture", "deflate", "inflate"),
    max_sfx_cues=6,
    environment_style="void",
    character_style="mannequin",
    narrator_style="medical_eli12",
    audio_bed_mood="clinical_drone",
)

INCIDENT = ModeProfile(
    name="incident",
    environment_censor=False,
    single_shot_human_anchor=False,
    allowed_domains=("incident", "mechanical", "environmental", "anatomical"),
    sfx_trigger_keywords=("metal", "buckle", "strap", "impact", "door", "slam",
                          "clank", "engine", "turbulence", "alarm", "crowd",
                          "siren", "crash", "glass", "step", "struggle",
                          "latch", "cabin", "seat", "lock", "unlatch", "press",
                          "force", "twist", "strike", "tackle", "click", "snap"),
    max_sfx_cues=8,
    environment_style="contextual",
    character_style="role_based",
    narrator_style="news_narrative",
    audio_bed_mood="tension_pulse",
)

MODE_REGISTRY: dict[str, ModeProfile] = {
    "anatomical": ANATOMICAL,
    "incident": INCIDENT,
}

MECHANICAL = ModeProfile(
    name="mechanical",
    environment_censor=False,
    single_shot_human_anchor=False,
    allowed_domains=("mechanical", "physics", "engineering", "environmental"),
    sfx_trigger_keywords=("metal", "gear", "piston", "valve", "pressure",
                          "hydraulic", "pneumatic", "bolt", "weld", "torque",
                          "friction", "tension", "compression", "shear",
                          "bearing", "shaft", "spring", "lever", "hinge",
                          "clamp", "drill", "saw", "grind", "spin",
                          "rotate", "vibrate", "oscillate"),
    max_sfx_cues=7,
    environment_style="contextual",
    character_style="mannequin",
    narrator_style="mechanical_explainer",
    audio_bed_mood="mechanical_hum",
)

EXPLORER = ModeProfile(
    name="explorer",
    environment_censor=False,
    single_shot_human_anchor=False,
    allowed_domains=("history", "mystery", "science", "nature", "exploration",
                     "archaeology", "civilization", "geography", "environment"),
    sfx_trigger_keywords=("footsteps", "wind", "creak", "stone", "water", "torch",
                          "reverb", "echo", "whisper", "rumble", "chime", "click",
                          "gear", "ambient", "breeze", "sand", "ocean", "forest"),
    max_sfx_cues=8,
    environment_style="contextual",
    character_style="explorer_persona",
    narrator_style="first_person_vlog",
    audio_bed_mood="epic_curiosity",
)

MODE_REGISTRY["mechanical"] = MECHANICAL
MODE_REGISTRY["explorer"] = EXPLORER


def detect_mode(topic: str) -> ModeProfile:
    """Detect production mode from topic string.

    Priority: explorer (if format=explorer or signals match) > incident > mechanical > anatomical (default).
    The user may always override with ``--mode explorer``, ``--mode incident`` or ``--mode mechanical``.
    """
    import os
    if (
        os.getenv("PRODUCTION_FORMAT", "").casefold() in {"explorer", "longform"}
        or os.getenv("LONGFORM_MODE", "").lower() in {"1", "true", "yes"}
    ):
        return EXPLORER

    topic_lower = topic.casefold()
    explorer_signals = (
        "pyramid", "ruins", "tomb", "temple", "ancient", "mystery", "lost city",
        "civilization", "expedition", "explorer", "archaeology", "antarctica",
        "deep sea", "trench", "atlantis", "monument", "artifacts", "curse",
        "labyrinth", "subterranean", "chamber", "hawara", "cistern",
    )
    if any(signal in topic_lower for signal in explorer_signals):
        return EXPLORER

    incident_signals = (
        "passenger", "flight", "crash", "arrested", "robbery", "fire",
        "earthquake", "accident", "attack", "storm", "hijack", "emergency",
        "police", "suspect", "witness", "victim", "bystander", "escaped",
        "broke into", "smashed", "vandal", "riot", "explosion",
        # Turkish equivalents
        "yolcu", "uçuş", "kaza", "olay", "saldırı", "yangın", "deprem",
        "polis", "şüpheli", "kaçış", "hırsız",
    )
    if any(signal in topic_lower for signal in incident_signals):
        return INCIDENT
    mechanical_signals = (
        "engine", "machine", "gear", "piston", "hydraulic", "bridge",
        "turbine", "motor", "brake", "suspension", "elevator", "crane",
        "robot", "factory", "pressure vessel", "boiler",
    )
    if any(signal in topic_lower for signal in mechanical_signals):
        return MECHANICAL
    return ANATOMICAL


def mode_from_name(name: str) -> ModeProfile:
    """Look up a ModeProfile by its string name.  Raises KeyError on unknown."""
    return MODE_REGISTRY[name]

