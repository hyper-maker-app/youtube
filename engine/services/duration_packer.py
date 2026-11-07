"""Allocate provider-native sources to continuous, measured audio windows."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
import re
import logging
from difflib import SequenceMatcher
from services.text_sanitizer import sanitize_spoken_text
from typing import Any

from providers.flow_contract import default_capabilities

# Provider-native Veo duration tiers (4s, 6s, 8s, 10s) and maximum shot ceiling
VEO_NATIVE_TIERS = tuple(float(v) for v in default_capabilities().supported_native_durations)
MAX_VEO_SHOT_DURATION = float(max(VEO_NATIVE_TIERS)) if VEO_NATIVE_TIERS else 10.0

@dataclass
class BlockPlan:
    block_index: int
    scene_id: str
    veo_duration: float
    audio_t0: float
    audio_t1: float
    pad_tail_seconds: float = 0.0
    freeze_tail_seconds: float = 0.0
    words: list[dict[str, Any]] = field(default_factory=list)
    visual_prompt: str = ""
    motion_prompt: str = ""
    narration: str = ""
    scene_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def speech_duration(self) -> float:
        return max(0.0, self.audio_t1 - self.audio_t0)


def is_data_broll_scene(scene: dict[str, Any]) -> bool:
    return bool(scene.get("is_data_broll") or scene.get("broll_type") or any(
        "[DATA_BROLL]" in str(scene.get(key, "")).upper()
        for key in ("visual_prompt", "motion_prompt")))


def snap_to_veo_tier(duration: float) -> float:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Duration must be positive and finite")
    candidates = [tier for tier in VEO_NATIVE_TIERS if tier >= duration - 1e-9]
    if not candidates:
        raise ValueError("Duration exceeds provider-native maximum; split the scene first")
    return min(candidates)


def split_scene_durations(duration: float, max_duration: float = MAX_VEO_SHOT_DURATION) -> list[float]:
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(max_duration) or max_duration <= 0:
        raise ValueError("Duration and shot ceiling must be positive and finite")
    allowed = [tier for tier in VEO_NATIVE_TIERS if tier <= max_duration]
    if not allowed:
        raise ValueError("Shot ceiling is below every supported provider-native duration")

    # If duration fits within max_duration without splitting into multiple blocks:
    if duration <= max_duration:
        # Screenwriter 4.0s scene -> preserve as 4.0s native
        if duration <= 4.0 and 4.0 in allowed:
            return [4.0]
        # Screenwriter 6.0s scene -> preserve as 6.0s native
        if duration <= 6.0 and 6.0 in allowed:
            return [6.0]
        # Screenwriter 8.0s scene or 6.0 - 8.5s speech range -> preserve as 8.0s native (do not split 4+4)
        if duration <= 8.5 and 8.0 in allowed:
            return [8.0]
        candidates = [tier for tier in allowed if tier >= duration - 1e-9]
        if candidates:
            return [min(candidates)]

    # If duration exceeds max_duration (e.g. > 10.0s), split across native tiers intelligently
    count = math.ceil(duration / max(allowed))
    needed = duration / count
    native = min(tier for tier in allowed if tier >= needed - 1e-9)
    return [native] * count


def _scene_audio_boundaries(scenes, durations, total_duration, words):
    """Prefer provider word timestamps; use authored proportions only without alignment."""
    if words:
        ids = [str(scene.get("id") or scene.get("scene_id") or f"scene_{i+1:02d}")
               for i, scene in enumerate(scenes)]
        starts = []
        for scene_id in ids[1:]:
            assigned = [float(word["start"]) for word in words
                        if str(word.get("beat_id") or word.get("scene_id") or "") == scene_id]
            if not assigned:
                break
            starts.append(min(assigned))
        if len(starts) == len(scenes)-1 and all(0 < value < total_duration for value in starts) and starts == sorted(set(starts)):
            return [0.0, *starts, total_duration]
        clean = lambda token: re.sub(r"[^\w]", "", token).lower()
        scene_tokens = [[clean(token) for token in sanitize_spoken_text(str(scene.get("narration", ""))).split()]
                        for scene in scenes]
        if all(scene_tokens):
            authored = [token for tokens in scene_tokens for token in tokens]
            observed = [clean(str(word.get("text") or word.get("word") or "")) for word in words]
            matcher = SequenceMatcher(None, authored, observed, autojunk=False)
            token_map = {match.a+offset: match.b+offset
                         for match in matcher.get_matching_blocks() for offset in range(match.size)}
            offsets = [sum(len(tokens) for tokens in scene_tokens[:i]) for i in range(1,len(scenes))]
            if matcher.ratio() >= 0.65 and all(offset in token_map for offset in offsets):
                starts = [float(words[token_map[offset]]["start"]) for offset in offsets]
                if all(math.isfinite(value) and 0 < value < total_duration for value in starts) and starts == sorted(set(starts)):
                    return [0.0, *starts, total_duration]
    logging.getLogger(__name__).warning("Scene audio boundaries use authored duration proportions because word alignment is unavailable or incomplete")
    return [0.0, *[total_duration * sum(durations[:i]) / sum(durations) for i in range(1,len(scenes))], total_duration]


def pack_durations_to_veo_blocks(
    scenes: list[dict[str, Any]], total_audio_duration: float,
    words: list[dict[str, Any]] | None = None, default_block_duration: float = 8.0,
) -> list[BlockPlan]:
    if not scenes:
        return []
    if not math.isfinite(total_audio_duration) or total_audio_duration <= 0:
        raise ValueError("Measured audio duration must be positive and finite")
    durations = [float(scene.get("duration", default_block_duration)) for scene in scenes]
    if any(not math.isfinite(value) or value <= 0 for value in durations):
        raise ValueError("Scene durations must be positive and finite")
    boundaries = _scene_audio_boundaries(scenes, durations, total_audio_duration, words or [])
    plans: list[BlockPlan] = []
    for index, scene in enumerate(scenes):
        cursor, end = boundaries[index:index+2]
        span = end - cursor
        if is_data_broll_scene(scene):
            native_durations = [span]
        else:
            authored_dur = float(scene.get("duration", 0.0))
            if authored_dur == 8.0 and span <= 8.5:
                native_durations = [8.0]
            elif authored_dur == 4.0 and span <= 4.0:
                native_durations = [4.0]
            elif authored_dur in VEO_NATIVE_TIERS and span <= authored_dur:
                native_durations = [authored_dur]
            else:
                native_durations = split_scene_durations(span)
        count = len(native_durations)
        scene_id = str(scene.get("id") or scene.get("scene_id") or f"scene_{index+1:02d}")
        for part, native in enumerate(native_durations):
            start = cursor + span * part / count
            stop = cursor + span * (part + 1) / count if part < count - 1 else end
            suffix = chr(ord("a") + part) if part < 26 else str(part+1)
            plans.append(BlockPlan(
                block_index=len(plans)+1,
                scene_id=f"{scene_id}_{suffix}" if count > 1 else scene_id,
                veo_duration=native, audio_t0=start, audio_t1=stop,
                words=[word for word in (words or []) if float(word.get("start", 0)) >= start and float(word.get("start", 0)) < stop],
                visual_prompt=str(scene.get("visual_prompt", "")).strip(),
                motion_prompt=str(scene.get("motion_prompt", "")).strip(),
                narration=str(scene.get("narration", "")).strip(),
                scene_metadata=deepcopy(scene),
            ))
    return plans

snap_duration = snap_to_veo_tier
split_duration = split_scene_durations
pack_durations = pack_durations_to_veo_blocks
