"""Autonomous audio bed engine — mood-matched ambient BGM via FFmpeg lavfi synthesis.

Generates a continuous low-volume ambient texture that glues speech and foley.
Three mood profiles map to ModeProfile audio_bed_mood:

- **tension_pulse** (incident): Warm 42/44.5 Hz sub-bass sines + low-passed brown rumble + slow LFO.
- **clinical_drone** (anatomical): Warm 45 Hz sub-bass sine + 90 Hz harmonic + filtered pink noise (<220 Hz).
- **mechanical_hum** (mechanical): 50 Hz industrial transformer hum + 100 Hz harmonic + low-passed rumble.

All generation is local FFmpeg; no remote API call is made.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Mood → FFmpeg lavfi filter chain
# ---------------------------------------------------------------------------

_MOOD_CHAINS: dict[str, str] = {
    # tension_pulse: warm sub-bass sine (42 Hz) + detuned beating sub (44.5 Hz) + filtered brown noise + slow tension LFO
    "tension_pulse": (
        "sine=frequency=42:sample_rate=48000[sub1];"
        "sine=frequency=44.5:sample_rate=48000[sub2];"
        "[sub2]volume=0.35[sub2v];"
        "anoisesrc=color=brown:sample_rate=48000:amplitude=0.06[bnoise];"
        "[bnoise]lowpass=f=100[filtered];"
        "[sub1][sub2v][filtered]amix=inputs=3:weights=0.60 0.25 0.15[raw];"
        "[raw]tremolo=f=0.9:d=0.35[out]"
    ),
    # clinical_drone: warm 45 Hz sub-bass sine + 90 Hz harmonic + soft low-pass filtered pink noise (<220 Hz)
    "clinical_drone": (
        "sine=frequency=45:sample_rate=48000[sub];"
        "sine=frequency=90:sample_rate=48000[h2];"
        "[h2]volume=0.12[subwarm];"
        "anoisesrc=color=pink:sample_rate=48000:amplitude=0.03[pnoise];"
        "[pnoise]lowpass=f=220[filtered_noise];"
        "[sub][subwarm][filtered_noise]amix=inputs=3:weights=0.65 0.15 0.20[out]"
    ),
    # mechanical_hum: deep 50 Hz industrial transformer hum + 100 Hz harmonic + low-pass brown machinery rumble
    "mechanical_hum": (
        "sine=frequency=50:sample_rate=48000[hum50];"
        "sine=frequency=100:sample_rate=48000[hum100];"
        "[hum100]volume=0.18[hum100v];"
        "anoisesrc=color=brown:sample_rate=48000:amplitude=0.07[bnoise];"
        "[bnoise]lowpass=f=180[rumble];"
        "[hum50][hum100v][rumble]amix=inputs=3:weights=0.60 0.20 0.20[out]"
    ),
    # epic_curiosity: 40 Hz deep sub-bass + 120 Hz harmonic shimmer + atmospheric low-pass ambient + gentle wonder tremolo
    "epic_curiosity": (
        "sine=frequency=40:sample_rate=48000[sub];"
        "sine=frequency=120:sample_rate=48000[harm];"
        "[harm]volume=0.18[harmv];"
        "anoisesrc=color=brown:sample_rate=48000:amplitude=0.05[bnoise];"
        "[bnoise]lowpass=f=160[ambient];"
        "[sub][harmv][ambient]amix=inputs=3:weights=0.55 0.25 0.20[raw];"
        "[raw]tremolo=f=0.5:d=0.25[out]"
    ),
}

# ---------------------------------------------------------------------------
# Mode name → mood mapping
# ---------------------------------------------------------------------------

_MODE_TO_MOOD: dict[str, str] = {
    "anatomical": "clinical_drone",
    "incident": "tension_pulse",
    "mechanical": "mechanical_hum",
    "explorer": "epic_curiosity",
}


def mood_from_mode(mode_name: str) -> str:
    """Map ModeProfile name to audio bed mood.

    Falls back to ``clinical_drone`` for unknown modes.
    """
    return _MODE_TO_MOOD.get(mode_name, "clinical_drone")


def generate_audio_bed(mood: str, duration_seconds: float, output_dir: str) -> str:
    """Generate mood-matched ambient audio bed via FFmpeg lavfi synthesis.

    Returns the absolute path to the generated 48 kHz stereo WAV file.

    Parameters
    ----------
    mood:
        One of ``tension_pulse``, ``clinical_drone``, ``mechanical_hum``.
    duration_seconds:
        Exact target length in seconds.
    output_dir:
        Directory in which to write the output file.
    """
    if mood not in _MOOD_CHAINS:
        raise ValueError(f"Unknown audio bed mood: {mood!r}; expected one of {sorted(_MOOD_CHAINS)}")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    out_path = Path(output_dir) / f"audio_bed_{mood}.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chain = _MOOD_CHAINS[mood]
    fade_in = 0.5
    fade_out = 1.0
    # Ensure fade_out doesn't exceed the duration
    effective_fade_out = min(fade_out, duration_seconds * 0.5)
    effective_fade_in = min(fade_in, duration_seconds * 0.25)

    # Build the full filter: mood chain → mono-to-stereo → fade → trim → format
    filtergraph = (
        f"{chain};"
        f"[out]afade=t=in:st=0:d={effective_fade_in},"
        f"afade=t=out:st={max(0, duration_seconds - effective_fade_out)}:d={effective_fade_out},"
        f"aformat=sample_rates=48000:channel_layouts=stereo,"
        f"stereotools=mode=lr>lr:slev=1.2:delay=2.5"
    )

    ffmpeg = config.resolve_ffmpeg()
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", filtergraph,
        "-t", f"{duration_seconds:.3f}",
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return str(out_path)


# ---------------------------------------------------------------------------
# Orchestral Score Engine (16:9 Longform Extension)
# ---------------------------------------------------------------------------

def generate_orchestral_score(mood: str, duration_seconds: float, output_dir: str) -> str:
    """Select and mix a real orchestral music track instead of synthetic drones.
    
    This implements the Longform capability for a true cinematic soundtrack.
    In a fully integrated environment, this would hit an API like Epidemic Sound
    or select from a local royalty-free `.wav` library.
    """
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    out_path = Path(output_dir) / f"orchestral_score_{mood}.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Real-world mapping to stock music stems
    mock_library = {
        "tension_pulse": "assets/music/stock_thriller_strings.wav",
        "clinical_drone": "assets/music/stock_ambient_piano.wav",
        "mechanical_hum": "assets/music/stock_industrial_brass.wav",
    }
    
    source_file = Path(config.ROOT) / mock_library.get(mood, mock_library["clinical_drone"])
    
    # In a true pipeline, if the file is missing we would hit an API to download it.
    # For architectural completeness, we expect the file to exist or we raise an error,
    # rather than faking an orchestral score with a sine wave generator.
    if not source_file.is_file():
        raise FileNotFoundError(f"Missing orchestral stem for mood '{mood}': {source_file}")
    
    fade_in = 1.0
    fade_out = 3.0
    effective_fade_out = min(fade_out, duration_seconds * 0.5)
    effective_fade_in = min(fade_in, duration_seconds * 0.25)

    ffmpeg = config.resolve_ffmpeg()
    
    # Real orchestral scores have much more dynamic range; we add a compressor.
    filtergraph = (
        f"afade=t=in:st=0:d={effective_fade_in},"
        f"afade=t=out:st={max(0, duration_seconds - effective_fade_out)}:d={effective_fade_out},"
        "acompressor=threshold=-12dB:ratio=4:attack=5:release=50,"
        "aformat=sample_rates=48000:channel_layouts=stereo"
    )

    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-stream_loop", "-1", "-i", str(source_file),
        "-t", f"{duration_seconds:.3f}",
        "-af", filtergraph,
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return str(out_path)


def generate_music_bed(mood: str, duration_seconds: float, output_dir: str, use_orchestral: bool = False) -> str:
    """Primary entry point for music generation, routing to the correct synthesis engine."""
    if use_orchestral:
        return generate_orchestral_score(mood, duration_seconds, output_dir)
    return generate_audio_bed(mood, duration_seconds, output_dir)
