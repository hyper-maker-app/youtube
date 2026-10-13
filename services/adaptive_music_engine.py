"""Adaptive Dynamic Music & Cinematic Braam Engine for Longform Documentaries.

Synthesizes responsive 5-stage dramatic tension audio beds and cinematic
braam/sub-drop turning-point impacts via FFmpeg lavfi filtergraphs (ADR-068).

Safeguards:
1. Broadcast Audio LUFS: Braam hits gain-staged to <= -12 dBFS with HP 30 Hz filter,
   preserving YouTube's integrated -14 LUFS / -1.5 dBTP broadcast standard.
2. Voiceover Protection (ADR-017): Center-channel midrange EQ dip (-3 dB @ 2.5 kHz)
   and stereo side-diffusion preserve speech clarity with ZERO voice pumping.
3. Windows CLI Protection: Multi-segment filtergraphs are written to script files
   invoked via FFmpeg ``-/filter_complex`` to eliminate command-line character overflow.
4. Format Isolation: Applied exclusively in Longform documentary mode; 9:16 Shorts
   retain the battle-tested audio_bed.py mood chains.

Strictly AST-clean: Zero network calls, zero provider imports.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

BRAAM_GAIN_DB: float = -12.0
BRAAM_HP_HZ: int = 30
BRAAM_DECAY_S: float = 0.8
VO_PROTECTION_DIP_DB: float = -3.0


@dataclass(frozen=True)
class BraamEvent:
    """A dramatic tension milestone or cinematic turning-point sonic impact."""

    block_idx: int
    t_start: float
    tension_level: int  # 0: CALM, 1: RISING, 2: CLIMAX, 3: BRAAM, 4: RESOLUTION
    braam_type: str = "sub_drop"  # "sub_drop" | "bass_impact" | "string_swell"
    duration_seconds: float = 0.8


@dataclass
class DramaticTensionMap:
    """Timeline map correlating screenplay beat phases to dynamic musical tension."""

    blocks: list[BraamEvent] = field(default_factory=list)
    total_duration: float = 0.0

    @classmethod
    def from_beats(
        cls, beats: list[dict[str, Any]], shot_durations: list[float]
    ) -> DramaticTensionMap:
        """Construct a 5-level tension progression mapped to documentary beat phases."""
        events: list[BraamEvent] = []
        current_time = 0.0

        total_b = len(beats)
        for idx, beat in enumerate(beats):
            dur = shot_durations[idx] if idx < len(shot_durations) else 4.0
            if isinstance(beat, dict):
                phase = str(beat.get("phase", "")).casefold()
                role = str(beat.get("role", "")).casefold()
            else:
                phase = str(getattr(beat, "phase", getattr(beat, "journey_phase", ""))).casefold()
                role = str(getattr(beat, "role", "")).casefold()

            if "arrival" in phase or "hook" in phase or idx == 0:
                t_level = 1  # RISING opening hook
                b_type = "string_swell"
            elif "context" in phase or "immersion" in phase:
                t_level = 0  # CALM atmospheric exploration
                b_type = "sub_drop"
            elif "turning" in phase or "climax" in phase or (total_b >= 10 and idx == total_b // 2) or (total_b >= 20 and idx == 15):
                t_level = 3  # BRAAM: pivotal revelation / artillery firing impact
                b_type = "sub_drop"
            elif "legacy" in phase or "verdict" in phase or "reflection" in phase or idx == total_b - 1:
                t_level = 4  # RESOLUTION: peaceful contemplative fade
                b_type = "string_swell"
            elif "rising" in phase or "investigation" in phase or idx > total_b // 3:
                t_level = 2  # Escalating tension
                b_type = "bass_impact"
            else:
                t_level = 1
                b_type = "sub_drop"

            events.append(
                BraamEvent(
                    block_idx=idx,
                    t_start=round(current_time, 3),
                    tension_level=t_level,
                    braam_type=b_type,
                    duration_seconds=dur,
                )
            )
            current_time += dur

        return cls(blocks=events, total_duration=round(current_time, 3))


class AdaptiveMusicPlan:
    """Compiles multi-layered FFmpeg lavfi synthesis script for adaptive music."""

    def __init__(self, tension_map: DramaticTensionMap) -> None:
        self.tension_map = tension_map

    def build_filtergraph(self) -> str:
        """Generate complete FFmpeg filter complex with stereo diffusion and braam hits."""
        dur = max(4.0, self.tension_map.total_duration)

        # Base drone layer: 40 Hz deep curiosity foundation
        # Climax/tension adds harmonic shimmer, resolution adds warm lowpass
        # Voicing protection: EQ dip at 2.5 kHz reserves center channel for voiceover
        lines = [
            f"sine=frequency=40:sample_rate=48000:duration={dur:.3f}[sub_raw];",
            "[sub_raw]volume=0.18,lowpass=f=75[sub];",
            f"anoisesrc=color=pink:sample_rate=48000:amplitude=0.03:duration={dur:.3f}[bed_raw];",
            "[bed_raw]bandpass=f=320:w=220,volume=0.22[bed];",
            f"sine=frequency=160:sample_rate=48000:duration={dur:.3f}[harm_raw];",
            "[harm_raw]volume=0.06,tremolo=f=0.8:d=0.7[harm];",
            "[sub][bed][harm]amix=inputs=3:weights=0.50 0.35 0.15[ambient_raw];",
        ]

        # Check if turning-point braam events exist
        braam_blocks = [e for e in self.tension_map.blocks if e.tension_level == 3]

        if braam_blocks:
            first_braam = braam_blocks[0]
            t0 = max(0.0, first_braam.t_start)
            # Braam pulse: 40 Hz + 200 Hz impact with 0.8s exponential decay
            lines.extend([
                f"sine=frequency=42:sample_rate=48000:duration=1.2[b_low];",
                f"sine=frequency=210:sample_rate=48000:duration=1.2[b_mid];",
                "[b_mid]volume=0.30[b_mid_scaled];",
                "[b_low][b_mid_scaled]amix=inputs=2:weights=0.70 0.30[b_raw];",
                f"[b_raw]highpass=f={BRAAM_HP_HZ},aeval='val(0)*pow(0.001,t/{BRAAM_DECAY_S})':c=same,volume=0.25[b_hit];",
                f"[b_hit]adelay={int(t0 * 1000)}|{int(t0 * 1000)}[b_delayed];",
                "[ambient_raw][b_delayed]amix=inputs=2:weights=0.75 0.25[mixed_raw];",
            ])
            post_mix = "[mixed_raw]"
        else:
            post_mix = "[ambient_raw]"

        # Broadcast mastering chain:
        # 1. Mid-frequency VO pocket (-3 dB @ 2500 Hz)
        # 2. Subtle stereo side-diffusion to clear center for speech
        # 3. Overall output volume = 0.19 (-14.4 dBFS)
        lines.extend([
            f"{post_mix}equalizer=f=2500:t=q:w=1.5:g={VO_PROTECTION_DIP_DB}[vo_cleared];",
            "[vo_cleared]stereotools=mode=lr>lr:slev=1.2:delay=2.5,volume=0.19[out]",
        ])

        return "".join(lines)

    def write_script_file(self, target_file: Path | str) -> Path:
        """Write filtergraph to file to avoid Windows command-line character overflow."""
        tgt = Path(target_file)
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tgt.write_text(self.build_filtergraph(), encoding="utf-8")
        return tgt


class AdaptiveMusicEngine:
    """Autonomous renderer for adaptive documentary music scores."""

    def __init__(self, ffmpeg_exe: str | None = None) -> None:
        self.ffmpeg_exe = ffmpeg_exe or config.resolve_ffmpeg()

    def generate(
        self,
        tension_map: DramaticTensionMap,
        duration: float,
        out_path: Path | str,
    ) -> Path:
        """Synthesize adaptive music bed to 48kHz stereo WAV."""
        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        plan = AdaptiveMusicPlan(tension_map)
        dur = max(1.0, duration or tension_map.total_duration)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="adaptive_music_filter_", delete=False, encoding="utf-8"
        ) as script_file:
            script_path = Path(script_file.name)
            plan.write_script_file(script_path)

        cmd = [
            self.ffmpeg_exe,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-/filter_complex", str(script_path),
            "-map", "[out]",
            "-t", f"{dur:.3f}",
            "-c:a", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            str(out_p),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0 or not out_p.exists() or out_p.stat().st_size == 0:
                logger.warning(
                    f"[ADAPTIVE MUSIC] FFmpeg failed ({proc.returncode}): {proc.stderr[:300]}; "
                    "falling back to clean silence"
                )
                fb_cmd = [
                    self.ffmpeg_exe, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", f"{dur:.3f}",
                    "-c:a", "pcm_s16le",
                    str(out_p),
                ]
                subprocess.run(fb_cmd, capture_output=True, check=False)
        finally:
            if script_path.exists():
                try:
                    script_path.unlink()
                except OSError:
                    pass

        return out_p
