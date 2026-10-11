"""Assemble final Hawara documentary video using generated Flow assets."""

import json
import os
import subprocess
from pathlib import Path
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

OUT_DIR = Path("out/the-lost-labyrinth-of-hawara_20261007_130518")
FLOW_OUT = Path("C:/Users/bekir/OneDrive/Masaüstü/flow-agent/flow-agent/output")

VIDEO_BLOCK1 = FLOW_OUT / "acct-3a47677a-5da.mp4"
IMAGE_BLOCK2 = FLOW_OUT / "acct-be19f889-414.jpg"
IMAGE_BLOCK3 = FLOW_OUT / "nova_artifact.png"
VO_PATH = OUT_DIR / "audio" / "vo.mp3"
WORDS_PATH = OUT_DIR / "words.json"
CAPTIONS_PATH = OUT_DIR / "captions.ass"
FINAL_VIDEO = OUT_DIR / "final_documentary.mp4"


def generate_ass_subtitles():
    """Generate ASS subtitles from words.json with sentence chunks."""
    with open(WORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = data.get("words", [])

    # Group words into 3-5 word chunks
    chunks = []
    current = []
    chunk_start = 0.0

    for w in words:
        if not current:
            chunk_start = w["start"]
        current.append(w["text"])
        if len(current) >= 4 or w["text"].endswith((".", ",", "?", "!")):
            chunk_end = w["end"] + 0.15
            chunks.append((chunk_start, chunk_end, " ".join(current).upper()))
            current = []

    if current:
        chunks.append((chunk_start, words[-1]["end"] + 0.2, " ".join(current).upper()))

    ass_header = """[Script Info]
Title: Hawara Documentary
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,38,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,30,30,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def fmt_time(t):
        hrs = int(t // 3600)
        mins = int((t % 3600) // 60)
        secs = t % 60
        return f"{hrs}:{mins:02d}:{secs:05.2f}"

    lines = [ass_header]
    for start, end, text in chunks:
        lines.append(f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Default,,0,0,0,,{text}\n")

    with open(CAPTIONS_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Generated subtitles: {CAPTIONS_PATH}")


def render():
    generate_ass_subtitles()

    # Step 1: Render Block 2 (Image to 8s Video with Ken Burns slow zoom)
    b2_video = OUT_DIR / "block02_motion.mp4"
    cmd_b2 = [
        FFMPEG_EXE, "-y",
        "-loop", "1", "-i", str(IMAGE_BLOCK2),
        "-vf", "scale=1376:768,zoompan=z='min(zoom+0.0006,1.12)':d=192:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24",
        "-t", "8.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(b2_video)
    ]
    print("Rendering Block 2 video motion...")
    subprocess.run(cmd_b2, check=True)

    # Step 2: Render Block 3 (Image to 7s Video with Ken Burns pan)
    b3_video = OUT_DIR / "block03_motion.mp4"
    cmd_b3 = [
        FFMPEG_EXE, "-y",
        "-loop", "1", "-i", str(IMAGE_BLOCK3),
        "-vf", "scale=1376:768,zoompan=z='1.08':x='iw/2-(iw/zoom/2)+on*0.3':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24:d=168",
        "-t", "7.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(b3_video)
    ]
    print("Rendering Block 3 video motion...")
    subprocess.run(cmd_b3, check=True)

    # Step 3: Concat 3 blocks, mix vo.mp3 + ambient bed, burn subtitles
    # Prepare concat file
    concat_list = OUT_DIR / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{VIDEO_BLOCK1.resolve().as_posix()}'\n")
        f.write(f"file '{b2_video.resolve().as_posix()}'\n")
        f.write(f"file '{b3_video.resolve().as_posix()}'\n")

    # Final assembly with audio bed synthesis and subtitle burn
    # Lavfi synth audio bed: low rumble (45Hz) + drone chord (110Hz) at -16dB
    filter_complex = (
        "subtitles=captions.ass:force_style='Fontsize=36'[v];"
        "[1:a]volume=1.0[vo];"
        "aevalsrc='0.07*sin(2*PI*45*t)+0.035*sin(2*PI*110*t)':d=23[bgm];"
        "[vo][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )

    cmd_final = [
        FFMPEG_EXE, "-y",
        "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-i", "audio/vo.mp3",
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-t", "22.94",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "final_documentary.mp4"
    ]

    print(f"Assembling final video to {FINAL_VIDEO}...")
    subprocess.run(cmd_final, cwd=str(OUT_DIR), check=True)
    print(f"SUCCESS: Final video saved at {FINAL_VIDEO} ({FINAL_VIDEO.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    render()
