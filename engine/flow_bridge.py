"""Flow & Deepgram & FFmpeg Factory Bridge for Grok Imagine Cinematic Studio.

Connects Grok Studio's 25-agent narrative planning (Character DNA, Wardrobe Lock,
3-act structure, MOMENTUM_VECTOR handoffs) to the local physical execution engine:
- Deepgram Aura-2 (voiceover + word timestamps)
- Google Flow CDP Port 9223 (Veo / Imagen 3 video blocks)
- FFmpeg Broadcast Editor (-14 LUFS, sidechain ducking, Libass karaoke subtitles)
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure engine is on sys.path
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

import captions
import config
import editor
from providers.factory import (
    get_image_provider,
    get_llm_provider,
    get_sfx_provider,
    get_video_provider,
    get_voice_provider,
)
from services.audio_bed import generate_audio_bed
from services.boundary_inspector import (
    BoundaryQAReport,
    TRANSITION_SCORE_THRESHOLD,
    extract_video_frame,
    inspect_transition_boundary,
    write_qa_report,
)
from services.sfx_categorizer import (
    SfxCategoryMatch,
    auto_categorize_scene_sfx,
    extract_sfx_category,
)
from services.continuity import (
    build_continuity_prompt_suffix,
    load_series_continuity,
    save_series_continuity,
)
from services.directing_rules import get_cinematic_guidelines
from services.director_agent import (
    DirectorDecision,
    WorldState,
    arbitrate_decision,
    commit_canon_delta,
    evaluate_visual_delta,
)
from services.duration_packer import pack_durations_to_veo_blocks, is_data_broll_scene
from services.prompt_compiler import compile_udse_prompt
try:
    from services.series_architect import build_canonical_rigor_mortis_world_state
except ImportError:
    try:
        from engine.services.series_architect import build_canonical_rigor_mortis_world_state
    except ImportError:
        try:
            from archive.legacy_services.series_architect import build_canonical_rigor_mortis_world_state
        except ImportError:
            def build_canonical_rigor_mortis_world_state():
                return WorldState(project_id="project-rigor-mortis-episode-01")
from services.text_sanitizer import sanitize_spoken_text
from services.remotion_bridge import render_remotion_broll, resolve_template_name

logger = logging.getLogger("grok_flow_bridge")


def is_scene_data_broll(sc: dict[str, Any]) -> bool:
    """Determine whether a scene specifies a procedural/motion graphics [DATA_BROLL]."""
    return is_data_broll_scene(sc)


_CACHE_SCHEMA = 1


def production_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps({"schema": _CACHE_SCHEMA, "payload": payload},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cache_sidecar(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".cache.json")


def cache_matches(path: Path, fingerprint: str) -> bool:
    try:
        saved = json.loads(cache_sidecar(path).read_text(encoding="utf-8"))
        return path.is_file() and saved.get("fingerprint") == fingerprint
    except (OSError, ValueError, TypeError):
        return False


def write_cache_fingerprint(path: Path, fingerprint: str) -> None:
    cache_sidecar(path).write_text(json.dumps({"schema": _CACHE_SCHEMA,"fingerprint":fingerprint}),encoding="utf-8")


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remove_flow_state_cache(state_dir: Path, out_dir: Path) -> None:
    """Delete only resolved state directories contained by this production."""
    root = out_dir.resolve()
    target = state_dir.resolve()
    if target == root or not target.is_relative_to(root):
        raise RuntimeError(f"Flow state cache escapes the production directory: {state_dir}")
    if state_dir.is_dir():
        shutil.rmtree(state_dir)


def aligned_block_scene(bp) -> dict[str, Any]:
    """Carry authored production metadata into every audio-aligned source block."""
    scene = dict(bp.scene_metadata)
    scene.update(id=bp.scene_id, duration=bp.veo_duration,
                 audio_t0=bp.audio_t0, audio_t1=bp.audio_t1,
                 pad_tail_seconds=bp.pad_tail_seconds, freeze_tail_seconds=bp.freeze_tail_seconds,
                 visual_prompt=bp.visual_prompt, motion_prompt=bp.motion_prompt, narration=bp.narration)
    template = (scene.get("data_broll_template") or scene.get("template_name")
                or scene.get("broll_template") or scene.get("broll_type"))
    if template:
        scene["template_name"] = template
    payload = next((scene[key] for key in ("data_broll_payload", "data_payload", "payload", "broll_props")
                    if scene.get(key) is not None), None)
    if payload is not None:
        scene["data_payload"] = payload
    return scene


def validate_video_source(path: Path, *, is_broll: bool, width: int, height: int) -> None:
    """Validate every source, including a first/only block without a transition."""
    frame = extract_video_frame(path, position="first")
    if frame is None:
        raise RuntimeError(f"Unreadable video source: {path.name}")
    actual_height, actual_width = frame.shape[:2]
    if actual_height <= 0 or actual_width <= 0:
        raise RuntimeError(f"Invalid video source dimensions: {path.name}")
    if abs(actual_width / actual_height - width / height) >= .02:
        raise RuntimeError(f"Invalid video source aspect ratio: {path.name}")
    if is_broll and (actual_width, actual_height) != (width, height):
        raise RuntimeError(f"Invalid B-roll source resolution {actual_width}x{actual_height}: {path.name}")



def snap_to_veo_duration(duration: float) -> float:
    """Snap a duration to the nearest supported Google Veo tier: [4.0, 6.0, 8.0, 10.0]."""
    tiers = [4.0, 6.0, 8.0, 10.0]
    return min(tiers, key=lambda t: abs(t - duration))


def sanitize_slug(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "-", slug)[:40] or "project"


def synthesize_dry_run_audio(out_wav: Path, duration: float = 16.0) -> None:
    """Generate dry-run audio fixture using local FFmpeg lavfi sine tone."""
    ffmpeg = config.resolve_ffmpeg()
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000",
        "-t", f"{duration:.3f}",
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "1",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True)


def synthesize_dry_run_video_block(
    out_mp4: Path,
    duration: float = 4.0,
    aspect: str = "16:9",
    color: str = "black",
) -> None:
    """Generate dry-run video block fixture using local FFmpeg lavfi color."""
    ffmpeg = config.resolve_ffmpeg()
    dims = "1920x1080" if aspect == "16:9" else "1080x1920"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={dims}:r=30",
        "-t", f"{duration:.3f}",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)


def make_mock_words(scenes: list[dict[str, Any]], total_duration: float) -> list[dict[str, Any]]:
    """Synthesize evenly-spaced word timings for dry-run captions."""
    all_words: list[str] = []
    for sc in scenes:
        clean_text = sanitize_spoken_text(sc.get("narration", ""))
        all_words.extend(clean_text.split())
    if not all_words:
        all_words = ["Grok", "Cinematic", "Studio", "Production"]

    step = total_duration / max(1, len(all_words))
    words: list[dict[str, Any]] = []
    for i, w in enumerate(all_words):
        start = round(i * step, 3)
        end = round((i + 1) * step, 3)
        words.append({
            "text": w,
            "start": start,
            "end": end,
            "is_emphasis": (i % 5 == 0),
        })
    return words


async def execute_grok_flow_production(
    *,
    project_title: str,
    genre: str = "Sci-Fi",
    scenes: list[dict[str, Any]],
    out_dir: Path,
    aspect_ratio: str = "16:9",
    dry_run: bool = False,
    no_music: bool = False,
    no_captions: bool = False,
    block_duration: float = 6.0,
    voice_provider: str = "deepgram",
    sfx_provider: str | None = None,
    hero_plate_path: Path | None = None,
    director_mode: bool = True,
    episode_num: int = 1,
    simulate_defect_block: int | None = None,
) -> Path:
    """Take Grok Studio planned scenes and execute full physical render with Flow + Voice + FFmpeg."""
    if not dry_run and any(scene.get("simulation_only") for scene in scenes):
        raise ValueError("Simulation scenes cannot be rendered by live production")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audio").mkdir(parents=True, exist_ok=True)
    (out_dir / "blocks").mkdir(parents=True, exist_ok=True)
    (out_dir / "keyframes").mkdir(parents=True, exist_ok=True)

    if aspect_ratio == "16:9":
        config.LONGFORM_MODE = True
        config.WIDTH = 1920
        config.HEIGHT = 1080
        config.ASPECT_RATIO_STRING = "16:9"
    else:
        config.LONGFORM_MODE = False
        config.WIDTH = 1080
        config.HEIGHT = 1920
        config.ASPECT_RATIO_STRING = "9:16"

    logger.info(f"--- Grok Studio -> Flow Production: {project_title} ---")
    logger.info(f"Target Output Directory: {out_dir}")
    logger.info(f"Scenes count: {len(scenes)} (dry_run={dry_run}, aspect={aspect_ratio}, voice={voice_provider})")

    # Step 1: Voiceover & Timings (100% English Invariant)
    vo_path = out_dir / "audio" / "vo.wav"
    words_path = out_dir / "words.json"
    beats = [
        {"id": s.get("id", f"scene_{i+1:02d}"), "text": sanitize_spoken_text(s.get("narration", ""))}
        for i, s in enumerate(scenes)
    ]

    voice_fingerprint = production_fingerprint({
        "renderer": "voice-alignment-v1", "beats": beats, "provider": voice_provider, "dry_run": dry_run,
        "settings": {key: value for key, value in os.environ.items()
                     if key.startswith(("DEEPGRAM_", "ELEVENLABS_", "VOYSLITY_", "TTS_", "VOICE_"))
                     and not any(secret in key for secret in ("KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE"))},
    })
    if dry_run:
        expected_duration = sum(float(s.get("duration", block_duration)) for s in scenes)
        synthesize_dry_run_audio(vo_path, duration=expected_duration)
        words = make_mock_words(scenes, expected_duration)
        measured_duration = expected_duration
    elif cache_matches(vo_path, voice_fingerprint) and words_path.is_file() and vo_path.stat().st_size > 10000:
        logger.info(f"[1/3] Voiceover already exists -> reusing: {vo_path}")
        words_data = json.loads(words_path.read_text(encoding="utf-8"))
        words = words_data.get("words", [])
        measured_duration = float(words_data.get("duration", 0.0))
    else:
        voice = get_voice_provider(voice_provider)
        voice_res = await voice.generate_narration(beats=beats, out_path=vo_path, lang="en")
        vo_path = Path(voice_res["vo_path"])
        words = voice_res.get("words", [])
        measured_duration = float(voice_res.get("duration", 0.0))

    words_path.write_text(json.dumps({"words": words, "duration": measured_duration}, indent=2), encoding="utf-8")
    write_cache_fingerprint(vo_path, voice_fingerprint)
    logger.info(f"[1/3] Voiceover ready: {measured_duration:.2f}s, {len(words)} timed words.")

    # Step 2: Native Dynamic Video Block Allocation via DurationPacker (Grok 4.6 Standard)
    block_plans = pack_durations_to_veo_blocks(
        scenes=scenes,
        total_audio_duration=measured_duration,
        words=words,
        default_block_duration=block_duration,
    )
    aligned_scenes = [aligned_block_scene(bp) for bp in block_plans]

    logger.info(f"[2/3] Generating {len(aligned_scenes)} dynamic video blocks (durations: {[s['duration'] for s in aligned_scenes]}) via Flow CDP...")

    block_paths: list[Path] = []
    qa_evaluations: list[dict[str, Any]] = []
    # Track which blocks are procedural [DATA_BROLL] for zero-cost routing and QA exception
    broll_flags = [is_scene_data_broll(s) for s in aligned_scenes]
    # Unified Video Block Generation & Transition Boundary QA (Dry-run & Live parity)
    import cv2
    video_prov = None if dry_run else get_video_provider("playwright_flow")
    slug = sanitize_slug(project_title)
    if slug == "project-rigor-mortis-episode-01":
        world_state = build_canonical_rigor_mortis_world_state()
    else:
        world_state = WorldState(project_id=slug)

    for i, sc in enumerate(aligned_scenes, 1):
        block_file = out_dir / "blocks" / f"block_{i:02d}.mp4"
        dur = float(sc.get("duration", block_duration))
        sc_dur = dur
        vp = str(sc.get("visual_prompt", "")).strip()
        mp = str(sc.get("motion_prompt", "")).strip()
        is_broll = broll_flags[i - 1]
        transition_is_broll = bool(is_broll or (i >= 2 and broll_flags[i - 2]))

        # Compile with UDSE v4.3 and active Visibility Gating
        compiled_vp = compile_udse_prompt(
            visual_prompt=vp,
            world_state=world_state,
            shot_spec=sc,
        ) if vp else ""
        full_prompt = f"{compiled_vp}. {mp}" if compiled_vp else mp

        depends_on_previous = bool(not is_broll and i >= 2 and not broll_flags[i-2])
        block_fingerprint = production_fingerprint({
            "renderer": "flow-remotion-audio-slots-v2", "scene": sc, "prompt": full_prompt,
            "size": [config.WIDTH, config.HEIGHT], "duration": dur, "dry_run": dry_run,
            "model": os.getenv("FLOW_VIDEO_MODEL", ""),
            "quality": os.getenv("FLOW_VIDEO_TEST_QUALITY" if dry_run else "FLOW_VIDEO_REAL_QUALITY", ""),
            "previous_reference": file_fingerprint(block_paths[-1]) if depends_on_previous else None,
        })
        if block_file.is_file() and not cache_matches(block_file, block_fingerprint):
            logger.info("Block %s source fingerprint changed or missing; regenerate", i)
            block_file.unlink()
            state_dir = block_file.parent / f"{block_file.stem}.flow-state"
            remove_flow_state_cache(state_dir, out_dir)
        if simulate_defect_block is not None and i == simulate_defect_block:
            block_file.unlink(missing_ok=True)

        if block_file.is_file() and block_file.stat().st_size > 1000:
            try:
                validate_video_source(block_file, is_broll=is_broll, width=config.WIDTH, height=config.HEIGHT)
                cached_probe = editor.probe(block_file, config.resolve_ffmpeg())
                if cached_probe.duration is not None and abs(float(cached_probe.duration) - sc_dur) > 0.5:
                    logger.info(f"Block {i}/{len(aligned_scenes)} duration mismatch (cached {cached_probe.duration:.1f}s != requested {sc_dur:.1f}s) -> re-generating")
                    block_file.unlink(missing_ok=True)
            except Exception as invalid_cache:
                logger.warning("Cached source is invalid; regenerate: %s", invalid_cache)
                block_file.unlink(missing_ok=True)

        if block_file.is_file() and block_file.stat().st_size > 1000:
            logger.info(f"Block {i}/{len(aligned_scenes)} already rendered -> reusing: {block_file.name}")
            if len(block_paths) >= 1:
                qa_rep = await inspect_transition_boundary(
                    hero_plate_path=hero_plate_path,
                    block_n_video=block_paths[-1],
                    block_n_plus_1_video=block_file,
                    dry_run=dry_run,
                    is_data_broll=transition_is_broll,
                    expected_width=config.WIDTH, expected_height=config.HEIGHT,
                    data_broll_sides=(broll_flags[i - 2], is_broll),
                )
                qa_evaluations.append({
                    "transition": f"Block {i-1:02d} -> Block {i:02d}",
                    "from_block": block_paths[-1].name,
                    "to_block": block_file.name,
                    "attempt": 1,
                    "continuity_score": round(float(qa_rep.continuity_score), 3),
                    "passed": bool(qa_rep.passed),
                    "threshold": TRANSITION_SCORE_THRESHOLD,
                    "violations": list(qa_rep.violations),
                    "corrective_prompt": str(qa_rep.corrective_prompt),
                    "inspected_by": str(qa_rep.inspected_by),
                })
                if not qa_rep.passed:
                    raise RuntimeError(f"Cached transition failed QA: {block_file.name}: {qa_rep.violations}")
            block_paths.append(block_file)
            continue

        # Extract exit-frame from previous block for abra_i2v temporal pixel lock
        start_frame_path: Path | None = None
        if not is_broll and block_paths and not broll_flags[i - 2] and block_paths[-1].is_file():
            exit_img = extract_video_frame(block_paths[-1], position="last")
            if exit_img is not None:
                kf_path = out_dir / "keyframes" / f"exit_frame_b{i-1:02d}.jpg"
                cv2.imwrite(str(kf_path), exit_img)
                start_frame_path = kf_path
                logger.info(f"Conditioning Block {i} on previous block exit frame: {kf_path.name}")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                is_defect_attempt = bool(
                    simulate_defect_block is not None
                    and i == simulate_defect_block
                    and attempt == 1
                )

                if is_broll:
                    # Pure engine: Render motion graphics B-Roll directly with Remotion (no Flow CDP/Veo call)
                    broll_tmpl = (sc.get("data_broll_template") or sc.get("template_name")
                                  or sc.get("broll_template") or sc.get("broll_type") or "")
                    broll_payload = next((sc[key] for key in
                        ("data_broll_payload", "data_payload", "payload", "broll_props")
                        if sc.get(key) is not None), {})
                    if not broll_tmpl:
                        raise ValueError("Data B-roll requires an explicit template_name or data_broll_template")
                    logger.info(
                        f"Rendering Remotion B-Roll block {i}/{len(aligned_scenes)} ({broll_tmpl}, duration={dur:.1f}s)..."
                    )
                    if dry_run:
                        try:
                            render_remotion_broll(
                                template_name=broll_tmpl,
                                data_payload=broll_payload,
                                output_path=block_file,
                                width=config.WIDTH,
                                height=config.HEIGHT,
                                fps=60,
                                duration_seconds=dur,
                            )
                        except Exception as remotion_err:
                            logger.warning(f"Dry-run Remotion render skipped/fallback: {remotion_err}")
                            color = "red" if is_defect_attempt else "black"
                            synthesize_dry_run_video_block(block_file, duration=dur, aspect=aspect_ratio, color=color)
                    else:
                        render_remotion_broll(
                            template_name=broll_tmpl,
                            data_payload=broll_payload,
                            output_path=block_file,
                            width=config.WIDTH,
                            height=config.HEIGHT,
                            fps=60,
                            duration_seconds=dur,
                        )
                elif dry_run:
                    color = "red" if is_defect_attempt else "black"
                    synthesize_dry_run_video_block(block_file, duration=dur, aspect=aspect_ratio, color=color)
                else:
                    logger.info(f"Rendering block {i}/{len(aligned_scenes)} (attempt {attempt}/{max_retries}) via Flow: {full_prompt[:60]}...")
                    await video_prov.animate_block(
                        start_frame=start_frame_path,
                        end_frame=None,
                        motion_prompt=full_prompt,
                        out_path=block_file,
                        duration=dur,
                    )

                if not block_file.is_file() or block_file.stat().st_size <= 1000:
                    raise RuntimeError(f"Renderer did not produce a valid video source: {block_file.name}")
                validate_video_source(block_file, is_broll=is_broll, width=config.WIDTH, height=config.HEIGHT)

                if block_file.is_file() and block_file.stat().st_size > 1000:
                    # Inspect transition boundary with previous block
                    if len(block_paths) >= 1:
                        if is_defect_attempt:
                            qa_rep = BoundaryQAReport(
                                continuity_score=0.42,
                                passed=False,
                                violations=[
                                    "Ontology break: E_DOOR_01 solid oak slab transformed into transparent glass window",
                                    "180-degree camera axis break and palette mutation",
                                ],
                                corrective_prompt="Lock E_DOOR_01 as solid opaque oak slab, zero glass panels",
                                inspected_by="simulated_continuity_defect",
                            )
                        else:
                            qa_rep = await inspect_transition_boundary(
                                hero_plate_path=hero_plate_path,
                                block_n_video=block_paths[-1],
                                block_n_plus_1_video=block_file,
                                dry_run=dry_run,
                                is_data_broll=transition_is_broll,
                                expected_width=config.WIDTH, expected_height=config.HEIGHT,
                                data_broll_sides=(broll_flags[i - 2], is_broll),
                            )

                        qa_evaluations.append({
                            "transition": f"Block {i-1:02d} -> Block {i:02d}",
                            "from_block": block_paths[-1].name if block_paths else None,
                            "to_block": block_file.name,
                            "attempt": attempt,
                            "continuity_score": round(float(qa_rep.continuity_score), 3),
                            "passed": bool(qa_rep.passed),
                            "threshold": TRANSITION_SCORE_THRESHOLD,
                            "violations": list(qa_rep.violations),
                            "corrective_prompt": str(qa_rep.corrective_prompt),
                            "inspected_by": str(qa_rep.inspected_by),
                        })

                        heal_suffix = " [HEAL VERIFIED]" if attempt > 1 and qa_rep.passed else ""
                        logger.info(
                            f"Transition Boundary QA [Block {i-1} -> {i}]: score={qa_rep.continuity_score:.2f} "
                            f"({qa_rep.inspected_by}, passed={qa_rep.passed}){heal_suffix}"
                        )

                        if not qa_rep.passed and (transition_is_broll or not director_mode):
                            raise RuntimeError(f"Transition failed QA: {block_file.name}: {qa_rep.violations}")

                        if not qa_rep.passed and director_mode:
                            # Dynamically resolve target entity
                            target_entity_id = sc.get("focus_entity") or sc.get("entity_id")
                            if not target_entity_id:
                                for eid in world_state.entities:
                                    if eid.lower() in str(qa_rep.violations).lower() or eid.lower() in sc.get("visual_prompt", "").lower():
                                        target_entity_id = eid
                                        break
                            if not target_entity_id:
                                target_entity_id = next(iter(world_state.entities.keys()), "E_HERO_01")

                            delta = evaluate_visual_delta(
                                entity_id=target_entity_id,
                                before_desc=aligned_scenes[i - 2].get("visual_prompt", ""),
                                after_desc=sc.get("visual_prompt", ""),
                                continuity_score=qa_rep.continuity_score,
                                violations=qa_rep.violations,
                            )
                            action = arbitrate_decision(delta, world_state, current_attempt=attempt)
                            if action.decision == DirectorDecision.HEAL and attempt <= action.max_heal_attempts:
                                logger.warning(f"Director Agent: HEAL triggered ({action.reason}). Corrective: {action.corrective_prompt}")
                                heal_parts = [action.corrective_prompt]
                                if action.scoped_negatives:
                                    heal_parts.append(f"Avoid: {', '.join(action.scoped_negatives)}")
                                if action.reframe_strategy in ("tighter_mcu", "insert"):
                                    reframe_prefix = f"Tight medium close-up shot focusing directly on {target_entity_id}. "
                                    full_prompt = f"{reframe_prefix}{full_prompt}. {'. '.join(heal_parts)}"
                                else:
                                    full_prompt = f"{full_prompt}. {'. '.join(heal_parts)}"
                                block_file.unlink(missing_ok=True)
                                continue
                            elif action.decision == DirectorDecision.CANONIZE:
                                logger.info(f"Director Agent: CANONIZING emergent visual ({action.reason}).")
                                commit_canon_delta(world_state, delta)
                            else:
                                raise RuntimeError(f"Transition failed QA after corrective attempts: {block_file.name}")
                    break
            except Exception as exc:
                logger.warning(f"Block {i} attempt {attempt} failed: {exc}")
                state_dir = block_file.parent / f"{block_file.stem}.flow-state"
                remove_flow_state_cache(state_dir, out_dir)
                if attempt == max_retries:
                    raise
                if not dry_run:
                    await asyncio.sleep(4.0 * attempt)
        write_cache_fingerprint(block_file, block_fingerprint)
        block_paths.append(block_file)

    # Write visual transition QA report (including any failed transition logs)
    qa_report_path = out_dir / "qa_report.json"
    failed_transitions = [r for r in qa_evaluations if not r.get("passed")]
    qa_summary = {
        "project_title": project_title,
        "threshold": TRANSITION_SCORE_THRESHOLD,
        "total_transitions_inspected": len(qa_evaluations),
        "passed_count": len(qa_evaluations) - len(failed_transitions),
        "failed_count": len(failed_transitions),
        "overall_passed": len(failed_transitions) == 0,
        "failed_transitions": failed_transitions,
        "transitions": qa_evaluations,
    }
    write_qa_report(qa_summary, qa_report_path)
    logger.info(f"Transition QA report written -> {qa_report_path} (inspected={len(qa_evaluations)}, failed={len(failed_transitions)})")
    # Step 3: FFmpeg Assembly, Dual-Stage SFX & Foley Bed, Karaoke Subtitles
    logger.info("[3/3] Mixing broadcast audio bed, procedural SFX foley, and subtitles with FFmpeg...")
    timeline_durations = [float(s["audio_t1"]) - float(s["audio_t0"]) for s in aligned_scenes]
    target_len = measured_duration + config.TAIL_HOLD

    # Derive and resolve procedural SFX cues
    sfx_cues: list[dict[str, Any]] = []
    sfx_cache_dir = out_dir / "audio" / "sfx"
    sfx_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        prov_name = "ffmpeg_lavfi" if dry_run else (sfx_provider or os.getenv("SFX_PROVIDER", "gradio_space"))
        sfx_prov = get_sfx_provider(prov_name)
        curr_t = 0.0
        for sc_idx, sc in enumerate(aligned_scenes):
            sc_dur = timeline_durations[sc_idx]
            category_match = extract_sfx_category(sc)
            if category_match:
                f_prompt = category_match.audiogen_prompt
                f_dur = category_match.duration
                f_cat = category_match.category
                tags = category_match.tags
                asset = await sfx_prov.resolve_asset(
                    {
                        "prompt": f_prompt,
                        "duration": min(f_dur, sc_dur),
                        "asset_id": f"sfx_sc{sc_idx+1:02d}_{f_cat}",
                        "tags": tags,
                        "category": f_cat,
                    },
                    cache_dir=sfx_cache_dir,
                )
                sfx_cues.append({
                    "cue_id": asset.get("asset_id", f"cue_{sc_idx}"),
                    "local_path": str(asset["local_path"]),
                    "category": f_cat,
                    "prompt": f_prompt,
                    "start": round(curr_t, 3),
                    "end": round(min(target_len, curr_t + min(f_dur, sc_dur)), 3),
                    "gain_db": -12.0,
                })
            curr_t += sc_dur
        logger.info(f"Integrated {len(sfx_cues)} procedural SFX foley cues into audio mix.")
    except Exception as sfx_err:
        logger.warning(f"SFX synthesis encountered notice: {sfx_err}. Continuing with music bed.")

    music_path: Path | None = None
    if not no_music:
        mood = "tension_pulse" if aspect_ratio == "16:9" else "clinical_drone"
        generated_bed = generate_audio_bed(
            mood=mood,
            duration_seconds=measured_duration + config.TAIL_HOLD + 2.0,
            output_dir=str(out_dir / "audio"),
            dry_run=dry_run,
        )
        music_path = Path(generated_bed)

    logger.info(
        f"[AUDIO] 3 Audio Layers Active in Final Mix:\n"
        f"  • Layer 1 (TTS Voiceover): {voice_provider.upper()} ({measured_duration:.2f}s, {len(words)} timed words)\n"
        f"  • Layer 2 (Background Music Bed): {music_path.name if music_path else 'None'} (-14 LUFS, TTS Sidechain Ducked)\n"
        f"  • Layer 3 (SFX Foley): {len(sfx_cues)} cues via {sfx_prov.__class__.__name__}"
    )

    captions_path: Path | None = None
    if not no_captions:
        is_historical = any(k in str(genre).lower() for k in ("history", "historical", "antiquity", "ancient", "period piece", "ww1", "ww2"))
        ass_content = captions.build_ass(
            words=words,
            total_duration=target_len,
            is_longform=(aspect_ratio == "16:9"),
            historical_stamp=is_historical,
            topic=project_title if is_historical else None,
        )
        captions_path = out_dir / "captions.ass"
        captions_path.write_text(ass_content, encoding="utf-8")

    # Render explicit broadcast 3-layer master audio track
    master_audio_path = out_dir / "audio" / "master_audio_3layer.wav"
    try:
        if not dry_run and vo_path.is_file():
            editor.mix_3_audio_layers(
                vo_path=vo_path,
                music_path=music_path,
                sfx_cues=sfx_cues,
                out_path=master_audio_path,
                target_duration=target_len,
            )
    except Exception as exc:
        logger.debug("3-layer audio track render skipped: %s", exc)

    final_mp4 = out_dir / "final_film.mp4"
    editor.render(
        block_paths=block_paths,
        vo_path=vo_path,
        out_path=final_mp4,
        punch_times=[],
        music_path=music_path,
        captions_path=captions_path,
        dry_run=dry_run,
        target_len=target_len,
        sfx_cues=sfx_cues,
        timeline_durations=timeline_durations,
    )

    if dry_run and not final_mp4.is_file():
        if block_paths and block_paths[0].is_file():
            shutil.copy2(block_paths[0], final_mp4)
        else:
            synthesize_dry_run_video_block(final_mp4, duration=4.0, aspect=aspect_ratio)

    # Seal ending continuity state into out_dir (ADR-090 Zero-Hardcoding)
    last_scene = aligned_scenes[-1] if aligned_scenes else {}
    last_delta = last_scene.get("delta_state", {})
    last_narration = last_scene.get("narration", "")
    ending_summary = f"Concluded Episode {episode_num} of {project_title}: {last_narration}. Telemetry: {last_delta}"
    save_series_continuity(
        series_dir=out_dir,
        episode_num=episode_num,
        ending_state=ending_summary,
        telemetry=last_delta,
        world_state=world_state.to_dict() if 'world_state' in locals() and hasattr(world_state, 'to_dict') else None,
    )

    # Step 4: YouTube Thumbnail Automation (Phase 4 / R4 Standard)
    thumbnail_path = out_dir / "thumbnail.jpg"
    try:
        from services.thumbnail_generator import extract_climax_frame, generate_thumbnail

        climax_frame_img = None
        # Select climax video block (~72% duration mark in catastrophe/UDSE structure)
        if block_paths:
            climax_idx = min(len(block_paths) - 1, max(0, int(len(block_paths) * 0.72)))
            climax_block = block_paths[climax_idx]
            if climax_block.is_file():
                climax_frame_img = extract_climax_frame(climax_block)
                if climax_frame_img is not None:
                    kf_climax = out_dir / "keyframes" / "climax_frame.jpg"
                    climax_frame_img.convert("RGB").save(kf_climax, "JPEG")
        elif final_mp4.is_file():
            climax_frame_img = extract_climax_frame(final_mp4, position_ratio=0.72)

        if climax_frame_img is None and hero_plate_path and hero_plate_path.is_file():
            climax_frame_img = hero_plate_path

        generate_thumbnail(
            base_image=climax_frame_img,
            title_text=project_title,
            output_path=thumbnail_path,
        )
        logger.info(f"Generated YouTube thumbnail -> {thumbnail_path}")
    except Exception as thumb_err:
        logger.warning(f"Thumbnail generation notice: {thumb_err}")

    logger.info(f"Production successfully completed! Final film: {final_mp4}")
    return final_mp4

