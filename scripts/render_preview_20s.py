"""Assemble 20.0s preview Short (5 blocks x 4.0s) with 1:1 Zack D. Films fidelity.

Includes:
- 5 video blocks scaled to 1080x1920 9:16 vertical
- Zack D. Films visual polish (vignette, micro-grain, contrast/saturation boost)
- Deepgram Hermes narration
- Tension ambient bed with ADR-017 sidechain ducking (-14.4 dBFS / 0.19 vol)
- 8 precisely timed ElevenLabs tactile ASMR Foley cues with Haas stereo & mastering
- Broadcast loudness mastering: integrated -14 LUFS / -1.5 dBTP
- Burned-in 9:16 vertical ASS captions in lower-middle safe zone
"""

import os
import sys
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import config


def main():
    root = Path(__file__).resolve().parent.parent
    prod_dir = root / "production_20s"
    out_path = prod_dir / "preview_20s.mp4"
    script_path = prod_dir / "_filtergraph.txt"
    captions_file = prod_dir / "captions.ass"

    ffmpeg = config.resolve_ffmpeg()

    blocks = [prod_dir / f"block{i:02d}.mp4" for i in range(1, 6)]
    for b in blocks:
        if not b.is_file():
            raise FileNotFoundError(f"Missing block: {b}")

    vo_path = prod_dir / "narration.wav"
    mus_path = prod_dir / "audio_bed_tension_pulse.wav"

    foleys = [
        {"path": prod_dir / "foley_water_plunge_mastered.wav", "dur": 0.80, "start": 1.0},
        {"path": prod_dir / "foley_door_handle_jam_mastered.wav", "dur": 0.68, "start": 3.2},
        {"path": prod_dir / "foley_door_handle_jam_mastered.wav", "dur": 0.68, "start": 5.2},
        {"path": prod_dir / "foley_seatbelt_unbuckle_mastered.wav", "dur": 0.65, "start": 8.8},
        {"path": prod_dir / "foley_window_button_mastered.wav", "dur": 0.60, "start": 10.5},
        {"path": prod_dir / "foley_underwater_swim_mastered.wav", "dur": 2.00, "start": 13.0},
        {"path": prod_dir / "foley_circuit_waterlog_mastered.wav", "dur": 1.48, "start": 16.8},
        {"path": prod_dir / "foley_window_thud_mastered.wav", "dur": 1.20, "start": 18.5},
    ]

    r = 44100
    stmts = []

    # Video block inputs: 0 to 4
    for i in range(5):
        stmts.append(
            f"[{i}:v]trim=duration=4.000,setpts=PTS-STARTPTS,fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1[v{i}]"
        )

    # Concat video
    stmts.append("[v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[cat]")
    stmts.append("[cat]zoompan=z='1.02':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30[zoom]")

    # Caption path escaping for Windows in FFmpeg filter
    # FFmpeg ass filter expects colons escaped as \: and backslashes escaped or forward slashes
    cap_str = str(captions_file).replace("\\", "/").replace(":", "\\:")
    stmts.append(
        f"[zoom]unsharp=5:5:0.5,noise=alls=2:allf=t+u,eq=contrast=1.06:saturation=1.05,vignette=PI/5,"
        f"ass=filename='{cap_str}':fontsdir='C\\:/Windows/Fonts'[vout]"
    )

    # Audio vo (input 5) and music (input 6)
    stmts.append(f"[5:a]aformat=sample_rates={r}:channel_layouts=stereo,apad,asplit=2[vo1][vo2]")
    stmts.append(f"[6:a]aformat=sample_rates={r}:channel_layouts=stereo,volume=0.19[mus]")
    stmts.append("[mus][vo2]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[duck]")
    stmts.append("[vo1][duck]amix=inputs=2:duration=first:dropout_transition=0[base]")

    # Foley inputs (inputs 7 to 14)
    sfx_labels = ["[base]"]
    for idx, f in enumerate(foleys):
        in_idx = 7 + idx
        dur = f["dur"]
        start = f["start"]
        delay_ms = int(round(start * 1000))
        fade_out_st = max(0.0, dur - 0.25)
        label = f"sfx{idx}"
        stmts.append(
            f"[{in_idx}:a]aformat=sample_rates={r}:channel_layouts=stereo,"
            f"atrim=0.000:{dur:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.015:curve=qsin,afade=t=out:st={fade_out_st:.3f}:d=0.250:curve=exp,"
            f"highpass=f=75,equalizer=f=250:t=q:w=1.5:g=-2.0,equalizer=f=4000:t=q:w=1.8:g=2.0,"
            f"haas=middle_source=mid:side_gain=1.25:left_delay=2.05:right_delay=2.12,"
            f"volume=-10.0dB,adelay={delay_ms}|{delay_ms}[{label}]"
        )
        sfx_labels.append(f"[{label}]")

    stmts.append(f"{''.join(sfx_labels)}amix=inputs={len(sfx_labels)}:duration=first:dropout_transition=0:normalize=0[mix]")
    stmts.append(f"[mix]loudnorm=I=-14:TP=-1.5:LRA=11,aformat=sample_rates={r}:channel_layouts=stereo[aout]")

    graph_text = ";\n".join(stmts)
    script_path.write_text(graph_text, encoding="utf-8")
    print(f"Wrote filtergraph to {script_path}")

    # Build command
    cmd = [ffmpeg, "-hide_banner", "-y"]
    for b in blocks:
        cmd += ["-i", str(b)]
    cmd += ["-i", str(vo_path)]
    cmd += ["-i", str(mus_path)]
    for f in foleys:
        cmd += ["-i", str(f["path"])]

    cmd += [
        "-/filter_complex", str(script_path),
        "-map", "[vout]", "-map", "[aout]",
        "-t", "20.000", "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        str(out_path)
    ]

    print(f"Rendering 20.0s preview video to {out_path}...")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print("FFmpeg error:")
        print(res.stderr[-2000:])
        raise RuntimeError(f"FFmpeg failed with code {res.returncode}")

    print(f"SUCCESS! Rendered: {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
