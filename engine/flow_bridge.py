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
from services.boundary_inspector import extract_video_frame, inspect_transition_boundary
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
from services.series_architect import build_canonical_rigor_mortis_world_state
from services.text_sanitizer import sanitize_spoken_text

logger = logging.getLogger("grok_flow_bridge")


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


def synthesize_dry_run_video_block(out_mp4: Path, duration: float = 4.0, aspect: str = "16:9") -> None:
    """Generate dry-run video block fixture using local FFmpeg lavfi color."""
    ffmpeg = config.resolve_ffmpeg()
    dims = "1920x1080" if aspect == "16:9" else "1080x1920"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={dims}:r=30",
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
    sfx_provider: str = "ffmpeg_lavfi",
    hero_plate_path: Path | None = None,
    director_mode: bool = True,
) -> Path:
    """Take Grok Studio planned scenes and execute full physical render with Flow + Voice + FFmpeg."""
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

    if dry_run:
        expected_duration = sum(float(s.get("duration", block_duration)) for s in scenes)
        synthesize_dry_run_audio(vo_path, duration=expected_duration)
        words = make_mock_words(scenes, expected_duration)
        measured_duration = expected_duration
    elif vo_path.is_file() and words_path.is_file() and vo_path.stat().st_size > 10000:
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
    logger.info(f"[1/3] Voiceover ready: {measured_duration:.2f}s, {len(words)} timed words.")

    # Step 2: Native Dynamic Video Block Allocation & Transition Boundary QA
    aligned_scenes: list[dict[str, Any]] = []
    accumulated_dur = 0.0
    scene_idx = 0

    while (accumulated_dur < measured_duration) or (scene_idx < len(scenes)):
        if scene_idx < len(scenes):
            sc = dict(scenes[scene_idx])
            raw_dur = float(sc.get("duration", block_duration))
            sc["duration"] = snap_to_veo_duration(raw_dur)
        else:
            prev = aligned_scenes[-1] if aligned_scenes else (scenes[0] if scenes else {})
            rem = measured_duration - accumulated_dur
            sc = {
                "id": f"scene_{len(aligned_scenes)+1:02d}",
                "narration": "",
                "visual_prompt": f"{prev.get('visual_prompt', '')}, continuous physical realism",
                "motion_prompt": f"{prev.get('motion_prompt', '')}, continuous camera movement",
                "duration": snap_to_veo_duration(rem if rem > 0 else 4.0),
            }
        aligned_scenes.append(sc)
        accumulated_dur += sc["duration"]
        scene_idx += 1

    # Tail optimization: ensure the final block fits the remaining audio duration without waste
    if len(aligned_scenes) > 1:
        prev_sum = sum(float(s["duration"]) for s in aligned_scenes[:-1])
        remaining = measured_duration - prev_sum
        if remaining > 0:
            aligned_scenes[-1]["duration"] = snap_to_veo_duration(remaining)
        else:
            aligned_scenes[-1]["duration"] = 4.0
    elif len(aligned_scenes) == 1:
        aligned_scenes[0]["duration"] = snap_to_veo_duration(measured_duration)

    logger.info(f"[2/3] Generating {len(aligned_scenes)} dynamic video blocks (durations: {[s['duration'] for s in aligned_scenes]}) via Flow CDP...")

    block_paths: list[Path] = []
    if dry_run:
        for i, sc in enumerate(aligned_scenes, 1):
            block_file = out_dir / "blocks" / f"block_{i:02d}.mp4"
            dur = float(sc.get("duration", block_duration))
            synthesize_dry_run_video_block(block_file, duration=dur, aspect=aspect_ratio)
            
            # Cross-block transition inspection
            if len(block_paths) >= 1:
                qa_report = await inspect_transition_boundary(
                    hero_plate_path=hero_plate_path,
                    block_n_video=block_paths[-1],
                    block_n_plus_1_video=block_file,
                    dry_run=True,
                )
                logger.info(
                    f"Transition Boundary QA [Block {i-1} -> {i}]: score={qa_report.continuity_score:.2f} "
                    f"({qa_report.inspected_by}, passed={qa_report.passed})"
                )
            block_paths.append(block_file)
    else:
        import cv2
        video_prov = get_video_provider("playwright_flow")
        slug = sanitize_slug(project_title)
        if slug == "project-rigor-mortis-episode-01":
            world_state = build_canonical_rigor_mortis_world_state()
        else:
            world_state = WorldState(project_id=slug)

        for i, sc in enumerate(aligned_scenes, 1):
            block_file = out_dir / "blocks" / f"block_{i:02d}.mp4"
            dur = float(sc.get("duration", block_duration))
            vp = str(sc.get("visual_prompt", "")).strip()
            mp = str(sc.get("motion_prompt", "")).strip()
            full_prompt = f"{vp}. {mp}" if vp else mp

            if block_file.is_file() and block_file.stat().st_size > 10000:
                logger.info(f"Block {i}/{len(aligned_scenes)} already rendered -> reusing: {block_file.name}")
                block_paths.append(block_file)
                continue

            # Extract exit-frame from previous block for abra_i2v temporal pixel lock
            start_frame_path: Path | None = None
            if block_paths and block_paths[-1].is_file():
                exit_img = extract_video_frame(block_paths[-1], position="last")
                if exit_img is not None:
                    kf_path = out_dir / "keyframes" / f"exit_frame_b{i-1:02d}.jpg"
                    cv2.imwrite(str(kf_path), exit_img)
                    start_frame_path = kf_path
                    logger.info(f"Conditioning Block {i} on previous block exit frame: {kf_path.name}")

            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Rendering block {i}/{len(aligned_scenes)} (attempt {attempt}/{max_retries}) via Flow: {full_prompt[:60]}...")
                    await video_prov.animate_block(
                        start_frame=start_frame_path,
                        end_frame=None,
                        motion_prompt=full_prompt,
                        out_path=block_file,
                        duration=dur,
                    )
                    if block_file.is_file() and block_file.stat().st_size > 10000:
                        # Inspect transition boundary with previous block
                        if len(block_paths) >= 1:
                            qa_rep = await inspect_transition_boundary(
                                hero_plate_path=hero_plate_path,
                                block_n_video=block_paths[-1],
                                block_n_plus_1_video=block_file,
                            )
                            logger.info(
                                f"Transition Boundary QA [Block {i-1} -> {i}]: score={qa_rep.continuity_score:.2f} "
                                f"({qa_rep.inspected_by}, passed={qa_rep.passed})"
                            )
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
                        break
                except Exception as exc:
                    logger.warning(f"Block {i} attempt {attempt} failed: {exc}")
                    state_dir = block_file.parent / f"{block_file.stem}.flow-state"
                    if state_dir.is_dir():
                        shutil.rmtree(state_dir, ignore_errors=True)
                    if attempt == max_retries:
                        raise
                    await asyncio.sleep(4.0 * attempt)
            block_paths.append(block_file)

    # Step 3: FFmpeg Assembly, Dual-Stage SFX & Foley Bed, Karaoke Subtitles
    logger.info("[3/3] Mixing broadcast audio bed, procedural SFX foley, and subtitles with FFmpeg...")
    target_len = round(measured_duration + config.TAIL_HOLD, 3)

    # Derive and resolve procedural SFX cues
    sfx_cues: list[dict[str, Any]] = []
    sfx_cache_dir = out_dir / "audio" / "sfx"
    sfx_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        sfx_prov = get_sfx_provider(sfx_provider or os.getenv("SFX_PROVIDER", "ffmpeg_lavfi"))
        curr_t = 0.0
        for sc_idx, sc in enumerate(aligned_scenes):
            sc_dur = float(sc.get("duration", block_duration))
            txt = f"{sc.get('narration', '')} {sc.get('visual_prompt', '')}".lower()
            foley_req = None
            if any(k in txt for k in ("sonar", "ping", "submarine", "depth", "ocean", "trench")):
                foley_req = ("abyssal submarine sonar ping", 2.0)
            elif any(k in txt for k in ("glitch", "spark", "circuit", "cyber", "terminal", "hack", "retinal")):
                foley_req = ("cybernetic electric glitch burst", 1.2)
            elif any(k in txt for k in ("airlock", "vent", "steam", "hiss", "pressure", "depressuriz", "decompression", "vacuum")):
                foley_req = ("pressurized valve airlock hiss", 1.8)
            elif any(k in txt for k in ("metal", "blade", "sword", "clash", "portcullis", "shield", "arrow", "rampart")):
                foley_req = ("iron metal clash impact", 1.5)
            elif any(k in txt for k in ("slam", "door", "lock", "deadbolt", "impact", "crash", "collision")):
                foley_req = ("sub-bass impact door slam", 1.8)
            elif any(k in txt for k in ("whoosh", "sprint", "whip", "leap", "burst", "hatch")):
                foley_req = ("cinematic camera whip whoosh transition", 1.5)
            elif any(k in txt for k in ("heartbeat", "pulse", "decibel", "breath", "whisper", "creeping")):
                foley_req = ("deep tension heartbeat pulse", 2.2)
            elif any(k in txt for k in ("rain", "wind", "storm", "fog", "corridor", "drone", "radiation")):
                foley_req = ("atmospheric wind drone", 2.5)

            if foley_req:
                f_prompt, f_dur = foley_req
                asset = await sfx_prov.resolve_asset(
                    {"prompt": f_prompt, "duration": min(f_dur, sc_dur), "asset_id": f"sfx_sc{sc_idx+1:02d}"},
                    cache_dir=sfx_cache_dir,
                )
                sfx_cues.append({
                    "cue_id": asset.get("asset_id", f"cue_{sc_idx}"),
                    "local_path": str(asset["local_path"]),
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
        )
        music_path = Path(generated_bed)

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
    )

    if dry_run and not final_mp4.is_file():
        if block_paths and block_paths[0].is_file():
            shutil.copy2(block_paths[0], final_mp4)
        else:
            synthesize_dry_run_video_block(final_mp4, duration=4.0, aspect=aspect_ratio)

    # Seal ending continuity state into out_dir
    last_scene = aligned_scenes[-1] if aligned_scenes else {}
    last_delta = last_scene.get("delta_state", {})
    last_narration = last_scene.get("narration", "")
    ending_summary = f"Survivor behind oak barricade with pry-bar. Telemetry: {last_delta}. Action: '{last_narration}'"
    save_series_continuity(
        series_dir=out_dir,
        episode_num=1,
        ending_state=ending_summary,
        telemetry=last_delta,
        world_state=world_state.to_dict() if 'world_state' in locals() and hasattr(world_state, 'to_dict') else None,
    )

    logger.info(f"Production successfully completed! Final film: {final_mp4}")
    return final_mp4
