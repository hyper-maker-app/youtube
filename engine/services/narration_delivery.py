"""Authored delivery stays separate from spoken text; no emotion/SSML injection."""
from __future__ import annotations

import math
import re

INTENTS = ("direct_hook", "curiosity", "dread", "urgency", "quiet_observation", "disbelief", "controlled_fear", "investigative_focus", "relief", "grief", "determination", "revelation", "final_verdict", "release", "danger_reveal", "precise_mechanism", "human_decision", "consequence", "final_payoff")
ENERGIES = ("restrained", "low", "controlled", "medium", "urgent", "peak", "released")
DELIVERY_FIELDS = ("speaker", "intent", "emotional_state", "energy", "pace", "pitch_direction", "volume_intent", "pause_before_ms", "pause_after_ms", "emphasis_words", "stress_pattern", "breath_policy", "phrase_boundary", "release_point", "narration_to_visual_link", "foley_alignment", "caption_grouping", "tension_level", "pause_reason", "voice_id", "expressivity")

STORYTELLING_CONTRACT = """
Complete the manuscript, ending, world rules, motivations and consequences before splitting scenes.
Open with You and a concrete personal moment, then a causal question, visible mechanism,
safe meaningful character choice/reaction, observable consequence and earned payoff.
Give every subject a human goal, curiosity or consequence. Reuse the canonical protagonist/cast
across Shorts (mechanical, anatomical, incident, abstract/nonhuman) and general fiction longform.
Do not force danger, death or rescue. Mechanical characters can observe safely indoors;
anatomical characters perform everyday actions. Never invent diagnoses, cures or unsafe heroics.
The character connects the audience to the real mechanism, never replaces its causal explanation.
For fiction author a midpoint turning point and a final payoff tied to the character's choice/change.
Each scene separates character_goal, risk, mechanism, visible_causal_change, character_action,
consequence and tension_level. Track wardrobe, inventory, damage, location, entry/exit state.
Carry accepted identity/reference hashes and versions; no redesign on resume.
Author delivery separately from speech using intent, tension_level, pace (numeric speed),
emphasis_words, pause_reason, energy, release_point and phrase_boundary. Use expressivity=0,
pace=1.0 initially; never encode these fields as spoken tags. One stable narrator throughout;
secondary authored voices require voice_reason. Characters remain silent with closed/neutral mouths.
No prose shortening to native clip durations. One causal change and location per technical clip;
continue longer creative scenes with entry/exit continuity. Proof is authored, above or beside
the lower-middle caption-safe zone. Captions are FFmpeg/ASS only. No decorative arrows.
"""


def validate_controls(voice: str, speed: float, expressivity: int) -> None:
    if not re.fullmatch(r"(?:flux|aura(?:-2)?)-[a-z0-9]+-[a-z]{2}", voice):
        raise ValueError("Explicit flux-* or aura-* voice model required")
    minimum = .5 if voice.startswith("flux-") else .7
    if not math.isfinite(speed) or not minimum <= speed <= 1.5:
        raise ValueError("Speaking speed outside model range")
    if voice.startswith("flux-") and abs(speed * 20 - round(speed * 20)) > 1e-7:
        raise ValueError("Flux speed requires 0.05 increments")
    if isinstance(expressivity, bool) or expressivity not in (-2, -1, 0, 1, 2) or int(expressivity) != expressivity:
        raise ValueError("Expressivity requires a whole number from -2 to 2")
    if not voice.startswith("flux-") and expressivity != 0:
        raise ValueError("Expressivity is supported only by Flux")


def delivery_profile(authored: dict | None, voice: str, speed: float = 1.0, expressivity: int = 0) -> dict:
    authored = authored or {}
    result = {k: authored[k] for k in DELIVERY_FIELDS if k in authored}
    result.setdefault("intent", "precise_mechanism")
    result.setdefault("speaker", "external_narrator")
    result.setdefault("emotional_state", "controlled")
    result.setdefault("energy", "controlled")
    result.setdefault("pitch_direction", "level")
    result.setdefault("volume_intent", "clear")
    result.setdefault("pause_before_ms", 0)
    result.setdefault("stress_pattern", "natural")
    result.setdefault("breath_policy", "natural")
    result.setdefault("narration_to_visual_link", "authored scene causal change")
    result.setdefault("foley_alignment", "none")
    result.setdefault("caption_grouping", "sentence")
    result.setdefault("phrase_boundary", "paragraph")
    result.setdefault("voice_id", voice)
    result.setdefault("pace", speed)
    result.setdefault("expressivity", expressivity)
    if result["intent"] not in INTENTS:
        raise ValueError("Unknown delivery intent")
    if result["energy"] not in ENERGIES:
        raise ValueError("Unknown delivery energy")
    if result["speaker"] != "external_narrator":
        raise ValueError("Characters cannot speak without an explicit lip-sync capability contract")
    validate_controls(result["voice_id"], float(result["pace"]), result["expressivity"])
    pause = result.get("pause_after_ms", 0)
    if pause and (not isinstance(pause, int) or not 0 <= pause <= 3000 or pause % 20):
        raise ValueError("Pause requires 500-3000 ms in 100 ms increments")
    if pause and (not result.get("pause_reason") or not result["voice_id"].startswith("flux-") or result["pace"] > 1.15):
        raise ValueError("Authored pause requires reason, Flux REST and speed <= 1.15")
    return result


def application_report(profile: dict, provider_settings: dict) -> list[dict]:
    """Transport truth: authored intent is not automatically applied audio."""
    flux = str(provider_settings.get("voice_id", "")).startswith("flux-")
    supported = {"pace": True, "expressivity": flux, "pause_after_ms": flux, "pause_before_ms": False,
                 "pitch_direction": False, "volume_intent": False, "emphasis_words": False,
                 "stress_pattern": False, "breath_policy": False}
    report = []
    neutral = (None, "", 0, [], "natural", "level", "clear")
    for field, is_supported in supported.items():
        requested = profile.get(field)
        report.append({"field": field, "requested": requested, "provider_support": "supported" if is_supported else "unsupported",
                       "applied": bool(is_supported and requested not in neutral), "reason": "provider parameter" if is_supported else "unsupported_by_provider",
                       "production_impact": "none" if is_supported or requested in neutral else "manual_review_required"})
    return report


def transport_chunks(text: str, limit: int = 1500) -> list[str]:
    """Prefer complete sentences; split oversized sentences at words, never drop text."""
    chunks = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if not sentence:
            continue
        if len(sentence) <= limit:
            if chunks and len(chunks[-1]) + len(sentence) + 1 <= limit:
                chunks[-1] += " " + sentence
            else:
                chunks.append(sentence)
        else:
            for word in sentence.split():
                if len(word) > limit:
                    raise ValueError("Unbroken narration token exceeds transport limit; repair manuscript")
                if chunks and len(chunks[-1]) + len(word) + 1 <= limit:
                    chunks[-1] += " " + word
                else:
                    chunks.append(word)
    return chunks
