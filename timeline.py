"""Provider-native timeline planning for video runs.

Every new run receives one immutable plan before the script is generated.  The
plan is persisted in ``script.json`` so a resume cannot silently change its
scene count, narration budget, or final duration when defaults evolve later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil
from typing import Iterable


BEAT_COUNT = 5
DEFAULT_MIN_DURATION = 32.0
VOICE_TAIL_SECONDS = 0.8


@dataclass(frozen=True)
class MotionProfile:
    key: str
    source: str
    display_name: str
    native_clip_duration: float
    output_resolution: str
    estimated_cost_per_second: float | None


MOTION_PROFILES: dict[str, MotionProfile] = {
    # The provider-factory pipeline owns a deterministic 8 x 4-second contract.
    "providers_4s": MotionProfile("providers_4s", "providers", "Provider adapters (4s)", 4.0, "720p", None),
    "veo_lite": MotionProfile("veo_lite", "flow", "Veo 3.1 Lite", 8.0, "720p", None),
    "vertex_veo_lite": MotionProfile("vertex_veo_lite", "vertex", "Vertex Veo 3.1 Lite", 8.0, "720p", 0.03),
    "vertex_veo_fast": MotionProfile("vertex_veo_fast", "vertex", "Vertex Veo 3.1 Fast", 8.0, "720p", 0.08),
    "vertex_veo": MotionProfile("vertex_veo", "vertex", "Vertex Veo 3.1", 8.0, "720p", 0.20),
    "h3_max": MotionProfile("h3_max", "fal", "MiniMax H3 Max", 5.0, "768p", 0.08),
    "kling_pro": MotionProfile("kling_pro", "fal", "Kling 2.5 Turbo Pro", 5.0, "720p", 0.07),
    "veo_fast": MotionProfile("veo_fast", "fal", "Veo 3.1 Fast", 8.0, "1080p", 0.10),
    "hailuo": MotionProfile("hailuo", "fal", "Hailuo 02", 6.0, "768p", None),
    "wan": MotionProfile("wan", "fal", "Wan 2.2 A14B", 4.0, "720p", None),
}


@dataclass(frozen=True)
class TimelinePlan:
    source: str
    motion_model: str
    motion_model_name: str
    native_clip_duration: float
    minimum_duration: float
    beat_count: int
    block_count: int
    shot_durations: tuple[float, ...]
    total_duration: float
    keyframe_count: int
    output_resolution: str
    estimated_cost_per_second: float | None = None
    legacy: bool = False
    # These are persisted render facts.  ``total_duration`` remains the generated
    # native footage duration for backwards compatibility with existing scripts.
    target_duration: float | None = None
    tail_hold: float = 1.5
    voice_duration: float | None = None
    content_duration: float | None = None

    @property
    def boundaries(self) -> list[float]:
        total = 0.0
        boundaries: list[float] = []
        for duration in self.shot_durations[:-1]:
            total += duration
            boundaries.append(round(total, 3))
        return boundaries

    @property
    def voice_target_duration(self) -> float:
        return max(4.0, self.total_duration - VOICE_TAIL_SECONDS)

    @property
    def voice_accept_min(self) -> float:
        return max(0.1, self.voice_target_duration - 0.4)

    @property
    def voice_accept_max(self) -> float:
        return self.voice_target_duration + 0.2

    @property
    def estimated_video_cost(self) -> float | None:
        if self.estimated_cost_per_second is None:
            return None
        return round(self.total_duration * self.estimated_cost_per_second, 2)

    def shot_window(self, block: int) -> tuple[float, float]:
        if not 1 <= block <= self.block_count:
            raise IndexError(f"Block {block} is outside 1..{self.block_count}")
        start = sum(self.shot_durations[:block - 1])
        end = start + self.shot_durations[block - 1]
        return round(start, 3), round(end, 3)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["shot_durations"] = list(self.shot_durations)
        # The public artifact names requested by the production protocol coexist
        # with the long-standing Python ``block_count`` field.
        data["n_blocks"] = self.block_count
        data["footage_duration"] = self.total_duration
        data["target_duration"] = self.target_duration if self.target_duration is not None else self.total_duration
        data["content_duration"] = self.content_duration if self.content_duration is not None else max(0.0, self.total_duration - self.tail_hold)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TimelinePlan":
        raw_durations = tuple(float(item) for item in data.get("shot_durations") or [])
        block_count = int(data.get("n_blocks") or data.get("block_count") or len(raw_durations))
        if not raw_durations:
            raise ValueError("Timeline plan has no shot durations")
        if len(raw_durations) != block_count:
            raise ValueError("Timeline block_count does not match shot_durations")
        total = round(sum(raw_durations), 3)
        declared_total = float(data.get("total_duration") or total)
        if abs(declared_total - total) > 0.01:
            raise ValueError("Timeline total_duration does not match shot_durations")
        return cls(
            source=str(data.get("source") or "legacy"),
            motion_model=str(data.get("motion_model") or "legacy"),
            motion_model_name=str(data.get("motion_model_name") or "Legacy timeline"),
            native_clip_duration=float(data.get("native_clip_duration") or raw_durations[0]),
            minimum_duration=float(data.get("minimum_duration") or total),
            beat_count=int(data.get("beat_count") or BEAT_COUNT),
            block_count=block_count,
            shot_durations=raw_durations,
            total_duration=total,
            keyframe_count=int(data.get("keyframe_count") or block_count + 1),
            output_resolution=str(data.get("output_resolution") or "unknown"),
            estimated_cost_per_second=data.get("estimated_cost_per_second"),
            legacy=bool(data.get("legacy", False)),
            target_duration=float(data["target_duration"]) if data.get("target_duration") is not None else total,
            tail_hold=float(data.get("tail_hold") or 1.5),
            voice_duration=float(data["voice_duration"]) if data.get("voice_duration") is not None else None,
            content_duration=float(data["content_duration"]) if data.get("content_duration") is not None else None,
        )

    @classmethod
    def for_profile(cls, profile_key: str, minimum_duration: float = DEFAULT_MIN_DURATION) -> "TimelinePlan":
        if profile_key not in MOTION_PROFILES:
            raise ValueError(f"Unknown motion model profile: {profile_key}")
        profile = MOTION_PROFILES[profile_key]
        minimum_duration = float(minimum_duration)
        if minimum_duration <= 0:
            raise ValueError("minimum duration must be positive")
        block_count = max(BEAT_COUNT, ceil(minimum_duration / profile.native_clip_duration))
        durations = tuple(profile.native_clip_duration for _ in range(block_count))
        total = round(sum(durations), 3)
        return cls(
            source=profile.source,
            motion_model=profile.key,
            motion_model_name=profile.display_name,
            native_clip_duration=profile.native_clip_duration,
            minimum_duration=minimum_duration,
            beat_count=BEAT_COUNT,
            block_count=block_count,
            shot_durations=durations,
            total_duration=total,
            keyframe_count=block_count + 1,
            output_resolution=profile.output_resolution,
            estimated_cost_per_second=profile.estimated_cost_per_second,
        )

    @classmethod
    def legacy_from_shots(cls, shots: Iterable[object]) -> "TimelinePlan":
        ordered = sorted(shots, key=lambda shot: int(getattr(shot, "block", 0)))
        if not ordered:
            raise ValueError("Cannot derive a legacy timeline without shots")
        durations: list[float] = []
        for shot in ordered:
            start = getattr(shot, "t_start", None)
            end = getattr(shot, "t_end", None)
            if start is not None and end is not None and float(end) > float(start):
                durations.append(round(float(end) - float(start), 3))
            else:
                durations.append(round(float(getattr(shot, "duration")), 3))
        if any(duration <= 0 for duration in durations):
            raise ValueError("Legacy timeline contains a non-positive shot duration")
        durations = tuple(durations)
        total = round(sum(durations), 3)
        return cls(
            source="legacy",
            motion_model="legacy",
            motion_model_name="Legacy persisted timeline",
            native_clip_duration=durations[0],
            minimum_duration=total,
            beat_count=BEAT_COUNT,
            block_count=len(durations),
            shot_durations=durations,
            total_duration=total,
            keyframe_count=len(durations) + 1,
            output_resolution="legacy",
            legacy=True,
        )


def profile_for_source(source: str, motion_model: str | None = None) -> str:
    if source == "flow":
        return "veo_lite"
    if source == "fal":
        return motion_model or "h3_max"
    if source == "vertex":
        # Keyframe-conditioned production uses a first-frame image.  Fast is the
        # supported GA default for that route; Lite remains an explicit profile only.
        return motion_model or "vertex_veo_fast"
    raise ValueError(f"Cannot choose a motion profile for source {source!r}")
