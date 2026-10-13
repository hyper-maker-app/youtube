"""Dynamic documentary screenplay engine implementing the Script-Weaver pattern.

Generates episodic, source-grounded longform documentary scripts based on an
authoritative Historical Truth Sheet (HiAPIAI pattern). Implements first-person
sensory immersion ('In Media Res'), flexible scene durations (6s - 15s), balanced
Nova A-Roll moments, historical witness interviews, and people-free B-roll plates.

Zero network/transport calls are made in this module (strictly AST-clean).
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

import config
from services.character import (
    CharacterProfile,
    classify_shot_role,
    compile_character_shot_prompt,
    compile_witness_shot_prompt,
    detect_era,
    get_active_character,
    get_era_witness,
)
from services.curated_beats import get_gallipoli_curated_beats, get_pompeii_curated_beats
from services.historical_research import HistoricalTruthSheet, get_historical_truth_sheet
from services.prompt_compiler import (
    apply_ancient_equipment_rule,
    apply_clothing_lock,
    apply_movement_lock,
    compile_longform_broll_prompt,
    format_multi_shot_prompt,
    format_veo_cinematography_prompt,
)
from services.script_engine import Beat, Script, Shot
from services.story_weaver import StoryWeaver
from timeline import TimelinePlan


def generate_dynamic_screenplay(
    topic: str,
    timeline: TimelinePlan | None = None,
    truth_sheet: HistoricalTruthSheet | None = None,
    lang: str = "en",
    aspect_ratio: str = "16:9",
    target_blocks: int | None = None,
) -> Script:
    """Generate dynamic source-grounded documentary script with flexible durations and locks."""
    sheet = truth_sheet or get_historical_truth_sheet(topic)
    character = get_active_character()
    era = sheet.era
    w1 = sheet.historical_figures[0] if sheet.historical_figures else get_era_witness(era, 1)
    w2 = sheet.historical_figures[1] if len(sheet.historical_figures) > 1 else get_era_witness(era, 2)

    total_blocks = target_blocks or (timeline.block_count if timeline and timeline.block_count >= 5 else 8)
    
    curated = list(getattr(sheet, "curated_beats", []) or [])
    if (era == "world_war_i" or "pxixpeatiqc" in topic.casefold()) and any(term in topic.casefold() for term in ("gallipoli", "canakkale", "çanakkale", "dardanelles", "seyit", "mecidiye", "pxixpeatiqc")):
        curated = get_gallipoli_curated_beats(total_blocks, lang=lang, topic=topic)
    elif any(term in topic.casefold() for term in ("pompeii", "pompei", "vezüv", "vesuvius", "qzzoxhjtliw")):
        curated = get_pompeii_curated_beats(total_blocks, lang=lang)

    # 1. Generate dynamic beats
    beats: list[Beat] = []
    curated_shot_map: dict[int, dict[str, Any]] = {}

    if curated and len(curated) >= total_blocks:
        # Step through curated beats with exact or sampled mapping
        if len(curated) == total_blocks:
            chosen = curated
        else:
            step = (len(curated) - 1) / max(1, total_blocks - 1)
            indices = [min(len(curated) - 1, int(round(i * step))) for i in range(total_blocks)]
            indices[0] = 0
            indices[-1] = len(curated) - 1
            chosen = [curated[idx] for idx in indices]

        for i, c_beat in enumerate(chosen):
            b_idx = i + 1
            beats.append(Beat(
                index=b_idx,
                text=c_beat["text"],
                role=c_beat.get("role", "host_nova"),
                emphasis=list(c_beat.get("emphasis", ["ancient", "monument"])),
            ))
            curated_shot_map[b_idx] = c_beat
    else:
        # Dynamic sensory generation using StoryWeaver (5-phase dramatic flow + 4 visual locks)
        weaver = StoryWeaver(
            truth_sheet=sheet,
            character=character,
            total_blocks=total_blocks,
            lang=lang,
        )
        woven_beats = weaver.weave()
        for i, w_beat in enumerate(woven_beats):
            b_idx = i + 1
            beats.append(Beat(
                index=b_idx,
                text=w_beat["text"],
                role=w_beat.get("role", "narrator"),
                emphasis=list(w_beat.get("emphasis", ["ancient", "monument"])),
            ))
            curated_shot_map[b_idx] = w_beat

    # 2. Assign flexible durations (6.0s - 15.0s for longform documentary pacing)
    # Default documentary blocks are 8.0s - 12.0s rather than 4s Shorts fragments
    durations: list[float] = []
    is_curated_flow = bool(curated and total_blocks in (15, 22))
    native_four_second_blocks = bool(
        is_curated_flow
        or (
            total_blocks >= 15
            and timeline is not None
            and timeline.motion_model == "providers_4s"
            and timeline.total_duration >= 60.0
            and bool(curated)
        )
    )
    for i in range(total_blocks):
        role_info = classify_shot_role(i + 1, total_blocks)
        if (curated_role := curated_shot_map.get(i + 1)) is not None and curated_role.get("action"):
            visual_role = curated_role.get("visual_role") or curated_role.get("role")
            role_info = {"is_speaking_avatar": visual_role == "host_nova", "is_witness_interview": False}
        if native_four_second_blocks:
            durations.append(4.0)
        elif role_info.get("is_speaking_avatar") or role_info.get("is_witness_interview"):
            durations.append(8.0)
        elif (curated_role := curated_shot_map.get(i + 1)) is not None and curated_role.get("action"):
            durations.append(8.0)
        else:
            durations.append(6.0 if i % 2 == 0 else 8.0)

    total_time = sum(durations)
    # If an existing timeline already specifies flexible documentary durations (>= 5.5s), keep it.
    # Otherwise build the dynamic longform timeline with flexible 6s-15s documentary durations.
    if timeline and hasattr(timeline, "shot_durations") and any(d >= 5.5 for d in timeline.shot_durations) and timeline.motion_model != "providers_4s" and not is_curated_flow:
        active_timeline = timeline
    else:
        active_timeline = TimelinePlan(
            source="explorer_longform",
            motion_model="longform_hybrid" if not is_curated_flow else "providers_4s",
            motion_model_name="Longform Hybrid (flexible)" if not is_curated_flow else "Provider adapters (4s)",
            native_clip_duration=8.0 if not is_curated_flow else 4.0,
            minimum_duration=total_time,
            beat_count=total_blocks,
            block_count=total_blocks,
            shot_durations=tuple(durations),
            total_duration=total_time,
            keyframe_count=total_blocks + 1,
            output_resolution="1080p",
            target_duration=total_time,
            content_duration=max(0.0, total_time - 1.5),
        )

    # 3. Generate reinforced Shots with anti-anachronism locks
    shots: list[Shot] = []
    current_time = 0.0

    for block in range(1, total_blocks + 1):
        if hasattr(active_timeline, "shot_window") and block <= active_timeline.block_count:
            t_start, t_end = active_timeline.shot_window(block)
        else:
            shot_dur = durations[block - 1]
            t_start, t_end = current_time, current_time + shot_dur
            current_time = t_end

        curated_entry = curated_shot_map.get(block)
        role_info = classify_shot_role(block, total_blocks)
        if curated_entry and curated_entry.get("action"):
            visual_role = curated_entry.get("visual_role") or curated_entry.get("role")
            role_info = {"is_speaking_avatar": visual_role == "host_nova", "is_witness_interview": False}
        is_witness = role_info.get("is_witness_interview", False)
        is_a_roll = role_info.get("is_speaking_avatar", False) and not is_witness

        materials = sheet.architecture_and_materials
        mat_text = materials[(block - 1) % len(materials)] if materials else "ancient limestone"
        proof_target = f"authentic {mat_text} with precision tooling marks"
        scene_desc = f"{sheet.location_name} highlighting {mat_text}"
        scale = "wide" if block % 2 == 1 else "close"

        if curated_entry:
            if curated_entry.get("scene"):
                scene_desc = curated_entry["scene"]
            if curated_entry.get("proof"):
                proof_target = curated_entry["proof"]
            if curated_entry.get("scale"):
                scale = curated_entry["scale"]

        if is_a_roll:
            start_prompt = compile_character_shot_prompt(character, scene_desc, role_info, aspect_ratio, era=era)
            start_prompt = apply_clothing_lock(start_prompt, era=era)
            if era != "world_war_i":
                start_prompt = apply_ancient_equipment_rule(start_prompt)
            end_prompt = start_prompt
            motion_prompt = apply_movement_lock(str(curated_entry.get("action")) if curated_entry and curated_entry.get("action") else (
                f"{character.name} faces the camera in documentary style with calm focused expression and closed mouth, gesturing toward {mat_text} "
                "with steady cinematic camera and natural posture"
            ))
            subj_id = f"host_{character.name.lower()}"
            subj_desc = character.anchor_description(era=era)
            vis_domain = "character"
            dom_event = f"{character.name} addresses the viewer on location at {sheet.location_name}"
            authored_proof = curated_entry.get("proof") if curated_entry else None
            proof_str = f"{character.name}'s brass temporal chronometer; {authored_proof or mat_text}"
            cont_anchor = f"{character.name} in {era} wardrobe"
            scale = "medium"
        elif is_witness:
            slot = int(role_info.get("witness_slot") or 1)
            witness = w1 if slot == 1 else w2
            start_prompt = compile_witness_shot_prompt(witness, scene_desc, aspect_ratio=aspect_ratio, era=era)
            start_prompt = apply_clothing_lock(start_prompt, era=era)
            if era != "world_war_i":
                start_prompt = apply_ancient_equipment_rule(start_prompt)
            end_prompt = start_prompt
            motion_prompt = apply_movement_lock(
                f"{witness['name']} looks toward the camera with period gravitas, thoughtful neutral expression and closed mouth in documentary interview framing, "
                "holding authentic drafting instrument"
            )
            subj_id = witness["id"]
            subj_desc = witness["appearance"]
            vis_domain = "character"
            dom_event = f"Historical eyewitness {witness['name']} provides testimony"
            proof_str = f"{witness['name']} in authentic {era} setting"
            cont_anchor = witness["name"]
            scale = "medium"
        else:
            start_prompt = compile_longform_broll_prompt(
                scene_description=scene_desc,
                proof_target=proof_target,
                truth_sheet=sheet,
                aspect_ratio=aspect_ratio,
                action_description=str(curated_entry.get("action") or "") if curated_entry else "",
            )
            end_prompt = start_prompt
            motion_prompt = format_veo_cinematography_prompt(
                shot_type=f"Cinematic {scale} documentary camera move",
                subject_labor=str(curated_entry.get("action")) if curated_entry and curated_entry.get("action") else f"slow camera glide revealing {proof_target}",
                lighting=str(curated_entry.get("lighting")) if curated_entry and curated_entry.get("lighting") else "golden hour morning light with volumetric dust motes",
                historical_atmosphere=f"historically accurate {era} documentary scene",
                camera_vector="slow steady cinematic dolly in",
                fps="24fps",
                era=era,
            )
            subj_id = "host_nova" if curated_entry and curated_entry.get("character_reference") else f"broll_shot_{block:02d}"
            if curated_entry and curated_entry.get("character_reference"):
                subj_desc = character.anchor_description(era=era)
                vis_domain = "character"
                dom_event = str(curated_entry.get("action")) if curated_entry.get("action") else f"{character.name} appears at {sheet.location_name}"
            else:
                subj_desc = f"historically grounded environment of {sheet.location_name}"
                vis_domain = "archaeology"
                dom_event = str(curated_entry.get("action")) if curated_entry and curated_entry.get("action") else f"camera glides across {proof_target}"
            proof_str = proof_target
            cont_anchor = str(curated_entry.get("continuity_anchor")) if curated_entry and curated_entry.get("continuity_anchor") else f"{sheet.location_name} {era} setting"

        shots.append(Shot(
            block=block,
            beat_index=block,
            t_start=t_start,
            t_end=t_end,
            subject_id=subj_id,
            subject_description=subj_desc,
            start_image_prompt=start_prompt,
            end_image_prompt=end_prompt,
            motion_prompt=motion_prompt,
            target_quadrant="center" if (is_a_roll or is_witness) else ("top_left", "center", "top_right", "center")[block % 4],
            dominant_event=dom_event,
            proof_on_screen=proof_str,
            entry_state=f"shot_{block:02d}_entry",
            exit_state=f"shot_{block:02d}_exit",
            scale=scale,
            journey_phase=("establish", "explore", "descend", "reveal", "resolve")[min(4, (block - 1) * 5 // total_blocks)],
            transition_kind="location_change" if block > 1 else "same_subject",
            visual_domain=vis_domain,
            continuity_anchor=cont_anchor,
            detail_target=proof_target,
            quality_critical=["authentic lighting", "zero modern equipment", "full headroom" if (is_a_roll or is_witness) else "period-correct visible people performing the authored action when called for"],
            location_id=str(curated_entry.get("location_id")) if curated_entry and curated_entry.get("location_id") else f"site_{era}_{block:02d}",
            endpoint_mode="first_only",
        ))

    return Script(
        topic=topic,
        beats=beats,
        shots=shots,
        lang=lang,
        timeline=active_timeline,
        mode="explorer",
    )
