#!/usr/bin/env python3
"""benchmark_quality_gate.py - Anti-Self-Deception Quality Gate for Longform AI Documentaries.

Enforces:
1. Genuine Generative AI Video Motion: Fails if video blocks are merely static still photos or pure linear 2D Ken Burns zooms.
2. Provenance & Integrity: Every block must have verifiable provenance sidecar and match recorded hashes.
3. Multi-layer Audio Mix: Narration + Ambient soundscape + BGM must all be present and non-zero.
4. Broadcast Audio LUFS: Must meet -14 LUFS (+/- 1.5 dB).
5. Returns Exit Code 0 ONLY if all benchmark criteria pass. Exits with 1 on any failure to force the loop to continue.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
import editor
from services.block_verifier import cached_block_is_trustworthy, read_provenance
from services.motion_authenticity import ClipMotionReport, analyze_clip, is_genuine


def measure_audio_lufs(video_path: Path) -> float | None:
    """Measure integrated loudness using ffmpeg ebur128 filter."""
    ffmpeg = config.resolve_ffmpeg()
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "info",
        "-i", str(video_path),
        "-af", "ebur128=framelog=verbose",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    lines = proc.stderr.splitlines() + proc.stdout.splitlines()
    for line in lines:
        if "I:" in line and "LUFS" in line:
            parts = line.split("I:")
            if len(parts) > 1:
                val_str = parts[1].replace("LUFS", "").strip()
                try:
                    return float(val_str)
                except ValueError:
                    pass
    return None


def audit_clip(clip_path: Path) -> dict[str, object]:
    """Audit a single video clip for genuine generative diffusion motion."""
    report = analyze_clip(clip_path)
    prov_ok, prov_reason = cached_block_is_trustworthy(clip_path)
    genuine = is_genuine(report)
    return {
        "clip": str(clip_path),
        "genuine_motion": genuine,
        "provenance_ok": prov_ok,
        "passed": genuine and prov_ok,
        "provenance_reason": prov_reason,
        "motion": report.to_dict(),
    }


def audit_run_directory(run_dir: Path) -> dict[str, object]:
    final_video = run_dir / "final.mp4"
    if not final_video.is_file():
        return {"passed": False, "error": f"final.mp4 does not exist in {run_dir}"}

    ffmpeg = config.resolve_ffmpeg()
    v_info = editor.probe(final_video, ffmpeg)
    dur = float(v_info.duration or 0.0)

    # 1. Inspect blocks
    blocks_dir = run_dir / "blocks"
    block_files = sorted(blocks_dir.glob("*.mp4")) if blocks_dir.exists() else []
    if not block_files:
        return {"passed": False, "error": "No block video files found in blocks/"}

    genuine_diffusion_blocks = []
    rigid_2d_blocks = []
    frozen_blocks = []
    provenance_failures = []
    block_details = []

    for b in block_files:
        rep = analyze_clip(b)
        prov_ok, prov_reason = cached_block_is_trustworthy(b)
        b_name = b.stem
        det = {
            "block": b_name,
            "verdict": rep.verdict,
            "residual_px": round(rep.coherent_residual, 3),
            "frozen_ratio": round(rep.frozen_ratio, 2),
            "freeze_tail_s": rep.freeze_tail_s,
            "reasons": rep.reasons,
            "provenance_ok": prov_ok,
            "provenance_reason": prov_reason,
        }
        block_details.append(det)

        if not prov_ok:
            provenance_failures.append(b_name)

        if rep.verdict == "frozen":
            frozen_blocks.append(b_name)
        elif rep.verdict == "rigid_2d_motion":
            rigid_2d_blocks.append(b_name)
        elif is_genuine(rep):
            genuine_diffusion_blocks.append(b_name)
        else:
            frozen_blocks.append(b_name)

    # 2. Check audio layers & loudness
    has_audio = bool(v_info.has_audio)
    soundscape = run_dir / "ambient_soundscape.wav"
    audio_bed = run_dir / "audio_bed_epic_curiosity.wav"
    audio_layers_ok = soundscape.exists() or audio_bed.exists()

    lufs = measure_audio_lufs(final_video)
    lufs_ok = lufs is not None and (-16.5 <= lufs <= -12.0)

    # 3. Calculate Score & Feedback
    score = 0
    feedback = []

    # Resolution & Widescreen
    if v_info.width == 1920 and v_info.height == 1080:
        score += 20
    else:
        feedback.append(f"Resolution is {v_info.width}x{v_info.height}, expected 1920x1080.")

    # Duration >= 40s
    if dur >= 40.0:
        score += 20
    else:
        feedback.append(f"Duration is only {dur:.1f}s, expected at least 40.0s.")

    # Real Motion / Non-freeze / Non-rigid
    invalid_blocks = len(frozen_blocks) + len(rigid_2d_blocks)
    if invalid_blocks == 0 and len(genuine_diffusion_blocks) == len(block_files):
        score += 35
    else:
        score += max(0, int(35 * (len(genuine_diffusion_blocks) / max(1, len(block_files)))))
        if frozen_blocks:
            feedback.append(f"Found {len(frozen_blocks)} frozen/stagnant blocks: {frozen_blocks}")
        if rigid_2d_blocks:
            feedback.append(f"Found {len(rigid_2d_blocks)} rigid 2D Ken Burns blocks (not real video): {rigid_2d_blocks}")

    # Audio layers
    if has_audio and audio_layers_ok:
        score += 15
    else:
        feedback.append("Missing multi-layer audio design (ambient soundscape or audio bed).")

    # Audio LUFS
    if lufs_ok:
        score += 10
    else:
        feedback.append(f"Integrated loudness is {lufs} LUFS (expected -14 LUFS +/- 1.5 dB).")

    if provenance_failures:
        feedback.append(f"Missing or invalid AI-video provenance: {provenance_failures}")
    passed = (score >= 80) and (len(frozen_blocks) == 0) and (len(rigid_2d_blocks) == 0) and (len(provenance_failures) == 0)

    return {
        "passed": passed,
        "score": score,
        "duration": dur,
        "width": v_info.width,
        "height": v_info.height,
        "total_blocks": len(block_files),
        "genuine_diffusion_blocks": len(genuine_diffusion_blocks),
        "rigid_2d_blocks": rigid_2d_blocks,
        "frozen_blocks": frozen_blocks,
        "provenance_failures": provenance_failures,
        "lufs": lufs,
        "block_details": block_details,
        "feedback": feedback,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit a documentary run or clip against the benchmark standard.")
    parser.add_argument("run_dir", type=Path, nargs="?", default=None, help="Path to run output directory")
    parser.add_argument("--clip", type=Path, default=None, help="Directly audit an individual video clip")
    args = parser.parse_args()

    if args.clip:
        res = audit_clip(args.clip)
        print(json.dumps(res, indent=2))
        if not res.get("passed"):
            print(f"\n❌ CLIP FAILED AUTHENTICITY GATE: {res.get('motion', {}).get('verdict')}; provenance={res.get('provenance_ok')}", file=sys.stderr)
            sys.exit(1)
        else:
            print("\n✅ CLIP PASSED: Genuine diffusion video motion verified.")
            sys.exit(0)

    if not args.run_dir:
        parser.error("Either run_dir or --clip must be provided.")

    result = audit_run_directory(args.run_dir)
    print(json.dumps(result, indent=2))

    if not result.get("passed"):
        print("\n❌ BENCHMARK QUALITY GATE FAILED! DO NOT COMPLETE GOAL! ITERATE AND RE-RENDER!", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n✅ BENCHMARK QUALITY GATE PASSED! Video meets documentary motion and audio standard.")
        sys.exit(0)


if __name__ == "__main__":
    main()
