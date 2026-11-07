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
import uuid
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_TOOLS = Path(__file__).resolve().parents[1]
_ROOT = _TOOLS.parent

# Ensure root, engine, and tools are on sys.path
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(_ROOT / "engine"))
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_console_text(text: Any) -> str:
    """Normalize unicode math/checkmarks to plain ASCII so Windows console never crashes."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "\u2074": "^4",
        "\u2070": "^0",
        "\u00b9": "^1",
        "\u00b2": "^2",
        "\u00b3": "^3",
        "\u00b0": " deg ",
        "\u2713": "[OK]",
        "\u2705": "[OK]",
        "\u274c": "[X]",
        "\u2192": "->",
        "\u2265": ">=",
        "\u2264": "<=",
        "\u2022": "-",
        "\u00b7": "-",
        "\u26a0": "[!]",
        "\u2014": "--",
        "\u2013": "-",
    }
    for char, rep in replacements.items():
        if char in text:
            text = text.replace(char, rep)
    return text.encode("ascii", errors="replace").decode("ascii")


from engine.flow_bridge import execute_grok_flow_production, sanitize_slug
from engine.providers.llm.grok import GrokLLMProvider
from engine.services.continuity import EpisodeHandoff, apply_handoff_to_scenes
from engine.services.screenplay_linter import lint_scenes
from engine.services.text_sanitizer import sanitize_spoken_text
from engine.services.universal_narrative import (
    UniversalNarrativeEngine,
    build_llm_catastrophe_system_prompt,
    build_llm_genre_system_prompt,
    detect_genre_archetype,
    generate_5act_script,
    generate_catastrophe_scenes,
    generate_universal_scenes,
)
from tools.cli.production import build_production_bible

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("produce_commands")


def _load_short_test_draft(directory: Path, slug: str, *, title: str, genre: str, duration: int, aspect: str) -> list[dict[str, Any]]:
    """Load a matching unreviewed test draft; it must still pass all review gates."""
    for path in sorted(directory.glob(f"{slug}_draft_*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            scenes = data.get("scenes")
            if (data.get("kind") == "unreviewed_short_test_draft" and data.get("short_test") is True
                    and data.get("production_certified") is False and data.get("title") == title
                    and data.get("genre") == genre and data.get("duration") == duration
                    and data.get("aspect") == aspect and isinstance(scenes, list) and len(scenes) >= 4
                    and all(isinstance(s, dict) and not s.get("simulation_only") for s in scenes)):
                return scenes
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return []


def _save_short_test_draft(directory: Path, slug: str, *, title: str, genre: str, duration: int, aspect: str, scenes: list[dict[str, Any]]) -> Path:
    """Preserve an unreviewed live authoring result without overwriting earlier drafts."""
    path = directory / f"{slug}_draft_{uuid.uuid4().hex}.json"
    payload = {"kind": "unreviewed_short_test_draft", "short_test": True,
               "production_certified": False, "review_status": "not_reviewed",
               "title": title, "genre": genre, "duration": duration, "aspect": aspect, "scenes": scenes}
    with path.open("x", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    return path

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
                    "micro_math": {
                        "type": "string",
                        "description": "Concrete survival metrics: temperature, pressure in PSI/bar, time in seconds, distance, calories, radiation",
                    },
                },
                "required": [
                    "id",
                    "scene_number",
                    "narration",
                    "visual_prompt",
                    "motion_prompt",
                    "duration",
                    "micro_math",
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


def generate_local_3act_scenes(title: str, genre: str = "catastrophe", duration: int = 300, aspect: str = "16:9", *, simulation: bool = False) -> list[dict[str, Any]]:
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
        return generate_catastrophe_scenes(title=title, duration=duration, aspect=aspect, simulation=simulation)
    return generate_universal_scenes(title=title, genre=genre, duration=duration, aspect=aspect, simulation=simulation)


def _mark_partial_review(scorecard: Any, *, mode: str, short_test: bool, simulation: bool) -> None:
    """Do not promote a checklist-only or simulated score to production certification."""
    if simulation:
        scorecard.passed = False
        scorecard.grade = "SIMULATION (UNCERTIFIED)"
        if "Simulation fixtures cannot receive production certification" not in scorecard.defects:
            scorecard.defects.append("Simulation fixtures cannot receive production certification")
    elif mode == "strict-checklist" and not short_test:
        scorecard.passed = False
        scorecard.grade = "PARTIAL REVIEW (UNCERTIFIED)"
        scorecard.defects.append("Checklist-only review cannot certify production; use holistic review.")


def _review_allows_render(scorecard: Any, *, dry_run: bool) -> bool:
    """Only a passed review authorizes live rendering; dry runs are simulations."""
    return dry_run or (scorecard.passed and scorecard.total_score >= 90)


def produce_film(
    title: str = typer.Argument(..., help="Title or central premise of the film"),
    genre: str = typer.Option("catastrophe", "--genre", "-g", help="Film genre (e.g. catastrophe, Survival Horror, Sci-Fi, Cyberpunk)"),
    engine: str = typer.Option("flow", "--engine", "-e", help="Physical render engine: 'flow' (Google Flow CDP: Veo 3.1 + Remotion + Deepgram + FFmpeg) or 'xai'"),
    veo_mode: str = typer.Option(
        "quality",
        "--veo-mode",
        help="Google Veo 3.1 model quality mode: 'quality' (720p HD master), 'fast' (360p high-speed), or 'lite' (rapid preview pre-vis)",
    ),
    duration: int = typer.Option(300, "--duration", "-d", help="Target film duration in seconds"),
    aspect: str = typer.Option("16:9", "--aspect", "-a", help="Aspect ratio: '16:9' or '9:16'"),
    screenplay_mode: str = typer.Option("strict-checklist", "--screenplay-mode", help="Screenplay review: strict-checklist or holistic (experimental)."),
    voice_provider: str = typer.Option("deepgram", "--voice-provider", "-v", help="Narration provider: 'deepgram', 'voyslity', 'elevenlabs', or 'azure'"),
    plan_only: bool = typer.Option(False, "--plan-only", "-p", help="Generate production bible, character DNA, and handoff scenes without rendering"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run local offline simulation without remote provider calls"),
    no_music: bool = typer.Option(False, "--no-music", help="Disable background audio bed"),
    no_captions: bool = typer.Option(False, "--no-captions", help="Disable burned Libass karaoke subtitles"),
    hero_plate: Optional[str] = typer.Option(None, "--hero-plate", help="Path to character hero plate image for continuity QA"),
    allow_flow_text_fallback: bool = typer.Option(False, "--allow-flow-text-fallback", help="Explicitly allow text-only Flow generation when native reference conditioning is unavailable."),
    rebuild: bool = typer.Option(False, "--rebuild", "-r", help="Bypass cached handoff and re-generate canonical 3-act UDSE screenplay"),
    director_mode: bool = typer.Option(True, "--director-mode/--no-director-mode", help="Enable Grok 4.6 Autonomous Director Engine with UDSE v4.2"),
    episode: int = typer.Option(1, "--episode", help="Episode number in series (default: 1)"),
    continue_from: Optional[str] = typer.Option(None, "--continue-from", help="Directory or path to previous episode continuity handoff to thaw state"),
    simulate_defect_block: Optional[int] = typer.Option(None, "--simulate-defect-block", help="Simulate a visual continuity breach on block N to test Director Agent HEAL re-generation loop"),
    video_qa: bool = typer.Option(False, "--video-qa/--no-video-qa", help="Audit sampled video frames before final assembly; motion and audio are not covered"),
    video_qa_model: str = typer.Option("gemini-3.1-pro", "--video-qa-model", help="Model identifier used by the configured video QA adapter"),
    video_qa_batch_size: int = typer.Option(12, "--video-qa-batch-size", min=3, help="Local maximum sampled images per request; provider limits may differ."),
    max_patch_passes: int = typer.Option(1, "--max-patch-passes", help="--max-patch-passes sets the maximum selective video QA patch passes (0-1)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Automatically confirm physical video rendering without prompting"),
    allow_deepmind_fallback: bool = typer.Option(False, "--allow-deepmind-fallback", help="Allow fallback to DeepMind heuristic if gemini_webapi is unavailable"),
    force_render: bool = typer.Option(False, "--force-render", help="Compatibility option; does not bypass the live review gate."),
    export_shorts: bool = typer.Option(
        False,
        "--export-shorts",
        "--vertical-cut",
        help="Legacy: center-crop multiplex 9:16 cut from 16:9 master. For native 9:16 Flow production, use --aspect 9:16.",
    ),
    gemini_judge_model: str = typer.Option("gemini-3.1-pro", "--gemini-judge-model", help="Gemini judge model identifier (default: gemini-3.1-pro via Chrome CDP)"),
    grok_judge_model: str = typer.Option("grok-4.20-non-reasoning", "--grok-judge-model", help="xAI Grok judge model identifier (default: grok-4.20-0309-non-reasoning)"),
    short_test: bool = typer.Option(False, "--short-test", help="Use the explicitly authorized short integration-test contract; output is not production certified."),
) -> None:
    """Produce a complete cinematic film through Flow, voice, and FFmpeg.

    Set --max-patch-passes to 0 or 1 to control selective video repairs.
    """
    slug = sanitize_slug(title)
    normalized_veo_mode = veo_mode.lower()
    if normalized_veo_mode not in ("quality", "fast", "lite", "720p", "360p"):
        raise typer.BadParameter("Choose quality, fast, or lite", param_hint="--veo-mode")
    if normalized_veo_mode in ("quality", "720p", "hd"):
        os.environ["VEO_QUALITY_MODE"] = "quality"
        os.environ["FLOW_VIDEO_REAL_QUALITY"] = "720p"
    elif normalized_veo_mode in ("fast", "360p"):
        os.environ["VEO_QUALITY_MODE"] = "fast"
        os.environ["FLOW_VIDEO_TEST_QUALITY"] = "360p"
    elif normalized_veo_mode in ("lite", "preview"):
        os.environ["VEO_QUALITY_MODE"] = "lite"
        os.environ["FLOW_VIDEO_TEST_QUALITY"] = "360p"
    if screenplay_mode not in {"strict-checklist", "holistic"}:
        raise typer.BadParameter("Choose strict-checklist or holistic", param_hint="--screenplay-mode")
    if short_test:
        if force_render:
            console.print("[red]--short-test cannot bypass the adversarial review gate.[/red]")
            raise typer.Exit(code=1)
        if genre.strip().lower() != "catastrophe" or not 1 <= duration <= 40:
            console.print("[red]--short-test requires catastrophe genre and a duration between 1 and 40 seconds.[/red]")
            raise typer.Exit(code=1)
        slug = f"test-only-{slug}"
        console.print("[yellow]TEST ONLY: short integration contract; output is not production certified.[/yellow]")
    if os.getenv("XAI_MODEL") and (grok_judge_model in ("grok-4.20-non-reasoning", "grok-4.20-0309-non-reasoning") or not grok_judge_model):
        grok_judge_model = os.getenv("XAI_MODEL")
    out_dir = _ROOT / "out" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    sequences_dir = _ROOT / "sequences"
    sequences_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(
        f"[bold cyan]Grok Imagine Cinematic Studio v4.0[/bold cyan] [yellow]x[/yellow] [bold green]Google Flow CDP Engine[/bold green]\n\n"
        f"[FILM] [b]Project Title:[/b] {title}\n"
        f"[GENRE] [b]Genre:[/b] {genre}\n"
        f"[ENGINE] [b]Physical Engine:[/b] {engine.upper()} (Google Flow CDP + Remotion + Deepgram + FFmpeg)\n"
        f"[VEO] [b]Veo 3.1 Quality/Mode:[/b] {veo_mode.upper()} ({'720p HD Master' if normalized_veo_mode in ('quality', '720p') else '360p High-Speed Preview'})\n"
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

    # Resume authored handoffs; simulation data never becomes a live production.
    if not rebuild and handoff_path.is_file() and handoff_path.stat().st_size > 100:
        try:
            saved_data = json.loads(handoff_path.read_text(encoding="utf-8"))
            if (
                saved_data.get("scenes")
                and bool(saved_data.get("short_test", False)) == short_test
                and (dry_run or not any(scene.get("simulation_only") for scene in saved_data["scenes"]))
                and len(saved_data["scenes"]) >= 4
                and saved_data.get("duration") == duration
                and (not genre or saved_data.get("genre", "").lower() == genre.lower())
                and (genre != "catastrophe" or all("micro_math" in s and s.get("narration", "").startswith(("You ", "Your ")) for s in saved_data["scenes"]))
                and saved_data.get("adversarial_review", {}).get("passed", False) is True
                and saved_data.get("adversarial_review", {}).get("total_score", 0) >= 90
            ):
                scenes = saved_data["scenes"]
                for s in scenes:
                    s["narration"] = sanitize_spoken_text(s.get("narration", ""))
                console.print(f"  + Reusing authored screenplay ({len(scenes)} scenes); current rules will be reviewed again -> [dim]{handoff_path.name}[/dim]")
        except Exception:
            pass

    archetype = detect_genre_archetype(genre)
    if not scenes and short_test and xai_key and not dry_run and not rebuild:
        scenes = _load_short_test_draft(sequences_dir, slug, title=title, genre=genre, duration=duration, aspect=aspect)
        if scenes:
            console.print("  + Resuming unreviewed TEST-ONLY draft; full review remains mandatory.")
    if not scenes and xai_key and not dry_run:
        console.print(f"  + Orchestrating Universal 2nd-Person Screenplay ({archetype.display_name}) via xAI Grok API...")
        try:
            from engine.services.skill_loader import get_skill_loader
            skill_loader = get_skill_loader()
            console.print(f"  + Injected live directives from {len(skill_loader.list_skills())} disk skills.")

            llm = GrokLLMProvider(
                api_key=xai_key,
                model=os.getenv("XAI_MODEL") or "grok-4.20-0309-non-reasoning",
                base_url=os.getenv("XAI_API_BASE"),
            )
            engine_inst = UniversalNarrativeEngine(skill_loader=skill_loader, llm_provider=llm)
            scenes = engine_inst.generate_screenplay(
                title=title,
                genre=genre,
                duration=duration,
                aspect=aspect,
                voice_provider=voice_provider,
                dry_run=dry_run,
                short_test=short_test,
            )
            if short_test and not any(s.get("simulation_only") for s in scenes):
                draft_path = _save_short_test_draft(sequences_dir, slug, title=title, genre=genre, duration=duration, aspect=aspect, scenes=scenes)
                console.print(f"  + Saved unreviewed TEST-ONLY draft -> [dim]{draft_path.name}[/dim]")
            console.print(f"  + Grok authored {len(scenes)} dynamic 2nd-person scenes across 5 acts.")
        except Exception as exc:
            console.print(f"[red]Screenplay authoring failed: {safe_console_text(exc)}[/red]")
            raise typer.Exit(code=1)
    elif not scenes:
        if not dry_run:
            console.print("[red]Live authoring requires XAI_API_KEY or an existing handoff. Use --dry-run for offline simulation.[/red]")
            raise typer.Exit(code=1)
        scenes = generate_universal_scenes(title, genre, duration, aspect=aspect, simulation=True)
        console.print("[yellow]Offline simulation fixture loaded; this screenplay cannot receive production certification.[/yellow]")

    if not dry_run and any(scene.get("simulation_only") for scene in scenes):
        console.print("[red]Simulation scenes cannot be rendered as a live production, including with --force-render.[/red]")
        raise typer.Exit(code=1)

    if not dry_run and not short_test and genre.strip().lower() == "catastrophe" and len(scenes) != 38:
        console.print("[red]Production catastrophe contract requires 38 scenes; use --short-test only for an explicitly authorized integration test.[/red]")
        raise typer.Exit(code=1)

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

    # Phase 1.25: Pre-Generation Linter (zero-cost deterministic format enforcement)
    # Report model-authored repair requirements before the judge loop.
    console.print("\n[bold cyan][1.25/3] Running Pre-Generation Linter (POV · CTA · Veo Guards)...[/bold cyan]")
    scenes, lint_actions = lint_scenes(scenes)
    if lint_actions:
        fix_count = sum(1 for a in lint_actions if "ERROR" in a)
        warn_count = sum(1 for a in lint_actions if "WARNING" in a)
        if fix_count:
            console.print(f"  [green][OK] {fix_count} violation(s) require model-authored repair:[/green]")
            for act in lint_actions:
                if "WARNING" not in act:
                    console.print(f"    [dim]- {act}[/dim]")
        if warn_count:
            console.print(f"  [yellow][!] {warn_count} advisory warning(s):[/yellow]")
            for act in lint_actions:
                if "WARNING" in act:
                    console.print(f"    [yellow dim]- {act}[/yellow dim]")
    else:
        console.print("  [green][OK] All scenes passed pre-lint checks -- no corrections needed.[/green]")

    # Phase 1.5: Adversarial Review & Auto-Healing (Grok & Gemini Quality Gate)
    console.print("\n[bold magenta][1.5/3] Running Adversarial Screenplay Audit & Auto-Healer...[/bold magenta]")
    from engine.services.screenplay_reviewer import ScreenplayReviewer, GeminiWebAPIUnavailableError
    from engine.services.screenplay_healer import ScreenplayHealer

    allow_deepmind = allow_deepmind_fallback
    reviewer = ScreenplayReviewer(
        xai_api_key=xai_key,
        allow_deepmind_fallback=allow_deepmind,
        gemini_model=gemini_judge_model,
        grok_model=grok_judge_model,
        short_test=short_test,
        screenplay_mode=screenplay_mode,
        aspect=aspect,
    )
    initial_scenes_snapshot = copy.deepcopy(scenes)
    consult_ai_active = bool(xai_key and not dry_run and screenplay_mode == "holistic")

    try:
        scorecard = reviewer.review(scenes, title=title, genre=genre, consult_ai=consult_ai_active)
    except GeminiWebAPIUnavailableError:
        console.print("\n[bold red][FAIL-CLOSED USER GATE][/bold red] [yellow]gemini_webapi (Chrome CDP port 9223) is unavailable or timed out.[/yellow]")
        proceed_fallback = typer.confirm("Could not connect to gemini_webapi. Fallback to alternative DeepMind protocol?", default=False)
        if not proceed_fallback:
            console.print("[bold red]Operation halted by user (Fail-Closed). Check gemini_webapi or Chrome CDP (port 9223) session.[/bold red]")
            raise typer.Exit(code=1)
        allow_deepmind = True
        reviewer = ScreenplayReviewer(
            xai_api_key=xai_key,
            allow_deepmind_fallback=True,
            gemini_model=gemini_judge_model,
            grok_model=grok_judge_model,
            short_test=short_test,
            screenplay_mode=screenplay_mode,
            aspect=aspect,
        )
        scorecard = reviewer.review(scenes, title=title, genre=genre, consult_ai=consult_ai_active)

    simulation_only = dry_run or any(scene.get("simulation_only") for scene in scenes)
    if simulation_only:
        scorecard.passed = False
        scorecard.grade = "SIMULATION (UNCERTIFIED)"
        scorecard.defects.append("Simulation fixtures cannot receive production certification")

    initial_ai_critique = scorecard.ai_critique
    initial_score = scorecard.total_score
    initial_grade = scorecard.grade
    initial_grok = scorecard.grok_score
    initial_gemini = scorecard.gemini_score
    reinforcement_records = []
    round_records = []

    if scorecard.ai_critique:
        console.print(Panel(
            scorecard.ai_critique.strip(),
            title="[bold yellow]Initial Adversarial Reviewer Critique (Grok xAI & Google Gemini)[/bold yellow]",
            border_style="yellow",
        ))

    if (not scorecard.passed or scorecard.total_score < 90) and not dry_run and (screenplay_mode == "holistic" or short_test):
        console.print(f"  [yellow]Initial audit score: {scorecard.total_score}/100 ({scorecard.grade}) with {len(scorecard.defects)} defect(s). Initiating Multi-Round Auto-Healer (up to 3 passes, target >= 90)...[/yellow]")
        healer = ScreenplayHealer(
            reviewer=reviewer,
            xai_api_key=xai_key,
            target_score=90,
            grok_model=grok_judge_model,
        )
        heal_res = healer.heal(scenes, title=title, genre=genre, max_iterations=4, consult_ai=consult_ai_active, initial_scorecard=scorecard)
        scenes = heal_res.repaired_scenes
        scorecard = heal_res.final_scorecard
        if not scorecard.ai_critique:
            scorecard.ai_critique = initial_ai_critique
        reinforcement_records = heal_res.reinforcement_records
        round_records = heal_res.round_records

        # Print each round in detail
        for rnd in round_records:
            rep_ids_str = ", ".join(f"Scene {sid}" for sid in rnd.repaired_scene_ids) if rnd.repaired_scene_ids else "Deterministic polish"
            defects_preview = "\n".join(f"    - {safe_console_text(d)}" for d in rnd.defects_before[:4])
            if len(rnd.defects_before) > 4:
                defects_preview += f"\n    [dim]... and {len(rnd.defects_before) - 4} more defect(s)[/dim]"

            round_panel_text = (
                f"[bold cyan]Judges Review (Pre-Healing):[/bold cyan]\n"
                f"  - Grok xAI Score: {rnd.grok_score_before or 'N/A'}/100 | Gemini Score: {rnd.gemini_score_before or 'N/A'}/100\n"
                f"  - Combined Score: {rnd.score_before}/100 ({rnd.grade_before})\n\n"
                f"[bold yellow]Flagged Defects ({len(rnd.defects_before)}):[/bold yellow]\n"
                f"{defects_preview}\n\n"
                f"[bold green]Screenwriter Actions:[/bold green]\n"
                f"  - Repaired: [bold]{rep_ids_str}[/bold]\n\n"
                f"[bold magenta]Judges Re-Audit (Post-Healing):[/bold magenta]\n"
                f"  - Grok xAI Score: {rnd.grok_score_after or 'N/A'}/100 | Gemini Score: {rnd.gemini_score_after or 'N/A'}/100\n"
                f"  - Re-Audit Score: [bold green]{rnd.score_after}/100 ({rnd.grade_after})[/bold green]"
            )
            console.print(Panel(
                round_panel_text,
                title=f"[bold yellow]🥊 ROUND {rnd.iteration} ADVERSARIAL DEBATE & REPAIR[/bold yellow]",
                border_style="cyan",
            ))

        # Progression Table
        table = Table(title="[bold magenta]Adversarial Multi-Round Progression Scoreboard[/bold magenta]", border_style="magenta")
        table.add_column("Round", justify="center", style="bold white")
        table.add_column("Grok Score", justify="center")
        table.add_column("Gemini Score", justify="center")
        table.add_column("Total Score", justify="center")
        table.add_column("Grade", justify="center")
        table.add_column("Repaired Scenes", style="green")
        table.add_column("Verdict", style="bold")

        table.add_row(
            "Initial",
            str(initial_grok or "N/A"),
            str(initial_gemini or "N/A"),
            f"{initial_score}/100",
            initial_grade,
            "Initial Draft",
            "[yellow]Defects Flagged[/yellow]"
        )
        for rnd in round_records:
            status_str = "[bold green]Target Reached (>=90)[/bold green]" if (rnd.score_after >= 90) else "[yellow]Advancing to Next Round[/yellow]"
            rep_ids_str = ", ".join(f"{sid}" for sid in rnd.repaired_scene_ids) if rnd.repaired_scene_ids else "Polish"
            table.add_row(
                f"Round {rnd.iteration}",
                str(rnd.grok_score_after or "N/A"),
                str(rnd.gemini_score_after or "N/A"),
                f"{rnd.score_after}/100",
                rnd.grade_after,
                f"Scenes: {rep_ids_str}",
                status_str,
            )
        console.print(table)
    elif not simulation_only:
        console.print(f"  [green]Initial review completed: {scorecard.total_score}/100 ({scorecard.grade})[/green]")

    _mark_partial_review(scorecard, mode=screenplay_mode, short_test=short_test, simulation=simulation_only)

    # Generate Comprehensive Transparent Raw Audit Report
    artifacts_dir = _ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    project_report_file = artifacts_dir / f"{slug}_adversarial_report.md"
    latest_report_file = artifacts_dir / ("TEST_ONLY_ADVERSARIAL_SCREENPLAY_PIPELINE_REPORT.md" if short_test else "ADVERSARIAL_SCREENPLAY_PIPELINE_COMPLETE_REPORT.md")

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

    # Build Round-by-Round Markdown Sections
    round_md_sections = []
    if round_records:
        round_md_sections.append("## 1. Multi-Round Progression Scoreboard\n")
        round_md_sections.append("| Round | Grok Score | Gemini Score | Total Score | Grade | Screenwriter Repaired Scenes | Status |")
        round_md_sections.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        round_md_sections.append(f"| Initial | {initial_grok or 'N/A'} | {initial_gemini or 'N/A'} | {initial_score}/100 | {initial_grade} | Initial Draft | Defects Flagged |")
        for rnd in round_records:
            rep_ids_str = ", ".join(f"Scene {sid}" for sid in rnd.repaired_scene_ids) if rnd.repaired_scene_ids else "Polish"
            status_text = "Target Certified" if rnd.score_after >= 90 else "Advancing to Next Round"
            round_md_sections.append(f"| Round {rnd.iteration} | {rnd.grok_score_after or 'N/A'} | {rnd.gemini_score_after or 'N/A'} | {rnd.score_after}/100 | {rnd.grade_after} | {rep_ids_str} | {status_text} |")
        round_md_sections.append("\n## 2. Round-by-Round Adversarial Debate Details\n")
        for rnd in round_records:
            rep_ids_str = ", ".join(f"Scene {sid}" for sid in rnd.repaired_scene_ids) if rnd.repaired_scene_ids else "Polish"
            defects_list_str = "\n".join(f"- {d}" for d in rnd.defects_before)
            round_md_sections.append(f"### 🥊 Round {rnd.iteration}\n")
            round_md_sections.append(f"- **Judges Evaluation Before:** Grok = {rnd.grok_score_before or 'N/A'}/100, Gemini = {rnd.gemini_score_before or 'N/A'}/100 -> Total: **{rnd.score_before}/100 ({rnd.grade_before})**\n")
            if rnd.ai_critique_before:
                round_md_sections.append(f"#### Judges Critique Before Round {rnd.iteration}\n```\n{rnd.ai_critique_before.strip()}\n```\n")
            round_md_sections.append(f"#### Flagged Defects ({len(rnd.defects_before)})\n{defects_list_str}\n")
            round_md_sections.append(f"#### Screenwriter Actions\n- Repaired scenes: **{rep_ids_str}**\n")
            for act in rnd.repair_actions:
                round_md_sections.append(f"  - {act}")
            round_md_sections.append(f"\n- **Judges Re-Audit After Round {rnd.iteration}:** Grok = {rnd.grok_score_after or 'N/A'}/100, Gemini = {rnd.gemini_score_after or 'N/A'}/100 -> **New Score: {rnd.score_after}/100 ({rnd.grade_after})**\n\n---\n")

    report_content = (
        f"# Complete Adversarial Screenplay Audit & Closed-Loop Healing Report\n\n"
        f"- **Project Title:** {title}\n"
        f"- **Genre:** {genre}\n"
        f"- **Contract:** {'TEST ONLY (not production certified)' if short_test else 'production'}\n"
        f"- **Total Scenes:** {len(scenes)} ({duration}s)\n"
        f"- **Final {'Test Review' if short_test else 'Certification'}:** {scorecard.grade} ({scorecard.total_score}/100) — {'PASSED' if scorecard.passed else 'FAILED'}\n"
        f"- **Dual-Judge Final Scores:** Grok = {scorecard.grok_score or 'N/A'}, Gemini = {scorecard.gemini_score or 'N/A'}\n\n"
        + "\n".join(round_md_sections)
        + f"\n## 3. Final Dual-Judge Evaluation Verdict\n\n"
        f"{scorecard.ai_critique or 'Deterministic schema evaluation passed without critical defects.'}\n\n"
        f"## 4. Healed Scenes Before vs After Comparison\n\n"
        f"{chr(10).join(diff_lines) if diff_lines else 'No scene modifications were required.'}\n\n"
        f"## 5. Closed-Loop Skill Reinforcement Log\n\n"
        f"{chr(10).join(reinf_lines)}\n\n"
        f"## 6. Raw Prompts and LLM Responses\n\n"
        f"### A. Raw Compact Screenplay Payload (Sent to Judges)\n"
        f"```json\n{scorecard.raw_prompt or 'N/A'}\n```\n\n"
        f"### B. Judge 1 (xAI Grok) Raw Response\n"
        f"```\n{scorecard.raw_grok_response or 'N/A'}\n```\n\n"
        f"### C. Judge 2 (Google Gemini) Raw Response\n"
        f"```\n{scorecard.raw_gemini_response or 'N/A'}\n```\n"
    )
    project_report_file.write_text(report_content, encoding="utf-8")
    latest_report_file.write_text(report_content, encoding="utf-8")
    console.print(f"  + Transparent Audit Report written -> [dim]{project_report_file}[/dim]")


    if scorecard.passed and scorecard.total_score >= 90:
        console.print(Panel(
            f"[bold green]{'[TEST REVIEW PASSED]' if short_test else '[CERTIFIED] Screenplay Certified Grade A+'} ({scorecard.total_score}/100)![/bold green]\n\n"
            f"[b]Project Title:[/b] {safe_console_text(title)}\n"
            f"[b]Scenes / Duration:[/b] {len(scenes)} scenes / {duration}s ({aspect})\n"
            f"[b]Audit Scores:[/b]\n"
            + "\n".join(f"  - {safe_console_text(key)}: {value} pts" for key, value in scorecard.category_scores.items()),
            title="[TEST REVIEW] Adversarial Screenplay Gate" if short_test else "[CERTIFIED] Adversarial Screenplay Gate",
            border_style="green"
        ))
    else:
        clean_defects = [safe_console_text(d) for d in scorecard.defects[:5]]
        console.print(Panel(
            f"[bold red][FAILED] Screenplay Audit Incomplete: {scorecard.grade} ({scorecard.total_score}/100)[/bold red]\n\n"
            f"[b]Project Title:[/b] {safe_console_text(title)}\n"
            f"[b]Defects ({len(scorecard.defects)}):[/b]\n" + "\n".join(f"  - {d}" for d in clean_defects),
            title="[AUDIT WARNING] Screenplay Quality Gate",
            border_style="red"
        ))

    # Save handoff packet
    handoff_packet = {
        "short_test": short_test,
        "production_certified": False,
        "screenplay_review_passed": bool(scorecard.passed and scorecard.total_score >= 90),
        "screenplay_review": scorecard.to_dict(),
        "title": title,
        "genre": genre,
        "episode": episode,
        "duration": duration,
        "aspect": aspect,
        "ai_critique": scorecard.ai_critique,
        "adversarial_review": {
            "passed": scorecard.passed,
            "grade": scorecard.grade,
            "total_score": scorecard.total_score,
            "grok_score": scorecard.grok_score,
            "gemini_score": scorecard.gemini_score,
            "defects_count": len(scorecard.defects),
        },
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
            f"python tools/cinematic_studio_cli.py produce-film \"{title}\" --genre \"{genre}\" --duration {duration}{' --short-test' if short_test else ''}",
            title="[HALT] Ready for Production Review",
            border_style="yellow"
        ))
        return

    # Fail-Closed Quality Gate: Enforce that only Certified screenplays proceed to physical execution
    _, final_lint_diagnostics = lint_scenes(scenes)
    final_lint_errors = [item for item in final_lint_diagnostics if "ERROR" in item]
    if final_lint_errors and not dry_run:
        console.print("[red]Physical rendering blocked: unresolved screenplay linter errors.[/red]")
        for item in final_lint_errors:
            console.print(f"  - {safe_console_text(item)}")
        raise typer.Exit(code=1)
    if not _review_allows_render(scorecard, dry_run=dry_run):
        console.print("\n[bold red][QUALITY GATE BLOCKED] Screenplay failed adversarial review (Score < 90 / Defects present).[/bold red]")
        if force_render:
            console.print("[yellow]--force-render cannot bypass the live review gate.[/yellow]")
        console.print("[dim]Inspect the review report and re-run with --plan-only.[/dim]\n")
        raise typer.Exit(code=1)

    if simulation_only and not dry_run:
        console.print("[red]Simulation handoffs cannot be rendered as live productions.[/red]")
        raise typer.Exit(code=1)

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
            allow_flow_text_fallback=allow_flow_text_fallback,
            director_mode=director_mode,
            episode_num=episode,
            simulate_defect_block=simulate_defect_block,
            video_qa=video_qa,
            video_qa_model=video_qa_model,
            video_qa_batch_size=video_qa_batch_size,
            max_patch_passes=max_patch_passes,
            target_duration=duration,
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

        console.print(f"  + Thumbnail locked -> [dim]{thumbnail_path}[/dim]")

        shorts_path = None
        if export_shorts:
            shorts_path = out_dir / f"{slug}_vertical_9x16.mp4"
            console.print(f"\n[bold cyan][VERTICAL] Multiplexing 9:16 vertical cut alongside 16:9 master...[/bold cyan]")
            try:
                import editor
                if final_mp4 and Path(final_mp4).is_file():
                    editor.export_shorts_multiplex(
                        input_path=final_mp4,
                        out_path=shorts_path,
                        max_duration=45.0,
                        start_time=0.0,
                    )
                    console.print(f"  + Vertical cut (9:16) produced -> [dim]{shorts_path}[/dim]")
                else:
                    logger.warning("Master video not found on disk; skipping vertical cut multiplex.")
            except Exception as exc:
                logger.warning(f"Vertical cut multiplex generation notice: {exc}")

        shorts_line = f"\n[VERTICAL] [b]Vertical Cut (9:16):[/b] {shorts_path}" if (shorts_path and shorts_path.is_file()) else ""
        console.print(Panel(
            f"[bold green][DONE] Film Successfully Produced![/bold green]\n\n"
            f"[VIDEO] [b]Final MP4:[/b] {final_mp4}\n"
            f"[THUMBNAIL] [b]Thumbnail:[/b] {thumbnail_path}{shorts_line}\n"
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
        help="[Primary Engine] Produce a complete film through Flow CDP, voice, and FFmpeg. Set --max-patch-passes to 0 or 1 for selective video repairs. Supports --veo-mode (quality/fast/lite).",
    )(produce_film)
