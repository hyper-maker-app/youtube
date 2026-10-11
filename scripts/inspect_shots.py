import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open(r'out\the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826\script.json', encoding='utf-8') as f:
    s = json.load(f)

for sh in s.get('shots', []):
    blk = sh.get('block')
    scale = sh.get('scale')
    loc = sh.get('location_id')
    subj = sh.get('subject_id')
    sec = sh.get('secondary_subject_ids')
    trans = sh.get('transition_kind')
    endpt = sh.get('endpoint_mode')
    dom = sh.get('visual_domain')
    motion = sh.get('motion_prompt', '')[:120]
    print(f"Block {blk:02d} | scale: {scale:<6} | loc: {loc:<20} | subj: {subj:<15} | sec: {str(sec):<25} | trans: {trans:<15} | endpt: {endpt}")
    print(f"   Motion: {motion}")
    print(f"   Start: {sh.get('start_image_prompt')[:120]}...")
    print(f"   Proof: {sh.get('proof_on_screen')}")
    print("-" * 100)
