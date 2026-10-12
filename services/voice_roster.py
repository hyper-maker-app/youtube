"""Deepgram Flux multi-voice roster with round-robin assignment and Entity Voice Lock.

Provides:
1. Male Flux Roster: Cliff, Kit, Conor, Donovan.
2. Female Flux Roster: Hannah, Alexis, Maeve, Sienna, Bree.
3. VoiceAssigner: Deterministic assignment preserving Entity Voice Lock across the production timeline.

Strictly AST-clean: Zero network calls, zero provider imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FluxVoice:
    """Immutable voice descriptor."""

    model_id: str
    name: str
    gender: str  # "male" | "female"
    accent: str
    tone: str
    primary_use: str


# ── Erkek Yardımcı Ses Havuzu (Sıralı / Round-Robin) ──
MALE_FLUX_ROSTER: tuple[FluxVoice, ...] = (
    FluxVoice(
        model_id="flux-cliff-en",
        name="Cliff",
        gender="male",
        accent="American",
        tone="Deep, confident, calm, raspy",
        primary_use="Hollywood trailer / Epic documentary",
    ),
    FluxVoice(
        model_id="flux-kit-en",
        name="Kit",
        gender="male",
        accent="British",
        tone="Friendly, energetic, clear, young adult",
        primary_use="Narrative engagement / Field interviewer",
    ),
    FluxVoice(
        model_id="flux-conor-en",
        name="Conor",
        gender="male",
        accent="British",
        tone="Deep, relaxed, mature, authoritative",
        primary_use="Historical veteran / Officer witness",
    ),
    FluxVoice(
        model_id="flux-donovan-en",
        name="Donovan",
        gender="male",
        accent="American",
        tone="Professional, calm, thoughtful, classical TV",
        primary_use="Archival historian / Expert witness",
    ),
)

# ── Kadın Yardımcı Ses Havuzu (Sıralı / Round-Robin) ──
FEMALE_FLUX_ROSTER: tuple[FluxVoice, ...] = (
    FluxVoice(
        model_id="flux-hannah-en",
        name="Hannah",
        gender="female",
        accent="American",
        tone="Clear, confident, storytelling, pleasant",
        primary_use="Featured storytelling",
    ),
    FluxVoice(
        model_id="flux-alexis-en",
        name="Alexis",
        gender="female",
        accent="American",
        tone="Professional, calm, empathetic, reassuring",
        primary_use="Professional eyewitness",
    ),
    FluxVoice(
        model_id="flux-maeve-en",
        name="Maeve",
        gender="female",
        accent="Irish",
        tone="Dramatic Irish accent, mystical, atmospheric",
        primary_use="Mythic / Epic witness",
    ),
    FluxVoice(
        model_id="flux-sienna-en",
        name="Sienna",
        gender="female",
        accent="American",
        tone="Warm, caring, fluid, young adult",
        primary_use="Intimate personal account",
    ),
    FluxVoice(
        model_id="flux-bree-en",
        name="Bree",
        gender="female",
        accent="American",
        tone="Mature, friendly, sweet, wise elder",
        primary_use="Historical elder / Matriarch witness",
    ),
)

_TITLES_PATTERN = re.compile(
    r"\b(corporal|captain|commander|officer|general|chief|royal|master|architect|baker|"
    r"historian|chronicler|soldier|gunner|artilleryman|onbaşı|onbasi|çavuş|cavus|"
    r"yüzbaşı|yuzbasi|binbaşı|binbasi|er|usta|kalfa|mimar|elder|keeper|scholar)\b",
    re.IGNORECASE,
)

_FEMALE_MARKERS: tuple[str, ...] = (
    "woman", "female", "lady", "queen", "priestess", "bree", "hannah", "alexis",
    "maeve", "sienna", "mother", "sister", "defne", "nova", "hatun", "sultan",
    "valide", "empress", "princess", "duchess", "abbess", "nun", "matron", "maiden",
    "daughter", "wife", "hatshepsut", "cleopatra", "nefertiti", "zenobia", "boudica",
)

_MALE_MARKERS: tuple[str, ...] = (
    "man", "male", "corporal", "captain", "onbaşı", "seyit", "baker", "neo",
    "soldier", "gunner", "father", "brother", "cliff", "kit", "conor", "donovan",
    "vitruvius", "torkhan", "neferhotep", "herodotus", "arukh", "kaelen", "damon",
    "nihat", "ali", "niğdeli",
)


class VoiceAssigner:
    """Manages multi-voice assignment with Entity Voice Lock and gendered round-robin rotation."""

    def __init__(
        self,
        primary_voice: str = "aura-2-hera-en",
        initial_locks: dict[str, str] | None = None,
    ) -> None:
        self.primary_voice = primary_voice
        self._male_index: int = 0
        self._female_index: int = 0
        # Entity Lock Map: entity_id -> assigned_model_id
        self._entity_lock: dict[str, str] = dict(initial_locks or {})

    def assign_voice(self, beat: dict[str, Any] | object) -> str:
        """Assign voice model with immutable entity locking across the whole production."""
        if isinstance(beat, dict):
            role_raw = beat.get("role", "narrator")
        else:
            role_raw = getattr(beat, "role", "narrator")
        role = str(role_raw or "narrator").strip().casefold()

        # 1. Main narrator / host nova always retains primary voice
        if role in ("narrator", "host_nova", "host_question", "default"):
            return self.primary_voice

        # 2. Extract normalized entity identifier
        entity_id = self._canonical_entity_id(role)

        # 3. Entity Lock Guarantee: If already assigned in this video, NEVER change
        if entity_id in self._entity_lock:
            return self._entity_lock[entity_id]

        # 4. Gender Detection
        gender = self._detect_gender(role, beat)

        # 5. Round-Robin Assignment from the appropriate gender pool
        if gender == "male":
            if not MALE_FLUX_ROSTER:
                return self.primary_voice
            voice = MALE_FLUX_ROSTER[self._male_index % len(MALE_FLUX_ROSTER)]
            self._male_index += 1
        else:
            if not FEMALE_FLUX_ROSTER:
                return self.primary_voice
            voice = FEMALE_FLUX_ROSTER[self._female_index % len(FEMALE_FLUX_ROSTER)]
            self._female_index += 1

        # Lock this entity for the rest of the production run
        self._entity_lock[entity_id] = voice.model_id
        return voice.model_id

    def _canonical_entity_id(self, role: str) -> str:
        """Normalize role to unique entity ID with title stripping and substring matching."""
        clean = re.sub(r"^witness:\s*", "", role, flags=re.IGNORECASE)
        # Strip parenthetical annotations like "(1840 BC — Middle Kingdom Egypt)"
        clean = re.sub(r"\([^)]*\)", "", clean).strip()
        # Strip military, occupational, and honorary titles
        clean = _TITLES_PATTERN.sub("", clean)
        clean = re.sub(r"[^\w]+", "_", clean).strip("_").casefold()
        if not clean:
            clean = "auxiliary_speaker"

        # Substring containment check against existing locks
        # (e.g. "seyit" matches "corporal_seyit" or "seyit_onbasi")
        for existing_id in self._entity_lock:
            if existing_id and (existing_id in clean or clean in existing_id):
                return existing_id

        return clean

    def _detect_gender(self, role: str, beat: Any = None) -> str:
        """Determine gender using historical role indicators, titles, and text cues."""
        text = ""
        if isinstance(beat, dict):
            text = str(beat.get("text", "") or "").casefold()
        elif hasattr(beat, "text"):
            text = str(getattr(beat, "text", "") or "").casefold()
        r = role.casefold()

        if any(m in r for m in _FEMALE_MARKERS) or any(m in text for m in ("she said", "as a woman", "her voice")):
            return "female"
        if any(m in r for m in _MALE_MARKERS):
            return "male"
        # Historical military/archaeological default bias
        return "male"

    def get_locked_voices(self) -> dict[str, str]:
        """Return a copy of the current entity-to-voice lock map."""
        return dict(self._entity_lock)
