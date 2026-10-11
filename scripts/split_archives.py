import zipfile
from pathlib import Path

root = Path('.')
run_dir = root / 'out' / 'the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826'

# 1. Veo Blocks Part 1 (block01 to block06)
zip_veo_pt1 = root / 'pilot_incident_veo_blocks_part1.zip'
blocks_p1 = [run_dir / 'blocks' / f'block{i:02d}.mp4' for i in range(1, 7)]
with zipfile.ZipFile(zip_veo_pt1, 'w', zipfile.ZIP_DEFLATED) as z:
    for b in blocks_p1:
        if b.exists():
            z.write(b, f'blocks/{b.name}')
print(f'1. {zip_veo_pt1.name}: {zip_veo_pt1.stat().st_size / (1024*1024):.2f} MB ({len(blocks_p1)} blok)')

# 2. Veo Blocks Part 2 (block07 to block12)
zip_veo_pt2 = root / 'pilot_incident_veo_blocks_part2.zip'
blocks_p2 = [run_dir / 'blocks' / f'block{i:02d}.mp4' for i in range(7, 13)]
with zipfile.ZipFile(zip_veo_pt2, 'w', zipfile.ZIP_DEFLATED) as z:
    for b in blocks_p2:
        if b.exists():
            z.write(b, f'blocks/{b.name}')
print(f'2. {zip_veo_pt2.name}: {zip_veo_pt2.stat().st_size / (1024*1024):.2f} MB ({len(blocks_p2)} blok)')

# 3. Rejected Keyframes
zip_rejected = root / 'pilot_incident_rejected_keyframes.zip'
rej_dir = run_dir / 'rejected'
rej_files = list(rej_dir.rglob('*.png')) if rej_dir.exists() else []
with zipfile.ZipFile(zip_rejected, 'w', zipfile.ZIP_DEFLATED) as z:
    for r in rej_files:
        rel = r.relative_to(rej_dir)
        z.write(r, f'rejected/{rel}')
print(f'3. {zip_rejected.name}: {zip_rejected.stat().st_size / (1024*1024):.2f} MB ({len(rej_files)} dosya)')

# 4. Main package (Clean, without raw blocks and without rejected frames)
zip_main = root / 'pilot_incident_full_video_run.zip'
main_files = []
# Final video
if (run_dir / 'final.mp4').exists():
    main_files.append((run_dir / 'final.mp4', 'final.mp4'))
# Approved keyframes
for kf in sorted((run_dir / 'keyframes').glob('*.png')):
    main_files.append((kf, f'keyframes/{kf.name}'))
# Roster
for r in sorted((run_dir / 'roster').glob('*.png')):
    main_files.append((r, f'roster/{r.name}'))
# Manifests & json
for fname in ['script.json', 'prompt_manifest.json', 'run_manifest.json', 'asset_roster.json', 'refs.json', 'metadata.json', 'metadata.txt', 'release_report.json', 'captions.ass']:
    fp = run_dir / fname
    if fp.exists():
        main_files.append((fp, fname))
# Reviews
for rev in sorted((run_dir / 'keyframe_reviews').glob('*.json')):
    main_files.append((rev, f'keyframe_reviews/{rev.name}'))
# Log & diff
if (run_dir / 'run_output.txt').exists():
    main_files.append((run_dir / 'run_output.txt', 'run_output.txt'))
if (root / 'video_fixes.diff').exists():
    main_files.append((root / 'video_fixes.diff', 'video_fixes.diff'))

with zipfile.ZipFile(zip_main, 'w', zipfile.ZIP_DEFLATED) as z:
    for src, arcname in main_files:
        z.write(src, arcname)
print(f'4. {zip_main.name} (Ana Paket - Ham bloklar ve retler çıkarılmış): {zip_main.stat().st_size / (1024*1024):.2f} MB ({len(main_files)} dosya)')
