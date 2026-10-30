"""Grok Imagine Cinematic Studio CLI — Film Production Pipeline Command.

Bridges Grok Studio narrative authoring with Google Flow CDP, Deepgram, and FFmpeg.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel

_TOOLS = Path(__file__).resolve().parents[1]
_ROOT = _TOOLS.parent

# Ensure root and engine are on sys.path
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(_ROOT / "engine"))

from engine.flow_bridge import execute_grok_flow_production, sanitize_slug
from engine.providers.llm.grok import GrokLLMProvider
from engine.services.continuity import EpisodeHandoff, apply_handoff_to_scenes
from engine.services.series_architect import generate_rigor_mortis_episode_01_scenes
from engine.services.text_sanitizer import sanitize_spoken_text
from engine.services.universal_narrative import (
    build_llm_genre_system_prompt,
    detect_genre_archetype,
    generate_universal_scenes,
)
from tools.cli.production import build_production_bible

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("produce_commands")

SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "topic": {"type": "string"},
        "format": {"type": "string", "enum": ["short", "longform"]},
        "mode": {"type": "string", "enum": ["incident", "mechanical", "anatomical", "explorer"]},
        "ending_character_state": {
            "type": "string",
            "description": "Protagonist physical state, clothing damage, and held inventory.",
        },
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "scene_number": {"type": "integer"},
                    "narration": {"type": "string"},
                    "visual_prompt": {"type": "string"},
                    "motion_prompt": {"type": "string"},
                    "camera_scale": {
                        "type": "string",
                        "enum": ["wide", "medium", "close", "macro", "micro", "nano"],
                    },
                    "duration": {"type": "number"},
                },
                "required": [
                    "id",
                    "scene_number",
                    "narration",
                    "visual_prompt",
                    "motion_prompt",
                    "duration",
                ],
            },
        },
    },
    "required": ["title", "topic", "scenes"],
}


def generate_local_3act_scenes(title: str, genre: str, duration: int = 60, aspect: str = "16:9") -> list[dict[str, Any]]:
    """Synthesize structured scenes adhering to the universal 2nd-person retention standard across all genres.

    Invariants:
    - 100% English narration in 2nd-person singular ('You'). Zero 3rd-person narrator.
    - In-media-res crisis hook within the first 3 seconds.
    - Concrete micro-survival & technical mathematics tailored to genre (PSI, ATM, RAM %, dB, bodkin arrows).
    - Atmospheric & situational framing (helmet HUD, peephole, periscope, terminal, arrow slit) to eliminate AI facial uncanny valley.
    - Aspect-ratio tailored smart endings: 16:9 unresolved cliffhangers vs 9:16 seamless audio loops.
    """
    return generate_universal_scenes(title=title, genre=genre, duration=duration, aspect=aspect)


def produce_film(
    title: str = typer.Argument(..., help="Title or central premise of the film"),
    genre: str = typer.Option("Survival Horror", "--genre", "-g", help="Film genre (e.g. Survival Horror, Sci-Fi, Cyberpunk)"),
    engine: str = typer.Option("flow", "--engine", "-e", help="Physical render engine: 'flow' (Google Veo / Imagen 3 CDP) or 'xai'"),
    duration: int = typer.Option(40, "--duration", "-d", help="Target film duration in seconds"),
    aspect: str = typer.Option("16:9", "--aspect", "-a", help="Aspect ratio: '16:9' or '9:16'"),
    voice_provider: str = typer.Option("deepgram", "--voice-provider", "-v", help="Narration provider: 'deepgram', 'voyslity', or 'elevenlabs'"),
    plan_only: bool = typer.Option(False, "--plan-only", "-p", help="Generate production bible, character DNA, and handoff scenes without rendering"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run local offline simulation without remote provider calls"),
    no_music: bool = typer.Option(False, "--no-music", help="Disable background audio bed"),
    no_captions: bool = typer.Option(False, "--no-captions", help="Disable burned Libass karaoke subtitles"),
    hero_plate: Optional[str] = typer.Option(None, "--hero-plate", help="Path to character hero plate image for continuity QA"),
    rebuild: bool = typer.Option(False, "--rebuild", "-r", help="Bypass cached handoff and re-generate canonical 3-act UDSE screenplay"),
    director_mode: bool = typer.Option(True, "--director-mode/--no-director-mode", help="Enable Grok 4.6 Autonomous Director Engine with UDSE v4.2"),
    episode: int = typer.Option(1, "--episode", help="Episode number in series (default: 1)"),
    continue_from: Optional[str] = typer.Option(None, "--continue-from", help="Directory or path to previous episode continuity handoff to thaw state"),
    simulate_defect_block: Optional[int] = typer.Option(None, "--simulate-defect-block", help="Simulate a visual continuity breach on block N to test Director Agent HEAL re-generation loop"),
) -> None:
    """Produce a complete cinematic film: Grok Studio AI Brain -> Flow CDP Video -> Voice Provider -> FFmpeg Assembly."""
    slug = sanitize_slug(title)
    out_dir = _ROOT / "out" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    sequences_dir = _ROOT / "sequences"
    sequences_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold cyan]Grok Imagine Cinematic Studio v4.0[/bold cyan] [yellow]x[/yellow] [bold green]Google Flow CDP Engine[/bold green]\n\n"
        f"[FILM] [b]Project Title:[/b] {title}\n"
        f"[GENRE] [b]Genre:[/b] {genre}\n"
        f"[ENGINE] [b]Physical Engine:[/b] {engine.upper()}\n"
        f"[VOICE] [b]Voice Provider:[/b] {voice_provider.upper()} (100% English Invariant)\n"
        f"[DIRECTOR] [b]Director Mode:[/b] {director_mode} (UDSE v4.2 & HEAL/CANONIZE)\n"
        f"[TIME] [b]Target Duration:[/b] {duration}s ({aspect})\n"
        f"[DRY-RUN] [b]Dry Run:[/b] {dry_run}",
        title="[FILM] Production Launch v4.0",
        border_style="cyan"
    ))

    # Phase 1: Grok Studio Brain (Production Bible & Scenario Generation)
    console.print("\n[bold yellow][1/3] Activating Grok Studio 25-Agent Core...[/bold yellow]")
    bible = build_production_bible(
        title=title,
        genre=genre,
        target_duration_seconds=duration,
    )
    bible_path = out_dir / "series_bible.json"
    bible_path.write_text(json.dumps(bible, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  + Production Bible locked -> [dim]{bible_path.name}[/dim]")

    scenes: list[dict[str, Any]] = []
    xai_key = os.getenv("XAI_API_KEY", "").strip()
    handoff_path = sequences_dir / f"{slug}_handoff.json"

    # Canonical UDSE v4.2 resolution or explicit --rebuild
    if (rebuild or slug == "project-rigor-mortis-episode-01") and director_mode:
        console.print("  + Compiling Canonical 3-Act UDSE v4.2 Screenplay (9 blocks / 74s / EAB Invariants)...")
        scenes = generate_rigor_mortis_episode_01_scenes()
        duration = int(sum(float(s.get("duration", 8.0)) for s in scenes))
    elif handoff_path.is_file() and handoff_path.stat().st_size > 100:
        try:
            saved_data = json.loads(handoff_path.read_text(encoding="utf-8"))
            if saved_data.get("scenes") and len(saved_data["scenes"]) >= 4:
                scenes = saved_data["scenes"]
                for s in scenes:
                    s["narration"] = sanitize_spoken_text(s.get("narration", ""))
                console.print(f"  + Reusing existing verified screenplay ({len(scenes)} scenes) -> [dim]{handoff_path.name}[/dim]")
        except Exception:
            pass

    archetype = detect_genre_archetype(genre)
    if not scenes and xai_key and not dry_run:
        console.print(f"  + Orchestrating Universal 2nd-Person Screenplay ({archetype.display_name}) via xAI Grok API...")
        try:
            llm = GrokLLMProvider(api_key=xai_key, model="grok-4.20-0309-non-reasoning")
            system_prompt = build_llm_genre_system_prompt(
                title=title,
                genre=genre,
                duration=duration,
                aspect=aspect,
            )
            script_data = asyncio.run(llm.generate_script(
                topic=f"{title} ({genre})",
                system_prompt=system_prompt,
                schema=SCRIPT_SCHEMA,
            ))
            scenes = script_data.get("scenes", [])
            console.print(f"  + Grok authored {len(scenes)} dynamic 2nd-person scenes.")
        except Exception as exc:
            console.print(f"  [yellow]Notice: Grok API call encountered: {exc}. Falling back to Universal Procedural scenes.[/yellow]")
            scenes = generate_universal_scenes(title, genre, duration, aspect=aspect)
    elif not scenes:
        console.print(f"  + Synthesizing Universal 2nd-Person Narrative ({archetype.display_name} Standard)...")
        scenes = generate_universal_scenes(title, genre, duration, aspect=aspect)

    # Sanitize all narration across scenes to guarantee 100% clean spoken audio
    for sc in scenes:
        sc["narration"] = sanitize_spoken_text(sc.get("narration", ""))

    # Thaw continuity if continuing from a previous episode (ADR-090 Standard)
    if continue_from:
        cont_path = Path(continue_from)
        handoff_file = cont_path if cont_path.is_file() else (cont_path / "episode_handoff.json")
        if handoff_file.is_file():
            try:
                thawed_handoff = EpisodeHandoff.thaw(handoff_file)
                scenes = apply_handoff_to_scenes(scenes, thawed_handoff)
                console.print(f"  [green]+ Thawed EpisodeHandoff from Episode {thawed_handoff.from_episode} (Hash: {thawed_handoff.continuity_hash[:10]}...)[/green]")
            except Exception as exc:
                console.print(f"  [yellow]Notice: Could not thaw EpisodeHandoff from {handoff_file}: {exc}[/yellow]")

    # Save handoff packet
    handoff_packet = {
        "title": title,
        "genre": genre,
        "episode": episode,
        "duration": duration,
        "aspect": aspect,
        "scenes": scenes,
    }
    handoff_path = sequences_dir / f"{slug}_handoff.json"
    handoff_path.write_text(json.dumps(handoff_packet, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"  + Handoff Packet sealed -> [dim]{handoff_path}[/dim]")

    if plan_only:
        console.print(Panel(
            f"[bold yellow][PLAN ONLY] Pre-Production Complete[/bold yellow]\n\n"
            f"[BIBLE] [b]Production Bible:[/b] {bible_path}\n"
            f"[HANDOFF] [b]Handoff Scenes:[/b] {handoff_path}\n"
            f"[SCENES] [b]Scene Count:[/b] {len(scenes)} scenes\n\n"
            f"[TIP] To physically produce video, run without --plan-only:\n"
            f"python tools/cinematic_studio_cli.py produce-film \"{title}\" --genre \"{genre}\" --duration {duration}",
            title="[HALT] Ready for Production Review",
            border_style="yellow"
        ))
        return

    # Phase 2: Physical Engine Execution
    if engine.lower() == "flow":
        console.print("\n[bold green][2/3] Dispatching to Physical Execution Factory (Flow CDP + Voice + FFmpeg)...[/bold green]")
        # Resolve Character Hero DNA plate if present
        characters_dir = _ROOT / "characters"
        candidates = [
            Path(hero_plate) if hero_plate else None,
            characters_dir / f"{slug}_hero.jpg",
            characters_dir / f"{slug}_hero.png",
            characters_dir / f"{slug}.jpg",
            characters_dir / f"{slug}.png",
            out_dir / "keyframes" / "hero_plate.jpg",
            out_dir / "keyframes" / "hero_plate.png",
        ]
        resolved_hero_plate = next((p for p in candidates if p and p.is_file() and p.stat().st_size > 500), None)
        if resolved_hero_plate:
            console.print(f"  + Character Hero DNA Plate locked -> [dim]{resolved_hero_plate.name}[/dim]")

        final_mp4 = asyncio.run(execute_grok_flow_production(
            project_title=title,
            genre=genre,
            scenes=scenes,
            out_dir=out_dir,
            aspect_ratio=aspect,
            dry_run=dry_run,
            no_music=no_music,
            no_captions=no_captions,
            block_duration=8.0 if aspect == "16:9" else 4.0,
            voice_provider=voice_provider,
            hero_plate_path=resolved_hero_plate,
            director_mode=director_mode,
            episode_num=episode,
            simulate_defect_block=simulate_defect_block,
        ))
        console.print(Panel(
            f"[bold green][DONE] Film Successfully Produced![/bold green]\n\n"
            f"[VIDEO] [b]Final MP4:[/b] {final_mp4}\n"
            f"[OUT] [b]Production Assets:[/b] {out_dir}",
            title="[COMPLETE] Production Complete",
            border_style="green"
        ))
    else:
        console.print(f"\n[yellow]Engine '{engine}' selected. Use xAI imagine tools to render handoff: {handoff_path}[/yellow]")


def register(app: typer.Typer) -> None:
    """Register 'produce-film' command to the root Typer CLI."""
    app.command(
        name="produce-film",
        help="Produce a complete film: Grok Studio AI Brain -> Flow CDP Video -> Deepgram -> FFmpeg Assembly.",
    )(produce_film)
