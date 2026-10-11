import zipfile
from pathlib import Path

root = Path('.')
run_dir = root / 'out' / 'the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826'

# 1. Karakter & Ortam Kartları (roster/*.png)
zip_roster = root / 'pilot_incident_roster_cards.zip'
roster_files = sorted((run_dir / 'roster').glob('*.png'))
with zipfile.ZipFile(zip_roster, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in roster_files:
        z.write(f, f'roster/{f.name}')
print(f'1. {zip_roster.name}: {zip_roster.stat().st_size / (1024*1024):.2f} MB ({len(roster_files)} dosya)')

# 2. Onaylanan Kilit Kareler (keyframes/*.png)
zip_kf = root / 'pilot_incident_admitted_keyframes.zip'
kf_files = sorted((run_dir / 'keyframes').glob('*.png'))
with zipfile.ZipFile(zip_kf, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in kf_files:
        z.write(f, f'keyframes/{f.name}')
print(f'2. {zip_kf.name}: {zip_kf.stat().st_size / (1024*1024):.2f} MB ({len(kf_files)} dosya)')

# 3. Ham Sesler & Audio Bed (*.wav, *.mp3, sfx_cache)
zip_audio = root / 'pilot_incident_audio_and_soundtrack.zip'
audio_files = []
# wav and mp3 in root of run
for ext in ('*.wav', '*.mp3'):
    audio_files.extend(run_dir.glob(ext))
# audio subfolder (vo.mp3)
if (run_dir / 'audio').exists():
    audio_files.extend((run_dir / 'audio').glob('*.*'))
# sfx_cache
if (run_dir / 'sfx_cache').exists():
    audio_files.extend((run_dir / 'sfx_cache').glob('*.*'))

with zipfile.ZipFile(zip_audio, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in audio_files:
        rel = f.relative_to(run_dir)
        z.write(f, str(rel))
print(f'3. {zip_audio.name}: {zip_audio.stat().st_size / (1024*1024):.2f} MB ({len(audio_files)} dosya)')

# 4. JSON Manifestoları, Promptlar ve Kodlar
zip_manifests = root / 'pilot_incident_manifests_and_code.zip'
manifest_files = []
for fname in ['script.json', 'prompt_manifest.json', 'run_manifest.json', 'asset_roster.json', 'refs.json', 'metadata.json', 'metadata.txt', 'release_report.json', 'captions.ass', 'words.json', 'voice_manifest.json', 'topic_selection.json', 'research.json', 'state.json', '_filtergraph.txt', 'ATTRIBUTIONS.txt']:
    fp = run_dir / fname
    if fp.exists():
        manifest_files.append((fp, fname))

# keyframe reviews
if (run_dir / 'keyframe_reviews').exists():
    for rev in sorted((run_dir / 'keyframe_reviews').glob('*.json')):
        manifest_files.append((rev, f'keyframe_reviews/{rev.name}'))

# terminal output log & diffs
if (run_dir / 'run_output.txt').exists():
    manifest_files.append((run_dir / 'run_output.txt', 'run_output.txt'))
if (root / 'video_fixes.diff').exists():
    manifest_files.append((root / 'video_fixes.diff', 'video_fixes.diff'))
if (root / 'KEYFRAME_ADMISSION_AUDIT_REPORT.md').exists():
    manifest_files.append((root / 'KEYFRAME_ADMISSION_AUDIT_REPORT.md', 'KEYFRAME_ADMISSION_AUDIT_REPORT.md'))
if (root / 'KEYFRAME_ADMISSION_AUDIT_REPORT.json').exists():
    manifest_files.append((root / 'KEYFRAME_ADMISSION_AUDIT_REPORT.json', 'KEYFRAME_ADMISSION_AUDIT_REPORT.json'))

with zipfile.ZipFile(zip_manifests, 'w', zipfile.ZIP_DEFLATED) as z:
    for src, arcname in manifest_files:
        z.write(src, arcname)
print(f'4. {zip_manifests.name}: {zip_manifests.stat().st_size / 1024:.2f} KB ({len(manifest_files)} dosya)')
