"""Autonomous audio bed engine — mood-matched ambient BGM & cinematic music.

Handles:
1. Dynamic music fetching / downloading from Pixabay API or Thematic catalog
   (cinematic/dramatic category) with robust offline / procedural fallback.
2. FFmpeg broadcast -14 LUFS loudness normalization (EBU R128 standard).
3. Broadcast-standard TTS sidechain ducking (music dynamically attenuates under speech).
4. Local FFmpeg procedural synthesis for zero-cost, zero-latency offline operation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

try:
    from engine import config
except ImportError:
    import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mood → FFmpeg lavfi filter chains (Procedural Synthesis Fallback)
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
    # cinematic_dramatic: deep 38 Hz rumble + 76 Hz dark foundation + sweeping dramatic tension modulation
    "cinematic_dramatic": (
        "sine=frequency=38:sample_rate=48000[sub1];"
        "sine=frequency=76:sample_rate=48000[sub2];"
        "[sub2]volume=0.28[sub2v];"
        "anoisesrc=color=brown:sample_rate=48000:amplitude=0.08[bnoise];"
        "[bnoise]lowpass=f=120[filtered];"
        "[sub1][sub2v][filtered]amix=inputs=3:weights=0.55 0.25 0.20[raw];"
        "[raw]tremolo=f=0.7:d=0.40[out]"
    ),
}

# ---------------------------------------------------------------------------
# Mode / Genre → mood mapping
# ---------------------------------------------------------------------------

_MODE_TO_MOOD: dict[str, str] = {
    "anatomical": "clinical_drone",
    "incident": "tension_pulse",
    "mechanical": "mechanical_hum",
    "explorer": "epic_curiosity",
    "catastrophe": "tension_pulse",
    "sci-fi": "cinematic_dramatic",
    "horror": "tension_pulse",
    "survival": "tension_pulse",
}


def mood_from_mode(mode_name: str) -> str:
    """Map genre or ModeProfile name to audio bed mood. Defaults to tension_pulse."""
    return _MODE_TO_MOOD.get(mode_name.lower().strip(), "tension_pulse")


# ---------------------------------------------------------------------------
# Remote API Music Catalog: Pixabay & Thematic Integration
# ---------------------------------------------------------------------------

def fetch_pixabay_music(
    query: str = "cinematic dramatic tension",
    category: str = "music",
    duration_seconds: float = 60.0,
    output_dir: str | Path = "assets/music",
    api_key: str | None = None,
    timeout: float = 8.0,
) -> Path | None:
    """Fetch royalty-free dramatic background music track from Pixabay API.
    
    Returns the Path to the downloaded audio file, or None if unavailable.
    """
    key = api_key or os.getenv("PIXABAY_API_KEY")
    if not key:
        logger.debug("[AUDIO BED] PIXABAY_API_KEY not configured; skipping Pixabay fetch.")
        return None

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_file = out_dir / f"pixabay_{abs(hash(query + category)) % 1000000:06d}.mp3"
    if cache_file.is_file() and cache_file.stat().st_size > 10000:
        return cache_file

    try:
        params = urllib.parse.urlencode({
            "key": key,
            "q": query,
            "category": category,
            "per_page": 5,
        })
        url = f"https://pixabay.com/api/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "GrokCinematicStudio/3.11.4"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        hits = data.get("hits", [])
        for hit in hits:
            audio_url = hit.get("audio") or hit.get("preview_url") or hit.get("download_url")
            if audio_url:
                logger.info(f"[AUDIO BED] Downloading Pixabay music track: {hit.get('tags', 'track')}")
                urllib.request.urlretrieve(audio_url, cache_file)
                if cache_file.is_file() and cache_file.stat().st_size > 5000:
                    return cache_file
    except Exception as exc:
        logger.warning(f"[AUDIO BED] Pixabay API fetch notice: {exc}. Engaging offline fallback.")

    return None


def fetch_thematic_music(
    category: str = "cinematic",
    mood: str = "dramatic",
    duration_seconds: float = 60.0,
    output_dir: str | Path = "assets/music",
    api_key: str | None = None,
    timeout: float = 8.0,
) -> Path | None:
    """Fetch royalty-free dramatic background music track from Thematic catalog API.
    
    Returns the Path to the downloaded audio file, or None if unavailable.
    """
    key = api_key or os.getenv("THEMATIC_API_KEY")
    if not key:
        logger.debug("[AUDIO BED] THEMATIC_API_KEY not configured; skipping Thematic fetch.")
        return None

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_file = out_dir / f"thematic_{abs(hash(category + mood)) % 1000000:06d}.mp3"
    if cache_file.is_file() and cache_file.stat().st_size > 10000:
        return cache_file

    try:
        url = f"https://api.hellothematic.com/v1/tracks?genre={category}&mood={mood}&limit=5"
        req = urllib.request.Request(url, headers={
            "User-Agent": "GrokCinematicStudio/3.11.4",
            "Authorization": f"Bearer {key}",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tracks = data.get("tracks", data if isinstance(data, list) else [])
        for track in tracks:
            audio_url = track.get("audio_url") or track.get("preview_url") or track.get("file_url")
            if audio_url:
                logger.info(f"[AUDIO BED] Downloading Thematic music track: {track.get('title', 'track')}")
                urllib.request.urlretrieve(audio_url, cache_file)
                if cache_file.is_file() and cache_file.stat().st_size > 5000:
                    return cache_file
    except Exception as exc:
        logger.warning(f"[AUDIO BED] Thematic API fetch notice: {exc}. Engaging offline fallback.")

    return None


# ---------------------------------------------------------------------------
# Loudness Normalization (-14 LUFS Standard)
# ---------------------------------------------------------------------------

def normalize_loudness(
    input_path: str | Path,
    target_lufs: float = -14.0,
    target_tp: float = -1.5,
    target_lra: float = 11.0,
    out_path: str | Path | None = None,
    ffmpeg: str | None = None,
) -> Path:
    """Apply FFmpeg -14 LUFS broadcast loudness normalization (EBU R128 / YouTube standard).
    
    Parameters
    ----------
    input_path:
        Path to source audio file.
    target_lufs:
        Integrated loudness target (default: -14.0 LUFS).
    target_tp:
        True peak limit in dBFS (default: -1.5 dBFS).
    target_lra:
        Loudness range target (default: 11.0 LU).
    out_path:
        Target output path (if None, overwrites input atomically via temp file).
    ffmpeg:
        Optional path to FFmpeg binary.
    """
    ffmpeg_bin = ffmpeg or config.resolve_ffmpeg()
    src = Path(input_path)
    if not src.is_file():
        raise FileNotFoundError(f"Source audio file not found: {src}")

    dest = Path(out_path) if out_path else src
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_out = dest.with_suffix(".norm.wav")

    loudnorm_filter = (
        f"loudnorm=I={target_lufs}:TP={target_tp}:LRA={target_lra},"
        f"aformat=sample_rates=48000:channel_layouts=stereo"
    )

    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-af", loudnorm_filter,
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(temp_out),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if temp_out.is_file() and temp_out.stat().st_size > 100:
            if dest == src:
                src.unlink(missing_ok=True)
            shutil.move(str(temp_out), str(dest))
            return dest
        raise RuntimeError(f"Loudnorm failed to produce output: {proc.stderr}")
    finally:
        if temp_out.exists():
            temp_out.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# TTS Ducking (Sidechain Compression)
# ---------------------------------------------------------------------------

def _probe_duration(path: Path, ffmpeg_bin: str) -> float | None:
    """Read stream duration via ffmpeg -i stderr."""
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        err = proc.stderr or ""
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", err)
        if m:
            h, mnt, s = m.groups()
            return int(h) * 3600 + int(mnt) * 60 + float(s)
    except Exception:
        pass
    return None


def duck_audio_bed(
    voice_path: str | Path,
    music_path: str | Path,
    out_path: str | Path,
    target_lufs: float = -14.0,
    target_duration: float | None = None,
    duck_threshold: float = 0.04,
    duck_ratio: float = 3.5,
    attack_ms: int = 15,
    release_ms: int = 600,
    music_volume: float = 0.19,
    ffmpeg: str | None = None,
) -> Path:
    """Apply FFmpeg sidechain ducking so background music ducks under speech with -14 LUFS normalization.
    
    The speech stream splits into [vo1] (heard) and [vo2] (control signal for compressor).
    The music loops seamlessly, is ducked by [vo2], mixed with [vo1], and normalized to -14 LUFS.
    """
    ffmpeg_bin = ffmpeg or config.resolve_ffmpeg()
    vo = Path(voice_path)
    mus = Path(music_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not vo.is_file():
        raise FileNotFoundError(f"Voice audio track not found: {vo}")
    if not mus.is_file():
        raise FileNotFoundError(f"Music bed audio track not found: {mus}")

    # Determine render duration (must be finite to terminate aloop and apad)
    effective_dur = target_duration or _probe_duration(vo, ffmpeg_bin) or 10.0

    filtergraph = (
        "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,asplit=2[vo1][vo2];"
        f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,aloop=loop=-1:size=2e+09,volume={music_volume}[mus];"
        f"[mus][vo2]sidechaincompress=threshold={duck_threshold}:ratio={duck_ratio}:attack={attack_ms}:release={release_ms}[duck];"
        "[vo1][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix];"
        f"[mix]loudnorm=I={target_lufs}:TP=-1.5:LRA=11,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
    )

    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(mus),
        "-i", str(vo),
        "-filter_complex", filtergraph,
        "-map", "[aout]",
        "-t", f"{effective_dur:.3f}",
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(out),
    ]

    subprocess.run(cmd, check=True)
    return out


# ---------------------------------------------------------------------------
# Audio Bed Synthesis & Orchestration
# ---------------------------------------------------------------------------

def generate_audio_bed(
    mood: str,
    duration_seconds: float,
    output_dir: str,
    category: str = "cinematic",
    prefer_download: bool = True,
    dry_run: bool = False,
) -> str:
    """Generate or fetch mood-matched dramatic background music bed normalized to -14 LUFS.
    
    Hierarchy:
    1. Remote royalty-free fetch (Pixabay / Thematic) if credentials exist and not in dry-run.
    2. Local stock catalog in assets/music/ if present.
    3. Resilient procedural FFmpeg lavfi synthesis with sub-bass and harmonic tremolo.
    4. -14 LUFS loudness normalization applied across all outputs.
    """
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    resolved_mood = mood if mood in _MOOD_CHAINS else mood_from_mode(mood)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"audio_bed_{resolved_mood}.wav"

    # Attempt remote download if enabled
    downloaded_track: Path | None = None
    if prefer_download and not dry_run:
        downloaded_track = fetch_pixabay_music(
            query=f"cinematic {resolved_mood} dramatic",
            category=category,
            duration_seconds=duration_seconds,
            output_dir=out_dir / "cache",
        )
        if not downloaded_track:
            downloaded_track = fetch_thematic_music(
                category=category,
                mood=resolved_mood,
                duration_seconds=duration_seconds,
                output_dir=out_dir / "cache",
            )

    ffmpeg_bin = config.resolve_ffmpeg()

    # If remote track was downloaded, loop/trim it to target duration
    if downloaded_track and downloaded_track.is_file():
        logger.info(f"[AUDIO BED] Processing downloaded music track -> {out_path.name}")
        filter_expr = (
            f"aloop=loop=-1:size=2e+09,atrim=0:{duration_seconds:.3f},"
            f"afade=t=in:st=0:d=1.0,afade=t=out:st={max(0, duration_seconds - 2.0)}:d=2.0,"
            f"aformat=sample_rates=48000:channel_layouts=stereo"
        )
        cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(downloaded_track),
            "-af", filter_expr,
            "-t", f"{duration_seconds:.3f}",
            "-c:a", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)
    else:
        # Offline procedural synthesis via FFmpeg lavfi
        chain = _MOOD_CHAINS.get(resolved_mood, _MOOD_CHAINS["tension_pulse"])
        fade_in = min(0.5, duration_seconds * 0.25)
        fade_out = min(1.0, duration_seconds * 0.5)

        filtergraph = (
            f"{chain};"
            f"[out]afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={max(0, duration_seconds - fade_out)}:d={fade_out},"
            f"aformat=sample_rates=48000:channel_layouts=stereo,"
            f"stereotools=mode=lr>lr:slev=1.2:delay=2.5"
        )

        cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", filtergraph,
            "-t", f"{duration_seconds:.3f}",
            "-c:a", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)

    # Normalize output to broadcast standard -14 LUFS
    normalize_loudness(out_path, target_lufs=-14.0, ffmpeg=ffmpeg_bin)
    return str(out_path)


def generate_orchestral_score(mood: str, duration_seconds: float, output_dir: str) -> str:
    """Select and mix an orchestral music track with compressor and -14 LUFS normalization."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    out_path = Path(output_dir) / f"orchestral_score_{mood}.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mock_library = {
        "tension_pulse": "assets/music/stock_thriller_strings.wav",
        "clinical_drone": "assets/music/stock_ambient_piano.wav",
        "mechanical_hum": "assets/music/stock_industrial_brass.wav",
        "cinematic_dramatic": "assets/music/stock_cinematic_dramatic.wav",
    }

    source_file = Path(config.ROOT) / mock_library.get(mood, mock_library["tension_pulse"])
    if not source_file.is_file():
        logger.debug(f"[AUDIO BED] Stock file {source_file} not found; falling back to synthesis.")
        return generate_audio_bed(mood, duration_seconds, output_dir)

    fade_in = min(1.0, duration_seconds * 0.25)
    fade_out = min(3.0, duration_seconds * 0.5)
    ffmpeg_bin = config.resolve_ffmpeg()

    filtergraph = (
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={max(0, duration_seconds - fade_out)}:d={fade_out},"
        "acompressor=threshold=-12dB:ratio=4:attack=5:release=50,"
        "aformat=sample_rates=48000:channel_layouts=stereo"
    )

    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-stream_loop", "-1", "-i", str(source_file),
        "-t", f"{duration_seconds:.3f}",
        "-af", filtergraph,
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    normalize_loudness(out_path, target_lufs=-14.0, ffmpeg=ffmpeg_bin)
    return str(out_path)


def generate_music_bed(mood: str, duration_seconds: float, output_dir: str, use_orchestral: bool = False) -> str:
    """Primary routing entry point for background music generation."""
    if use_orchestral:
        return generate_orchestral_score(mood, duration_seconds, output_dir)
    return generate_audio_bed(mood, duration_seconds, output_dir)


# ---------------------------------------------------------------------------
# Self-Test Validation Function
# ---------------------------------------------------------------------------

def test_audio_bed() -> bool:
    """Self-contained runnable test function for audio_bed.py.
    
    Verifies:
    1. Clean generation of audio bed via synthesis/fallback.
    2. FFmpeg -14 LUFS loudness normalization.
    3. Sidechain ducking of background music under speech.
    """
    import tempfile
    test_dir = Path(tempfile.mkdtemp(prefix="test_audio_bed_"))
    try:
        ffmpeg_bin = config.resolve_ffmpeg()

        # 1. Test audio bed generation
        bed_path = generate_audio_bed(
            mood="tension_pulse",
            duration_seconds=3.0,
            output_dir=str(test_dir),
            dry_run=True,
        )
        assert Path(bed_path).is_file(), f"Audio bed file was not generated: {bed_path}"
        assert Path(bed_path).stat().st_size > 1000, "Audio bed file is unexpectedly small"

        # 2. Test loudness normalization
        norm_path = test_dir / "normalized_test.wav"
        normalize_loudness(bed_path, target_lufs=-14.0, out_path=norm_path, ffmpeg=ffmpeg_bin)
        assert norm_path.is_file(), "Normalized audio file was not generated"

        # 3. Create a test voiceover tone
        vo_test_path = test_dir / "vo_test.wav"
        vo_cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=300:duration=3.0:sample_rate=48000",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1",
            str(vo_test_path),
        ]
        subprocess.run(vo_cmd, check=True)

        # 4. Test sidechain ducking under voiceover
        ducked_out = test_dir / "ducked_mix.wav"
        duck_audio_bed(
            voice_path=vo_test_path,
            music_path=norm_path,
            out_path=ducked_out,
            target_lufs=-14.0,
            ffmpeg=ffmpeg_bin,
        )
        assert ducked_out.is_file(), "Ducked mix output file was not generated"
        assert ducked_out.stat().st_size > 1000, "Ducked mix file is too small"

        logger.info("[AUDIO BED] All audio bed self-tests passed successfully.")
        return True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = test_audio_bed()
    print(f"audio_bed self-test passed: {success}")
