"""CLI for the provider-factory YouTube Shorts pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from pipeline import RunContext, atomic_write_json, make_run_dir, provider_timeline, run
from providers.bundles import production_bundle
from services.topic_selection import select_topic
from services.topic_selection import select_topic_with_llm
from providers.factory import get_llm_provider
from services.mode_profile import ANATOMICAL, EXPLORER, INCIDENT, MECHANICAL, detect_mode, mode_from_name
from timeline import TimelinePlan


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a provider-native vertical YouTube Short.")
    parser.add_argument("--topic", help="Topic for a new run. When omitted, a selected production route uses autonomous topic selection.")
    parser.add_argument("--auto-topic", action="store_true", help="Select a documented non-duplicate topic without asking for one.")
    parser.add_argument("--resume", help="Existing run directory under out/ or an absolute run directory.")
    parser.add_argument("--lang", default=config.DEFAULT_LANG, choices=list(config.LANG_PROFILES))
    parser.add_argument("--music", help="Optional local music path.")
    parser.add_argument("--no-captions", dest="captions", action="store_false")
    parser.add_argument("--no-music", action="store_true", help="Disable background music entirely.")
    parser.add_argument("--dry-run", action="store_true", help="Use local FFmpeg fixtures only; no LLM/image/voice/video API call is made.")
    parser.add_argument("--llm", default=None, help="LLM provider override; default is LLM_PROVIDER from .env.")
    parser.add_argument("--video", default=None, help="Video provider override; default is VIDEO_PROVIDER from .env.")
    parser.add_argument("--voice", default=None, help="Voice provider override; default is VOICE_PROVIDER from .env.")
    parser.add_argument("--image", default=None, help="Image provider override; default is IMAGE_PROVIDER from .env.")
    parser.add_argument(
        "--test-blocks", type=int, metavar="N",
        help="Generate and edit only the first N native 4.0-second blocks (1-8); cannot be combined with --resume.",
    )
    parser.add_argument("--mode", choices=["anatomical", "incident", "mechanical", "explorer", "auto"], default="auto",
                        help="Production mode: anatomical (medical), incident (news event), mechanical (physics/engineering), explorer (field investigation), auto (detect from topic)")
    parser.add_argument(
        "--stage", choices=["all", "script", "narration", "roster", "keyframes", "video", "edit"], default="all",
        help="Run pipeline up to the specified stage (e.g. keyframes skips video and edit).",
    )
    parser.add_argument(
        "--skip-video", action="store_true",
        help="Skip video generation and editing (equivalent to --stage keyframes).",
    )
    parser.add_argument(
        "--blocks", type=int, metavar="N", default=None,
        help="Explicit block count for new runs (e.g. 15 for 60s 1-minute longform, 28 for full longform).",
    )
    parser.add_argument("--hybrid", action="store_true", default=False, help="Enable 2.5D Ken Burns hybrid mode for B-roll (defaults to False for full AI video).")
    parser.add_argument("--format", choices=["short", "longform"], default="short", help="Script format")
    parser.set_defaults(captions=config.CAPTIONS_ENABLED)
    return parser.parse_args(argv)


ROUTE_QUESTION = "Hangi video üretim yöntemini kullanalım? [1] Vertex AI (resmî API) / [2] Flow Agent (GitHub repo/CLI)"


def _route_from_interaction() -> str:
    """Ask the sole permitted production question, or provide one-line noninteractive status."""
    if not sys.stdin.isatty():
        raise SystemExit(ROUTE_QUESTION)
    print(ROUTE_QUESTION)
    response = input().strip()
    if response == "1":
        return "vertex"
    if response == "2":
        return "flow"
    raise SystemExit("Production route must be 1 or 2.")


def _resume_script(path: Path) -> tuple[str, TimelinePlan | None, str | None]:
    script_path = path / "script.json"
    if not script_path.exists():
        raise SystemExit(f"--resume requires {script_path}")
    payload = json.loads(script_path.read_text(encoding="utf-8"))
    raw = payload.get("timeline")
    persisted_mode = str(payload.get("mode")) if payload.get("mode") else None
    return str(payload.get("topic") or "resumed"), (TimelinePlan.from_dict(raw) if isinstance(raw, dict) else None), persisted_mode


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.format == "longform":
        os.environ["LONGFORM_MODE"] = "1"
        config.LONGFORM_MODE = True
        config.WIDTH = config.LONGFORM_WIDTH
        config.HEIGHT = config.LONGFORM_HEIGHT
        config.ASPECT_RATIO_STRING = "16:9"
        config.COMPOSITION_STRING = "16:9 horizontal composition"
        config.ORIENTATION_STRING = "landscape orientation"
        config.ASPECT_RATIO_FULL_STRING = "16:9 horizontal aspect ratio"
        if args.blocks is None:
            args.blocks = 15
        config.LONGFORM_HYBRID_MODE = bool(args.hybrid)
    if args.skip_video:
        args.stage = "keyframes"
    if (args.skip_video or args.stage in {"keyframes", "roster", "script", "narration"}) and not args.video:
        args.video = "vertex"
    # A dry run is local-only, so it has no billable route and never prompts. A real new
    # run with no explicit --video asks exactly the user-facing route question above.
    if not args.resume and not args.video and not args.dry_run:
        args.video = production_bundle(_route_from_interaction()).video_provider
    bundle = None
    if args.video and args.video.casefold().replace("-", "_") in {"vertex", "vertex_veo", "flow", "flow_agent"}:
        bundle = production_bundle(args.video, args.image)
        args.video, args.image = bundle.video_provider, bundle.image_provider
    if args.music and not Path(args.music).is_file():
        raise SystemExit(f"Music file not found: {args.music}")
    if args.test_blocks is not None and not 1 <= args.test_blocks <= 8:
        raise SystemExit("--test-blocks must be between 1 and 8")
    if args.test_blocks is not None and args.resume:
        raise SystemExit("--test-blocks cannot be combined with --resume; a persisted timeline is authoritative.")
    try:
        ffmpeg = config.resolve_ffmpeg()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    selected_topic: dict | None = None
    if not args.resume and not args.topic:
        # Dry runs are strictly local.  Production selection uses the already explicit
        # LLM route and therefore its configured Gemini text model/provider boundary.
        selected_topic = select_topic(config.ROOT / "pipeline_stats.db") if args.dry_run else asyncio.run(
            select_topic_with_llm(config.ROOT / "pipeline_stats.db", get_llm_provider(args.llm))
        )
        args.topic = str(selected_topic["selected_topic"])
    out_dir = make_run_dir(args.topic or "resumed", args.resume)
    if not selected_topic and not args.resume:
        selected_topic = {
            "selected_topic": args.topic,
            "mode": "manual",
            "reason": "user supplied topic",
        }
    if selected_topic:
        atomic_write_json(out_dir / "topic_selection.json", selected_topic)
    persisted_topic, persisted_timeline, persisted_mode = _resume_script(out_dir) if args.resume else (args.topic, None, None)
    if args.resume and persisted_mode == "explorer":
        os.environ["LONGFORM_MODE"] = "1"
        config.LONGFORM_MODE = True
        config.WIDTH = config.LONGFORM_WIDTH
        config.HEIGHT = config.LONGFORM_HEIGHT
        config.ASPECT_RATIO_STRING = "16:9"
        config.COMPOSITION_STRING = "16:9 horizontal composition"
        config.ORIENTATION_STRING = "landscape orientation"
        config.ASPECT_RATIO_FULL_STRING = "16:9 horizontal aspect ratio"
        args.format = "longform"
    # A persisted plan is authoritative.  A real new run begins with an eight-shot
    # screenplay outline, then locks a 6..13 block plan from measured narration before
    # it requests a keyframe; --resume never recalculates that plan.
    timeline = persisted_timeline or provider_timeline(args.test_blocks, blocks=args.blocks)
    topic = args.topic or persisted_topic or "resumed"

    # Resolve mode profile
    if args.mode == "incident":
        profile_mode = INCIDENT
    elif args.mode == "anatomical":
        profile_mode = ANATOMICAL
    elif args.mode == "mechanical":
        profile_mode = MECHANICAL
    elif args.mode == "explorer":
        profile_mode = EXPLORER
    elif args.resume and persisted_mode:
        try:
            profile_mode = mode_from_name(persisted_mode)
        except KeyError:
            profile_mode = detect_mode(topic)
    elif args.format == "longform":
        profile_mode = EXPLORER
    else:
        profile_mode = detect_mode(topic)

    if not args.resume:
        atomic_write_json(out_dir / "run_manifest.json", {
            "schema_version": 1, "topic": topic, "timeline": timeline.to_dict(),
            "mode": profile_mode.name,
            "production_bundle": bundle.to_dict() if bundle else None,
            "test_blocks": args.test_blocks, "dry_run": bool(args.dry_run),
        })
    print(f"topic   : {topic}")
    run_mode_label = f"test-blocks={args.test_blocks}" if args.test_blocks is not None else "full"
    timeline_label = "persisted" if args.resume or args.test_blocks is not None else "provisional; voice will lock 6-13 blocks"
    print(f"timeline: {timeline.block_count} x {timeline.native_clip_duration:.1f}s = {timeline.total_duration:.1f}s footage + {config.TAIL_HOLD:.1f}s tail ({run_mode_label}; {timeline_label})")
    print(f"mode    : {profile_mode.name}")
    print(f"providers: llm={args.llm or config.LLM_PROVIDER}, image={args.image or config.IMAGE_PROVIDER}, voice={args.voice or config.VOICE_PROVIDER}, video={args.video or config.VIDEO_PROVIDER}")
    print(f"ffmpeg  : {ffmpeg}")

    ctx = RunContext(
        topic=topic, out_dir=out_dir, lang=args.lang, mode=profile_mode, music=Path(args.music) if args.music else None,
        no_music=args.no_music, captions=args.captions, dry_run=args.dry_run, resumed=bool(args.resume), timeline=timeline,
        llm_provider=args.llm, video_provider=args.video, voice_provider=args.voice, image_provider=args.image,
        test_blocks=args.test_blocks, production_bundle=bundle.to_dict() if bundle else None,
        stage=args.stage, skip_video=args.skip_video, format=args.format,
    )
    run(ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
