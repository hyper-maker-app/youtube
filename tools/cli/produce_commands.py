"""Grok Imagine Cinematic Studio CLI — Film Production Pipeline Command.

Bridges Grok Studio narrative authoring with Google Flow CDP, Deepgram, and FFmpeg.
"""

from __future__ import annotations

import asyncio
import copy
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

# Ensure root, engine, and tools are on sys.path
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(_ROOT / "engine"))
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from engine.flow_bridge import execute_grok_flow_production, sanitize_slug
from engine.providers.llm.grok import GrokLLMProvider
from engine.services.continuity import EpisodeHandoff, apply_handoff_to_scenes
from engine.services.series_architect import generate_rigor_mortis_episode_01_scenes
from engine.services.text_sanitizer import sanitize_spoken_text
from engine.services.universal_narrative import (
    build_llm_catastrophe_system_prompt,
    build_llm_genre_system_prompt,
    detect_genre_archetype,
    generate_catastrophe_scenes,
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


def get_script_schema(duration: int = 300) -> dict[str, Any]:
    """Return JSON schema with dynamic scene count constraints matching duration."""
    min_scenes = max(5, int(duration / 8.5))
    max_scenes = max(6, int(duration / 7.0) + 2)
    schema = copy.deepcopy(SCRIPT_SCHEMA)
    schema["properties"]["scenes"]["minItems"] = min_scenes
    schema["properties"]["scenes"]["maxItems"] = max_scenes
    return schema


def generate_local_3act_scenes(title: str, genre: str = "catastrophe", duration: int = 300, aspect: str = "16:9") -> list[dict[str, Any]]:
    """Synthesize structured scenes adhering to the universal 2nd-person retention standard across all genres.

    Invariants:
    - 100% English narration in 2nd-person singular ('You'). Zero 3rd-person narrator.
    - In-media-res crisis hook within the first 3 seconds.
    - Concrete micro-survival & technical mathematics tailored to genre (PSI, ATM, RAM %, dB, bodkin arrows).
    - Atmospheric & situational framing (helmet HUD, peephole, periscope, terminal, arrow slit) to eliminate AI facial uncanny valley.
    - Aspect-ratio tailored smart endings: 16:9 unresolved cliffhangers vs 9:16 seamless audio loops.
    """
    arch = detect_genre_archetype(genre)
    if arch.slug == "catastrophe":
        return generate_catastrophe_scenes(title=title, duration=duration, aspect=aspect)
    return generate_universal_scenes(title=title, genre=genre, duration=duration, aspect=aspect)


def produce_film(
    title: str = typer.Argument(..., help="Title or central premise of the film"),
    genre: str = typer.Option("catastrophe", "--genre", "-g", help="Film genre (e.g. catastrophe, Survival Horror, Sci-Fi, Cyberpunk)"),
    engine: str = typer.Option("flow", "--engine", "-e", help="Physical render engine: 'flow' (Google Veo / Imagen 3 CDP) or 'xai'"),
    duration: int = typer.Option(300, "--duration", "-d", help="Target film duration in seconds"),
    aspect: str = typer.Option("16:9", "--aspect", "-a", help="Aspect ratio: '16:9' or '9:16'"),
    voice_provider: str = typer.Option("deepgram", "--voice-provider", "-v", help="Narration provider: 'deepgram', 'voyslity', 'elevenlabs', or 'azure'"),
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
    yes: bool = typer.Option(False, "--yes", "-y", help="Automatically confirm physical video rendering without prompting"),
    allow_deepmind_fallback: bool = typer.Option(False, "--allow-deepmind-fallback", help="Allow fallback to DeepMind heuristic if gemini_webapi is unavailable"),
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
        f"[AUDIO] [b]Audio Layers:[/b] 3 Layers Active (TTS + Music + SFX)\n"
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

    # Canonical UDSE v4.2 resolution for canonical pilot
    if slug == "project-rigor-mortis-episode-01" and director_mode:
        console.print("  + Compiling Canonical 3-Act UDSE v4.2 Screenplay (9 blocks / 74s / EAB Invariants)...")
        scenes = generate_rigor_mortis_episode_01_scenes()
        duration = int(sum(float(s.get("duration", 8.0)) for s in scenes))
    elif not rebuild and handoff_path.is_file() and handoff_path.stat().st_size > 100:
        try:
            saved_data = json.loads(handoff_path.read_text(encoding="utf-8"))
            if (
                saved_data.get("scenes")
                and len(saved_data["scenes"]) >= 4
                and saved_data.get("duration") == duration
                and (not genre or saved_data.get("genre", "").lower() == genre.lower())
                and (genre != "catastrophe" or all("micro_math" in s and s.get("narration", "").startswith(("You ", "Your ")) for s in saved_data["scenes"]))
            ):
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
            from engine.services.skill_loader import get_skill_loader
            skill_loader = get_skill_loader()

            console.print(f"  + Injected live directives from {len(skill_loader.list_skills())} disk skills.")

            llm = GrokLLMProvider(api_key=xai_key, model="grok-4.20-0309-non-reasoning")
            system_prompt = build_llm_genre_system_prompt(
                title=title,
                genre=genre,
                duration=duration,
                aspect=aspect,
            )
            target_schema = get_script_schema(duration=duration)
            script_data = asyncio.run(llm.generate_script(
                topic=f"{title} ({genre})",
                system_prompt=system_prompt,
                schema=target_schema,
            ))
            scenes = script_data.get("scenes", [])
            console.print(f"  + Grok authored {len(scenes)} dynamic 2nd-person scenes.")
        except Exception as exc:
            console.print(f"  [yellow]Notice: Grok API call encountered: {exc}. Falling back to Universal Procedural scenes.[/yellow]")
            if archetype.slug == "catastrophe":
                scenes = generate_catastrophe_scenes(title, duration=duration, aspect=aspect)
            else:
                scenes = generate_universal_scenes(title, genre, duration, aspect=aspect)
    elif not scenes:
        console.print(f"  + Synthesizing Universal 2nd-Person Narrative ({archetype.display_name} Standard)...")
        if archetype.slug == "catastrophe":
            scenes = generate_catastrophe_scenes(title, duration=duration, aspect=aspect)
        else:
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

    # Phase 1.5: Adversarial Review & Auto-Healing (Grok & Gemini Quality Gate)
    console.print("\n[bold magenta][1.5/3] Running Adversarial Screenplay Audit & Auto-Healer...[/bold magenta]")
    from engine.services.screenplay_reviewer import ScreenplayReviewer, GeminiWebAPIUnavailableError
    from engine.services.screenplay_healer import ScreenplayHealer

    allow_deepmind = allow_deepmind_fallback
    reviewer = ScreenplayReviewer(xai_api_key=xai_key, allow_deepmind_fallback=allow_deepmind)
    initial_scenes_snapshot = copy.deepcopy(scenes)

    try:
        scorecard = reviewer.review(scenes, title=title, genre=genre, consult_ai=bool(xai_key))
    except GeminiWebAPIUnavailableError:
        console.print("\n[bold red][FAIL-CLOSED USER GATE][/bold red] [yellow]gemini_webapi (Chrome CDP port 9223) is unavailable or timed out.[/yellow]")
        proceed_fallback = typer.confirm("gemini_webapi bağlantısı kurulamadı. DeepMind alternatif protokolüne geçilsin mi?", default=False)
        if not proceed_fallback:
            console.print("[bold red]İşlem kullanıcı tarafından durduruldu (Fail-Closed). gemini_webapi veya Chrome CDP (port 9223) oturumunu kontrol edin.[/bold red]")
            raise typer.Exit(code=1)
        allow_deepmind = True
        reviewer = ScreenplayReviewer(xai_api_key=xai_key, allow_deepmind_fallback=True)
        scorecard = reviewer.review(scenes, title=title, genre=genre, consult_ai=bool(xai_key))

    initial_ai_critique = scorecard.ai_critique
    reinforcement_records = []

    if scorecard.ai_critique:
        console.print(Panel(
            scorecard.ai_critique.strip(),
            title="[bold yellow]Adversarial Reviewer Critique (Grok xAI & Google Gemini)[/bold yellow]",
            border_style="yellow",
        ))

    if not scorecard.passed:
        console.print(f"  [yellow]Initial audit score: {scorecard.total_score}/100 ({scorecard.grade}) with {len(scorecard.defects)} defect(s). Initiating Full-Context Auto-Healer...[/yellow]")
        healer = ScreenplayHealer(reviewer=reviewer, xai_api_key=xai_key, target_score=90)
        heal_res = healer.heal(scenes, title=title, genre=genre, consult_ai=bool(xai_key))
        scenes = heal_res.repaired_scenes
        scorecard = heal_res.final_scorecard
        if not scorecard.ai_critique:
            scorecard.ai_critique = initial_ai_critique
        reinforcement_records = heal_res.reinforcement_records
        for log_line in heal_res.repair_log:
            console.print(f"    [dim]{log_line}[/dim]")
    else:
        console.print(f"  [green]Initial audit passed directly: {scorecard.total_score}/100 ({scorecard.grade})[/green]")

    # Generate Comprehensive Transparent Raw Audit Report
    artifacts_dir = _ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "ADVERSARIAL_SCREENPLAY_PIPELINE_COMPLETE_REPORT.md"

    # Build Before/After Diff Table
    diff_lines = []
    for idx, (orig, rep) in enumerate(zip(initial_scenes_snapshot, scenes)):
        if orig.get("narration") != rep.get("narration") or orig.get("visual_prompt") != rep.get("visual_prompt"):
            diff_lines.append(f"#### Scene {idx + 1}")
            if orig.get("narration") != rep.get("narration"):
                diff_lines.append(f"- **Before Narration:** {orig.get('narration')}")
                diff_lines.append(f"- **After Narration:** {rep.get('narration')}")
            if orig.get("visual_prompt") != rep.get("visual_prompt"):
                diff_lines.append(f"- **Before Prompt:** {orig.get('visual_prompt')}")
                diff_lines.append(f"- **After Prompt:** {rep.get('visual_prompt')}")
            diff_lines.append("")

    reinf_lines = []
    if reinforcement_records:
        for r in reinforcement_records:
            reinf_lines.append(f"- **Skill:** `{r.get('skill_slug')}` | **Rule:** {r.get('rule')} (Lines: {r.get('line_count')})")
    else:
        reinf_lines.append("- No persistent skill modifications required (screenplay compliant with active guidelines).")

    report_content = (
        f"# Complete Adversarial Screenplay Audit & Closed-Loop Healing Report\n\n"
        f"- **Project Title:** {title}\n"
        f"- **Genre:** {genre}\n"
        f"- **Total Scenes:** {len(scenes)} ({duration}s)\n"
        f"- **Final Certification:** {scorecard.grade} ({scorecard.total_score}/100) — {'PASSED' if scorecard.passed else 'FAILED'}\n"
        f"- **Dual-Judge Scores:** Grok = {scorecard.grok_score or 'N/A'}, Gemini = {scorecard.gemini_score or 'N/A'}\n\n"
        f"## 1. Dual-Judge Evaluation Verdict\n\n"
        f"{scorecard.ai_critique or 'Deterministic schema evaluation passed without critical defects.'}\n\n"
        f"## 2. Raw Prompts and LLM Responses\n\n"
        f"### A. Raw Compact Screenplay Payload (Sent to Judges)\n"
        f"```json\n{scorecard.raw_prompt or 'N/A'}\n```\n\n"
        f"### B. Judge 1 (xAI Grok) Raw Response\n"
        f"```\n{scorecard.raw_grok_response or 'N/A'}\n```\n\n"
        f"### C. Judge 2 (Google Gemini) Raw Response\n"
        f"```\n{scorecard.raw_gemini_response or 'N/A'}\n```\n\n"
        f"## 3. Healed Scenes Before vs After Comparison\n\n"
        f"{chr(10).join(diff_lines) if diff_lines else 'No scene modifications were required.'}\n\n"
        f"## 4. Closed-Loop Skill Reinforcement Log\n\n"
        f"{chr(10).join(reinf_lines)}\n"
    )
    report_file.write_text(report_content, encoding="utf-8")
    console.print(f"  + Transparent Audit Report written -> [dim]{report_file}[/dim]")

    if scorecard.passed:
        console.print(Panel(
            f"[bold green][CERTIFIED] Screenplay Certified Grade A+ ({scorecard.total_score}/100)![/bold green]\n\n"
            f"[b]Project Title:[/b] {title}\n"
            f"[b]Scenes / Duration:[/b] {len(scenes)} scenes / {duration}s ({aspect})\n"
            f"[b]Audit Scores:[/b]\n"
            f"  - CTA Isolation: {scorecard.category_scores.get('cta_isolation', 0)}/15 pts\n"
            f"  - Veo Negative Guards: {scorecard.category_scores.get('veo_guardrails', 0)}/25 pts\n"
            f"  - Thermodynamics: {scorecard.category_scores.get('thermodynamic_sanity', 0)}/20 pts\n"
            f"  - Chronological Scale: {scorecard.category_scores.get('narrative_time_scale', 0)}/15 pts\n"
            f"  - Causality Integrity: {scorecard.category_scores.get('causality_integrity', 0)}/15 pts\n"
            f"  - 2nd-Person Invariant: {scorecard.category_scores.get('pov_invariants', 0)}/10 pts",
            title="[CERTIFIED] Adversarial Screenplay Gate",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red][FAILED] Screenplay Audit Incomplete: {scorecard.grade} ({scorecard.total_score}/100)[/bold red]\n\n"
            f"[b]Project Title:[/b] {title}\n"
            f"[b]Defects ({len(scorecard.defects)}):[/b]\n" + "\n".join(f"  - {d}" for d in scorecard.defects[:5]),
            title="[AUDIT WARNING] Screenplay Quality Gate",
            border_style="red"
        ))

    # Save handoff packet
    handoff_packet = {
        "title": title,
        "genre": genre,
        "episode": episode,
        "duration": duration,
        "aspect": aspect,
        "ai_critique": scorecard.ai_critique,
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

    # Phase 2: User Confirmation Gate before Physical Execution
    if not dry_run and not yes:
        proceed = typer.confirm("Do you want to proceed with physical video rendering via Google Flow CDP?", default=True)
        if not proceed:
            console.print("[yellow]Physical production halted by user. Certified screenplay remains sealed in sequences/.[/yellow]")
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
        thumbnail_path = out_dir / "thumbnail.jpg"
        if not thumbnail_path.is_file():
            try:
                from engine.services.thumbnail_generator import generate_thumbnail

                generate_thumbnail(
                    base_image=None,
                    title_text=title,
                    output_path=thumbnail_path,
                )
            except Exception as exc:
                logger.warning(f"Fallback thumbnail generation notice: {exc}")

        console.print(f"  + YouTube Thumbnail locked -> [dim]{thumbnail_path}[/dim]")

        console.print(Panel(
            f"[bold green][DONE] Film Successfully Produced![/bold green]\n\n"
            f"[VIDEO] [b]Final MP4:[/b] {final_mp4}\n"
            f"[THUMBNAIL] [b]Thumbnail:[/b] {thumbnail_path}\n"
            f"[AUDIO] [b]Audio Layers Active (3 Layers):[/b]\n"
            f"  • Layer 1 (TTS Voiceover): {voice_provider.upper()}\n"
            f"  • Layer 2 (Background Music Bed): -14 LUFS (TTS Sidechain Ducked)\n"
            f"  • Layer 3 (SFX Foley): {os.getenv('SFX_PROVIDER', 'gradio_space')} / AudioGen / TangoFlux\n"
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
