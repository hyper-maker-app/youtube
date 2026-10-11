from pathlib import Path
import json

runs = [
    r'out\the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826',
    r'out\why-your-eyes-never-freeze-in-sub-zero-air_20260911_111329',
    r'out\the-passenger-who-tried-to-open-an-airplane-door_20260910_134812',
    r'out\the-lighthouse-that-still-signals-from-an-empty-_20260909_100223',
    r'out\why-your-stomach-doesn-t-dissolve-itself_20260908_135623'
]

for r in runs:
    p = Path(r)
    script_p = p / 'script.json'
    final_p = p / 'final.mp4'
    if p.exists() and script_p.exists():
        with open(script_p, encoding='utf-8') as f:
            s = json.load(f)
        print("Folder:", p.name)
        print("  Topic:", s.get("topic"))
        print("  Mode:", s.get("mode"))
        print("  Final:", final_p.exists(), f"({final_p.stat().st_size} bytes)" if final_p.exists() else "")
        print("  Shots:", len(s.get("shots", [])))
        print("-" * 60)
