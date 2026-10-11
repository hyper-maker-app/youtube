import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

ffmpeg = config.resolve_ffmpeg()
out_dir = Path(r"out\the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826\blocks")
tmp_dir = Path("tmp")
tmp_dir.mkdir(exist_ok=True)

blocks_to_check = [1, 2, 3, 5, 7, 9, 11]
for b in blocks_to_check:
    blk_path = out_dir / f"block{b:02d}.mp4"
    if blk_path.exists():
        frame_path = tmp_dir / f"block{b:02d}_mid.png"
        cmd = [ffmpeg, "-ss", "2.0", "-i", str(blk_path), "-vframes", "1", "-y", str(frame_path)]
        subprocess.run(cmd, capture_output=True)
        print(f"Extracted: {frame_path} ({frame_path.stat().st_size} bytes)")
