"""Diegetic ambient soundscape service for immersive historical documentary productions.

Generates multi-layered, era-specific environmental sound beds via local FFmpeg
lavfi synthesis (zero network/transport calls, strictly AST-clean):
- Neolithic / Göbekli Tepe: Steppe wind whistling across stone megaliths + 40 Hz subterranean resonance + distant rhythmic limestone chiseling and hammerstone tapping with acoustic echo.
- Maritime / Çanakkale: Coastal wind + deep ocean surf wash + distant thunderous naval artillery rumble.
- Egyptian / Hawara: Echoing underground corridor reverberation + dry desert heat wind + low monolithic limestone resonance.
- Classical / Greco-Roman: Ancient open-air colonnade breeze + distant marketplace room tone + stone courtyard acoustic decay.
- Default: Atmospheric natural historical room tone + gentle wind and low-frequency earth warmth.

Glued behind narration and BGM with sidechain ducking to eliminate acoustic voids while preserving -14 LUFS broadcast clarity.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import config
from services.character import detect_era

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Era → Multi-layered diegetic filter complex
# ---------------------------------------------------------------------------

_ERA_SOUNDSCAPE_CHAINS: dict[str, tuple[str, str]] = {
    "neolithic": (
        (
            "anoisesrc=color=pink:sample_rate=48000:amplitude=0.04[wind_raw];"
            "[wind_raw]bandpass=f=350:w=250,flanger=delay=15:speed=0.25[wind];"
            "sine=frequency=40:sample_rate=48000[drone_raw];"
            "[drone_raw]volume=0.18,lowpass=f=75[drone];"
            "anoisesrc=color=white:sample_rate=48000:amplitude=0.05[tap_raw];"
            "[tap_raw]highpass=f=2800,equalizer=f=3200:t=q:w=3.0:g=6,tremolo=f=1.2:d=0.95,volume=0.08,aecho=0.8:0.7:60:0.3[chisel];"
            "[wind][drone][chisel]amix=inputs=3:weights=0.55 0.30 0.15,volume=0.35[out]"
        ),
        "Anatolian steppe wind whistling across megalithic circles, 40 Hz bedrock resonance, and distant rhythmic stone chiseling with natural hill echo",
    ),
    "ottoman": (
        (
            "anoisesrc=color=pink:sample_rate=48000:amplitude=0.05[wind_raw];"
            "[wind_raw]bandpass=f=420:w=300,flanger=delay=18:speed=0.15[wind];"
            "sine=frequency=48:sample_rate=48000[artillery_raw];"
            "[artillery_raw]tremolo=f=0.3:d=0.8,lowpass=f=95,volume=0.25[rumble];"
            "anoisesrc=color=brown:sample_rate=48000:amplitude=0.04[surf_raw];"
            "[surf_raw]lowpass=f=220,volume=0.20[surf];"
            "[wind][rumble][surf]amix=inputs=3:weights=0.50 0.30 0.20,volume=0.38[out]"
        ),
        "Dardanelles coastal winds, rhythmic sea surf, and low distant artillery thuds echoing across the strait",
    ),
    "egyptian": (
        (
            "anoisesrc=color=pink:sample_rate=48000:amplitude=0.04[sand_raw];"
            "[sand_raw]bandpass=f=300:w=200,volume=0.45[desert_wind];"
            "sine=frequency=44:sample_rate=48000[hum_raw];"
            "[hum_raw]volume=0.20,lowpass=f=85[chamber_hum];"
            "anoisesrc=color=brown:sample_rate=48000:amplitude=0.03[crypt_raw];"
            "[crypt_raw]lowpass=f=140,aecho=0.8:0.6:80:0.35,volume=0.20[reverb];"
            "[desert_wind][chamber_hum][reverb]amix=inputs=3:weights=0.50 0.30 0.20,volume=0.32[out]"
        ),
        "Hawara desert plateau wind, deep acoustic chamber hum, and subterranean limestone corridor reverberation",
    ),
    "greco_roman": (
        (
            "anoisesrc=color=pink:sample_rate=48000:amplitude=0.04[breeze_raw];"
            "[breeze_raw]bandpass=f=380:w=260,volume=0.45[breeze];"
            "sine=frequency=45:sample_rate=48000[stone_raw];"
            "[stone_raw]volume=0.16,lowpass=f=80[resonance];"
            "anoisesrc=color=white:sample_rate=48000:amplitude=0.03[crowd_raw];"
            "[crowd_raw]bandpass=f=1200:w=800,volume=0.06,aecho=0.7:0.5:100:0.25[colonnade];"
            "[breeze][resonance][colonnade]amix=inputs=3:weights=0.55 0.30 0.15,volume=0.32[out]"
        ),
        "Mediterranean colonnade breeze, marble hall resonance, and distant courtyard acoustic reflection",
    ),
    "default": (
        (
            "anoisesrc=color=pink:sample_rate=48000:amplitude=0.04[wind_raw];"
            "[wind_raw]bandpass=f=350:w=240,volume=0.45[wind];"
            "sine=frequency=42:sample_rate=48000[drone_raw];"
            "[drone_raw]volume=0.16,lowpass=f=80[drone];"
            "anoisesrc=color=brown:sample_rate=48000:amplitude=0.03[room_raw];"
            "[room_raw]lowpass=f=160,volume=0.20[room];"
            "[wind][drone][room]amix=inputs=3:weights=0.50 0.30 0.20,volume=0.30[out]"
        ),
        "Natural atmospheric room tone, gentle landscape breeze, and warm low-frequency acoustic bedrock",
    ),
}


def resolve_soundscape_for_topic(topic_or_era: str) -> tuple[str, str, str]:
    """Resolve soundscape era, filter graph, and descriptive label."""
    candidate_era = topic_or_era.strip().casefold()
    if candidate_era in _ERA_SOUNDSCAPE_CHAINS:
        era = candidate_era
    else:
        era = detect_era(topic_or_era)
    
    chain_info = _ERA_SOUNDSCAPE_CHAINS.get(era) or _ERA_SOUNDSCAPE_CHAINS["default"]
    return era, chain_info[0], chain_info[1]


def get_soundscape_description(topic_or_era: str) -> str:
    """Return descriptive human-readable label of the diegetic soundscape."""
    _, _, desc = resolve_soundscape_for_topic(topic_or_era)
    return desc


def generate_ambient_soundscape(
    topic_or_era: str,
    duration: float,
    out_path: Path | str,
    ffmpeg: str | None = None,
) -> Path:
    """Synthesize multi-layered diegetic ambient soundscape matching historical era.

    Returns the absolute Path to the generated 48 kHz stereo WAV file.
    """
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = ffmpeg or config.resolve_ffmpeg()

    era, filter_complex, desc = resolve_soundscape_for_topic(topic_or_era)
    logger.info(f"[SOUNDSCAPE] Synthesizing diegetic audio for {era.upper()} ({duration:.1f}s): {desc}")

    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", f"{duration:.3f}",
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(out_p),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out_p.exists() or out_p.stat().st_size == 0:
        logger.warning(f"[SOUNDSCAPE] Synthesis failed ({proc.returncode}): {proc.stderr[:300]}; falling back to silence")
        # Generate silence fallback
        fb_cmd = [
            ffmpeg_exe, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", f"{duration:.3f}",
            "-c:a", "pcm_s16le",
            str(out_p),
        ]
        subprocess.run(fb_cmd, capture_output=True, check=False)

    return out_p
