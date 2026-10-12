"""Assemble the final v2 60s lightning protection longform documentary.

This script updates script.json to reference the clean people-free B-roll clips,
compiles final.mp4 using imageio-ffmpeg with all 15 video and 16 audio inputs,
and generates a 1-FPS contact sheet for verification.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import editor

BASE_DIR = Path(r"out\why-lightning-rods-protect-buildings_20261012_manual").resolve()
CLIPS_DIR = BASE_DIR / "flow_clips"
AUDIO_DIR = BASE_DIR / "audio"
SEGMENTS_DIR = AUDIO_DIR / "segments"

VIDEO_FILES = [
    CLIPS_DIR / "block01_opening_v2.mp4",
    CLIPS_DIR / "block02_storm_v2.mp4",
    CLIPS_DIR / "block03_rod_myth_v2.mp4",
    CLIPS_DIR / "block04_intercept_v2.mp4",
    CLIPS_DIR / "block05_downconductor_v2.mp4",
    CLIPS_DIR / "block06_smooth_route_v2.mp4",
    CLIPS_DIR / "block07_grounding.mp4",
    CLIPS_DIR / "block08_midpoint_v2.mp4",
    CLIPS_DIR / "block09_bonding_v2.mp4",
    CLIPS_DIR / "block10_incoming_surge_v2.mp4",
    CLIPS_DIR / "block11_surge_protection_v2.mp4",
    CLIPS_DIR / "block12_whole_system_v2.mp4",
    CLIPS_DIR / "block13_inspection_v2.mp4",
    CLIPS_DIR / "block14_limits_v2.mp4",
    CLIPS_DIR / "block15_closing_host.mp4",
]

AUDIO_FILES = [
    CLIPS_DIR / "block01_opening_v2.mp3",
    SEGMENTS_DIR / "block02.mp3",
    SEGMENTS_DIR / "block03.mp3",
    SEGMENTS_DIR / "block04.mp3",
    SEGMENTS_DIR / "block05.mp3",
    SEGMENTS_DIR / "block06.mp3",
    SEGMENTS_DIR / "block07.mp3",
    CLIPS_DIR / "block08_midpoint_v2.mp3",
    SEGMENTS_DIR / "block09.mp3",
    SEGMENTS_DIR / "block10.mp3",
    SEGMENTS_DIR / "block11.mp3",
    SEGMENTS_DIR / "block12.mp3",
    SEGMENTS_DIR / "block13.mp3",
    SEGMENTS_DIR / "block14.mp3",
    CLIPS_DIR / "block15_closing_host.mp3",
    AUDIO_DIR / "audio_bed_epic_curiosity.wav",
]


def update_script_json() -> None:
    script_path = BASE_DIR / "script.json"
    data = json.loads(script_path.read_text(encoding="utf-8"))
    for idx, block in enumerate(data.get("blocks", [])):
        block["file"] = VIDEO_FILES[idx].name
    script_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {script_path} with v2 clip references.")


def check_inputs() -> None:
    for i, v in enumerate(VIDEO_FILES, 1):
        if not v.exists():
            raise FileNotFoundError(f"Missing video {i}: {v}")
    for i, a in enumerate(AUDIO_FILES, 1):
        if not a.exists():
            raise FileNotFoundError(f"Missing audio {i}: {a}")
    print("All 15 video clips and 16 audio inputs exist.")


def build_filtergraph() -> Path:
    fg_path = BASE_DIR / "_final_filtergraph.txt"
    ass_path = BASE_DIR / "captions.ass"
    escaped_ass = str(ass_path.resolve()).replace("\\", "/").replace(":", r"\:")

    lines = []
    # Video normalization & trim
    for i in range(15):
        lines.append(
            f"[{i}:v]scale=1920:1080:flags=lanczos,setsar=1,fps=30,trim=duration=4,setpts=PTS-STARTPTS,format=yuv420p[v{i}];"
        )
    # Concat videos & burn captions
    concat_inputs = "".join(f"[v{i}]" for i in range(15))
    lines.append(
        f"{concat_inputs}concat=n=15:v=1:a=0,format=yuv420p,ass=filename='{escaped_ass}':fontsdir='C\\:/Windows/Fonts'[vid];"
    )

    # Audio delays for 15 voice tracks (inputs 15..29)
    for i in range(15):
        delay_ms = i * 4000
        in_idx = 15 + i
        out_lbl = f"a{i+1}"
        lines.append(
            f"[{in_idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={delay_ms}|{delay_ms},apad=pad_dur=60,atrim=duration=60[{out_lbl}];"
        )

    # BGM track (input 30)
    lines.append(
        "[30:a]aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-16:TP=-7:LRA=6,volume=0.19,apad=pad_dur=60,atrim=duration=60[bgm];"
    )

    # Mix voices
    all_voices = "".join(f"[a{i+1}]" for i in range(15))
    lines.append(
        f"{all_voices}amix=inputs=15:duration=longest:normalize=0:dropout_transition=0,apad=pad_dur=60,atrim=duration=60[voices];"
    )

    # Final audio mix & loudnorm target -14 LUFS
    lines.append(
        "[voices][bgm]amix=inputs=2:duration=first:normalize=0:dropout_transition=0,loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
    )

    fg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote filtergraph to {fg_path}")
    return fg_path


def render_final_video() -> Path:
    ffmpeg = config.resolve_ffmpeg()
    final_output = BASE_DIR / "final.mp4"
    rejected_output = BASE_DIR / "final_v1_rejected.mp4"

    if final_output.exists() and not rejected_output.exists():
        shutil.move(str(final_output), str(rejected_output))
        print(f"Preserved old v1 output as {rejected_output.name}")

    fg_path = build_filtergraph()

    cmd = [ffmpeg, "-y"]
    # 15 video inputs
    for v in VIDEO_FILES:
        cmd.extend(["-i", str(v)])
    # 16 audio inputs
    for a in AUDIO_FILES:
        cmd.extend(["-i", str(a)])

    cmd.extend([
        "-filter_complex_script", str(fg_path),
        "-map", "[vid]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        str(final_output),
    ])

    print("Running FFmpeg render...")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print("FFmpeg stderr:\n", res.stderr[-2000:])
        raise RuntimeError(f"FFmpeg failed with exit code {res.returncode}")

    print(f"Render completed: {final_output} ({os.path.getsize(final_output):,} bytes)")
    return final_output


def generate_contact_sheet(final_output: Path) -> Path:
    ffmpeg = config.resolve_ffmpeg()
    contact_sheet = BASE_DIR / "contact_sheet_1fps.jpg"
    # Generate 60-frame 1 FPS tile (10x6 grid)
    cmd = [
        ffmpeg, "-y",
        "-i", str(final_output),
        "-vf", "fps=1,scale=384:216,tile=10x6",
        "-frames:v", "1",
        "-q:v", "2",
        str(contact_sheet),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Generated 1-FPS contact sheet: {contact_sheet}")
    return contact_sheet


def main():
    check_inputs()
    update_script_json()
    out = render_final_video()
    generate_contact_sheet(out)
    info = editor.probe(out)
    print(f"Final video probe: {info.duration:.2f}s | {info.width}x{info.height} | FPS: {info.fps}")


if __name__ == "__main__":
    main()
