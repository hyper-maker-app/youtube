"""Safe workspace cleaner for YouTube Shorts automation repository.

Targets only verified temporary artifacts:
- 25 large .zip backup packages in root (~2.12 GB)
- Orphan temp images, test SFX audio, and legacy lighthouse logs in root (~8.1 MB)
- One-off throwaway patch/study scripts in root

STRICT SAFETY INVARIANTS:
- NEVER deletes MCP servers (_decision_mcp.py, _media_mcp.py, _pipeline_mcp.py, _research_mcp.py)
- NEVER deletes .env files, git configuration, core pipeline code, services, or assets
- Defaults to dry-run (simulation) unless --execute is explicitly passed.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Specific safe targets in root
TARGET_ZIP_NAMES = {
    "youtube_shorts_production_full.zip",
    "youtube_shorts_production_112826_FULL.zip",
    "youtube_shorts_rejected_keyframes_20260912.zip",
    "youtube_shorts_pipeline_and_prompts_lightweight.zip",
    "pilot_incident_full_video_run.zip",
    "youtube_shorts_llm_bundle_20260912.zip",
    "pilot_incident_final_video_only.zip",
    "youtube_shorts_admitted_keyframes_20260912.zip",
    "pilot_incident_rejected_keyframes.zip",
    "pilot_incident_rerun_and_control_20260912.zip",
    "pilot_incident_rerun_and_control_rejected_20260912.zip",
    "pilot_incident_veo_blocks_part2.zip",
    "pilot_incident_veo_blocks_part1.zip",
    "pilot_incident_roster_cards.zip",
    "youtube_shorts_production_112826_LLM_READY.zip",
    "pilot_incident_admitted_keyframes.zip",
    "pilot_incident_audio_and_soundtrack.zip",
    "youtube_shorts_production_112826_MINI.zip",
    "youtube_shorts_code_and_prompts_mini.zip",
    "zack_d_project_and_latest_run_for_llm.zip",
    "youtube_shorts_llm_complete_bundle_20260912.zip",
    "youtube_shorts_llm_bundle_code_and_manifests_20260912.zip",
    "youtube_pipeline_diagnostics.zip",
    "youtube_pipeline_dual_modality_v2.zip",
}

TARGET_ORPHAN_FILES = {
    "clean_salt_sheet.png",
    "temp_b4_end.png",
    "temp_b5_1s.png",
    "temp_b5_start.png",
    "test_kf07.png",
    "test_elevenlabs_sfx.mp3",
    "test_elevenlabs_sfx.wav",
    "test_elevenlabs_sfx_norm.wav",
    "video_fixes.diff",
}

TARGET_RETIRED_SCRIPTS = {
    "fix_config.py",
    "append_compiler.py",
    "chat.py",
    "vertex_veo_smoke_test.py",
    "_gen_scripts.py",
    "_prompt_study.py",
}

PROTECTED_MCP_SERVERS = {
    "_decision_mcp.py",
    "_media_mcp.py",
    "_pipeline_mcp.py",
    "_research_mcp.py",
}


def scan_unnecessary_files() -> list[tuple[Path, int]]:
    candidates: list[tuple[Path, int]] = []
    
    # 1. Zip archives in root
    for p in ROOT.glob("*.zip"):
        if p.name in TARGET_ZIP_NAMES:
            candidates.append((p, p.stat().st_size))
            
    # 2. Orphan media & diff
    for name in TARGET_ORPHAN_FILES:
        p = ROOT / name
        if p.is_file():
            candidates.append((p, p.stat().st_size))
            
    # 3. Lighthouse logs in root
    for p in ROOT.glob("lighthouse_*.log"):
        candidates.append((p, p.stat().st_size))
        
    # 4. Retired scratch scripts
    for name in TARGET_RETIRED_SCRIPTS:
        p = ROOT / name
        if p.is_file():
            candidates.append((p, p.stat().st_size))

    # Safety assertion: MCP servers never in candidates
    for p, _ in candidates:
        if p.name in PROTECTED_MCP_SERVERS:
            raise RuntimeError(f"FATAL: Attempted to clean protected MCP file: {p.name}")

    return sorted(candidates, key=lambda x: x[1], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean verified unnecessary workspace files.")
    parser.add_argument("--execute", action="store_true", help="Permanently delete verified files. Defaults to dry-run.")
    args = parser.parse_args()

    files = scan_unnecessary_files()
    total_bytes = sum(sz for _, sz in files)
    total_mb = total_bytes / (1024 * 1024)

    mode_label = "EXECUTION (DELETING)" if args.execute else "DRY-RUN (SIMULATION ONLY)"
    print(f"=== Workspace Cleanup Tool [{mode_label}] ===")
    print(f"Found {len(files)} target files totaling {total_mb:.2f} MB (~{total_mb / 1024:.2f} GB)\n")

    for p, sz in files:
        rel = p.relative_to(ROOT)
        print(f"  [{sz / (1024*1024):8.2f} MB] {rel}")

    if not args.execute:
        print("\n[!] No files were modified. To delete these files, run:")
        print("    python scripts/clean_workspace.py --execute")
        return 0

    print("\nDeleting files...")
    deleted_count = 0
    deleted_bytes = 0
    for p, sz in files:
        try:
            p.unlink()
            deleted_count += 1
            deleted_bytes += sz
        except OSError as exc:
            print(f"  [ERROR] Could not delete {p.name}: {exc}")

    print(f"\n[OK] Successfully cleaned {deleted_count} files, freed {deleted_bytes / (1024*1024):.2f} MB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
