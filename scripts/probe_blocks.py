import subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

ffmpeg = config.resolve_ffmpeg()
out_dir = Path(r"out\the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826\blocks")

for b in range(1, 13):
    blk = out_dir / f"block{b:02d}.mp4"
    # probe duration and frames
    cmd = [ffmpeg, "-i", str(blk)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in res.stderr.splitlines():
        if "Duration:" in line or "Stream #0:0" in line:
            print(f"Block {b:02d}: {line.strip()}")
