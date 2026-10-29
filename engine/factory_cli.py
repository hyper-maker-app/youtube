#!/usr/bin/env python3
"""Standalone Factory CLI for physical execution (Flow CDP + Deepgram + FFmpeg)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

# Ensure engine is on sys.path
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from flow_bridge import execute_grok_flow_production, sanitize_slug

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("factory_cli")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Physical execution factory for Grok Cinematic Studio.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'run' subcommand
    run_parser = subparsers.add_parser("run", help="Run full production from Grok handoff or scene JSON.")
    run_parser.add_argument("--handoff", type=Path, required=True, help="Path to handoff or script JSON file.")
    run_parser.add_argument("--out-dir", type=Path, default=None, help="Output directory for rendered film.")
    run_parser.add_argument("--aspect", choices=["16:9", "9:16"], default="16:9", help="Target aspect ratio.")
    run_parser.add_argument("--dry-run", action="store_true", help="Local lavfi dry-run simulation without network calls.")
    run_parser.add_argument("--no-music", action="store_true", help="Disable background audio bed.")
    run_parser.add_argument("--no-captions", action="store_true", help="Disable burned karaoke subtitles.")
    run_parser.add_argument("--block-duration", type=float, default=6.0, help="Target block clip duration in seconds.")

    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    if args.command == "run":
        if not args.handoff.is_file():
            logger.error(f"Handoff file not found: {args.handoff}")
            return 1

        try:
            data = json.loads(args.handoff.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"Failed to read handoff JSON: {exc}")
            return 1

        title = data.get("title") or data.get("project_title") or args.handoff.stem
        genre = data.get("genre", "Cinematic Fiction")
        scenes = data.get("scenes") or data.get("shots") or []

        if not scenes:
            logger.error("No scenes found in handoff file!")
            return 1

        out_dir = args.out_dir or (Path.cwd() / "out" / sanitize_slug(title))

        final_mp4 = await execute_grok_flow_production(
            project_title=title,
            genre=genre,
            scenes=scenes,
            out_dir=out_dir,
            aspect_ratio=args.aspect,
            dry_run=args.dry_run,
            no_music=args.no_music,
            no_captions=args.no_captions,
            block_duration=args.block_duration,
        )
        print(f"\n[SUCCESS] Final film generated at: {final_mp4}\n")
        return 0

    return 0


def main() -> None:
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
