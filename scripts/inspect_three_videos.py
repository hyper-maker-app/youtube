import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

dirs = [
    ("Video 1 [Incident]: The Pilot Who Got Sucked Out", Path(r"out\the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826")),
    ("Video 2 [Incident/Mechanical]: The Passenger Who Tried to Open Airplane Door", Path(r"out\the-passenger-who-tried-to-open-an-airplane-door_20260910_152208")),
    ("Video 3 [Anatomical]: Why Your Eyes Never Freeze", Path(r"out\why-your-eyes-never-freeze-in-sub-zero-air_20260911_111844")),
    ("Video 3-Alt [Anatomical]: Why Your Stomach Doesn't Dissolve Itself", Path(r"out\why-your-stomach-doesn-t-dissolve-itself_20260908_135621")),
]

for title, p in dirs:
    print("=" * 80)
    print(title)
    print("=" * 80)
    script_p = p / "script.json"
    if not script_p.exists():
        print("Script not found at", script_p)
        continue
    with open(script_p, encoding="utf-8") as f:
        s = json.load(f)
    print("Topic:", s.get("topic"))
    print("Mode:", s.get("mode"))
    shots = s.get("shots", [])
    print(f"Total Shots: {len(shots)}")
    for sh in shots:
        print(f"  Shot {sh.get('block'):02d} | scale={sh.get('scale'):<6} | trans={sh.get('transition_kind'):<16} | endpt={sh.get('endpoint_mode'):<10} | loc={sh.get('location_id')}")
