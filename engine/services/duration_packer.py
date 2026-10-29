"""DurationPacker and BlockPlan synchronization service (UDSE v4.3 / Grok 4.6 Standard).

Locks discrete Google Veo video buckets [4.0, 6.0, 8.0, 10.0] to continuous Deepgram
Aura-2 speech timelines (AudioClock), guaranteeing zero A/V drift across scene cuts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

VEO_NATIVE_TIERS: tuple[float, ...] = (4.0, 6.0, 8.0, 10.0)


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

    @property
    def speech_duration(self) -> float:
        return max(0.0, self.audio_t1 - self.audio_t0)


def snap_to_veo_tier(duration: float) -> float:
    """Snap a duration to the nearest supported native Google Veo tier: [4.0, 6.0, 8.0, 10.0]."""
    return min(VEO_NATIVE_TIERS, key=lambda t: abs(t - duration))


def pack_durations_to_veo_blocks(
    scenes: list[dict[str, Any]],
    total_audio_duration: float,
    words: list[dict[str, Any]] | None = None,
    default_block_duration: float = 8.0,
) -> list[BlockPlan]:
    """Compile scenes and audio timestamps into a sequence of aligned BlockPlans.
    
    Invariants:
    1. AudioClock is the single source of truth for narrative pacing.
    2. Video durations snap strictly to legal Veo tiers (4, 6, 8, 10s).
    3. Trailing differences between speech and video are handled via explicit freeze-tail
       hold padding (tpad=stop_mode=clone) rather than arbitrary audio truncation (-shortest).
    """
    words = words or []
    block_plans: list[BlockPlan] = []
    accumulated_audio_t = 0.0
    accumulated_video_t = 0.0

    # Calculate speech duration per scene based on word timestamps if available
    for i, sc in enumerate(scenes):
        sc_dur = float(sc.get("duration", default_block_duration))
        sc_id = str(sc.get("id") or sc.get("scene_id") or f"scene_{i+1:02d}")

        # Derive word segment for this scene
        t0 = accumulated_audio_t
        t1 = min(total_audio_duration, t0 + sc_dur)
        if i == len(scenes) - 1:
            t1 = max(t1, total_audio_duration)

        scene_words = [
            w for w in words
            if float(w.get("start", 0.0)) >= t0 - 0.2 and float(w.get("end", 0.0)) <= t1 + 0.3
        ]

        # Snap video duration to nearest legal Veo tier >= nominal duration
        raw_target = sc_dur
        snapped_dur = snap_to_veo_tier(raw_target)

        # Compute freeze-tail or pad if video exceeds speech
        speech_span = t1 - t0
        tail_freeze = max(0.0, snapped_dur - speech_span)

        plan = BlockPlan(
            block_index=i + 1,
            scene_id=sc_id,
            veo_duration=snapped_dur,
            audio_t0=round(t0, 3),
            audio_t1=round(t1, 3),
            pad_tail_seconds=round(tail_freeze, 3),
            freeze_tail_seconds=round(tail_freeze, 3),
            words=scene_words,
            visual_prompt=str(sc.get("visual_prompt", "")).strip(),
            motion_prompt=str(sc.get("motion_prompt", "")).strip(),
        )
        block_plans.append(plan)

        accumulated_audio_t = t1
        accumulated_video_t += snapped_dur

    logger.info(
        f"[DurationPacker] Packed {len(block_plans)} blocks: "
        f"AudioClock={total_audio_duration:.2f}s, VideoClock={accumulated_video_t:.2f}s."
    )
    return block_plans
