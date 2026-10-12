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
from services.historical_research import HistoricalTruthSheet, get_historical_truth_sheet
from services.prompt_compiler import (
    apply_ancient_equipment_rule,
    apply_clothing_lock,
    apply_movement_lock,
    compile_longform_broll_prompt,
    format_multi_shot_prompt,
)
from services.script_engine import Beat, Script, Shot
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
    if era == "world_war_i" and any(term in topic.casefold() for term in ("gallipoli", "canakkale", "çanakkale", "dardanelles")):
        curated = [
            {
                "text": "At dawn on 18 March 1915, I watch Allied battleships enter the Dardanelles, expecting gunfire to open the route toward Constantinople.",
                "role": "host_nova", "emphasis": ["18 March 1915", "Dardanelles"], "scale": "wide",
                "scene": "Nova arrives at the Gallipoli shore at dawn, 18 March 1915; period wool field coat and brass chronometer on her left wrist, Allied battleships entering the distant strait.",
                "proof": "Allied battleships entering the Dardanelles on 18 March 1915",
                "action": "Nova steps against the coastal wind and unfolds a field map as the fleet advances; her coat and hair move naturally, camera glides from her shoulder toward the strait with strong layered parallax.",
                "lighting": "golden dawn beneath heavy coastal cloud",
                "location_id": "gallipoli_1915_shore_dawn",
            },
            {
                "text": "The Ottoman minelayer Nusret laid twenty-six mines in Erenköy Bay on 8 March, hidden beneath a dark, choppy surface.",
                "role": "narrator", "emphasis": ["Nusret", "twenty-six mines"], "scale": "medium",
                "scene": "The Ottoman minelayer Nusret laying a line of twenty-six contact mines in Erenköy Bay on the night of 8 March 1915; authentic early twentieth-century vessel and naval crew.",
                "proof": "Nusret and its mine-laying operation in Erenköy Bay",
                "action": "Nusret moves through black water as sailors haul one contact mine over the rail and lower it with period rigging; rope strains, wake ripples, deck lamps flicker, and the camera tracks beside the hull.",
                "lighting": "cold moonlight with warm deck lanterns",
                "location_id": "erenkoy_bay_1915_night",
            },
            {
                "text": "Ottoman coastal batteries answered with smoke and thunder as crews loaded shells, reset their guns, and fired across the strait.",
                "role": "narrator", "emphasis": ["coastal batteries", "fired"], "scale": "close",
                "scene": "Ottoman coastal artillery battery at the Dardanelles on 18 March 1915; period heavy gun, wool-uniformed artillery crew, sandbags and powder smoke.",
                "proof": "An Ottoman artillery crew loading and firing a period coastal gun",
                "action": "Crewmen haul a shell, load the breech, traverse the gun and fire once; recoil jolts the barrel as powder smoke rolls past, camera tracks laterally across sandbags to reveal depth.",
                "lighting": "chiaroscuro daylight filtered through powder smoke",
                "location_id": "dardanelles_battery_1915",
            },
            {
                "text": "The French battleship Bouvet struck a mine and capsized; Irresistible and Ocean were also lost during the retreat.",
                "role": "narrator", "emphasis": ["Bouvet", "mine"], "scale": "wide",
                "scene": "The French battleship Bouvet in the Dardanelles on 18 March 1915, historically grounded pre-dreadnought silhouette on rough gray water, non-graphic depiction.",
                "proof": "Bouvet listing and capsizing after striking a mine",
                "action": "Bouvet takes a mine blast along the hull, lists sharply and capsizes as waves surge over the deck; distant ships alter course, camera tracks low across moving water with visible parallax.",
                "lighting": "cold storm light with brief orange blast illumination",
                "location_id": "dardanelles_bouvet_1915",
            },
            {
                "text": "The Allied fleet withdrew. The failed sea passage did not end the campaign; troops landed on Gallipoli on 25 April 1915.",
                "role": "narrator", "emphasis": ["withdrew", "25 April 1915"], "scale": "medium",
                "scene": "A damaged Allied warship withdrawing from the Dardanelles after the failed naval assault; smoke trails past the rocky peninsula, authentic 1915 silhouettes.",
                "proof": "The fleet turning away from the Dardanelles after the failed passage",
                "action": "The damaged ship turns away under its own power as smaller period vessels maneuver through choppy water to assist; smoke drifts downwind while the camera lifts gently from the wake toward the retreating fleet.",
                "lighting": "muted late-afternoon light with smoke haze",
                "location_id": "dardanelles_retreat_1915",
            },
            {
                "text": "The struggle shifted from sea to shore and endured months, leaving a legacy remembered in Turkey, Australia, New Zealand, and Britain.",
                "role": "narrator", "emphasis": ["sea to shore", "legacy"], "scale": "wide",
                "scene": "Nova walks the Gallipoli shoreline at evening, same face, chestnut hair, left-wrist brass chronometer and 1915 wool-and-linen camouflage; the Dardanelles opens behind her.",
                "proof": "The Gallipoli peninsula and the sea-to-land campaign shift",
                "action": "Nova folds her map and walks along the wind-beaten shore; waves cross the rocks and clouds move over the strait as the camera tracks backward to reveal the peninsula in layered depth.",
                "lighting": "soft overcast evening light, reflective and restrained",
                "location_id": "gallipoli_1915_shore_evening",
                "character_reference": True,
            },
        ]
        # A one-minute native Flow test uses fifteen four-second clips.  Keep a
        # topic-specific shot for every clip; sampling the six-beat short outline
        # used to fall through to unrelated generic archaeology copy at this size.
        if total_blocks >= 15:
            curated = [{'text': 'I have stepped onto Gallipoli as warships enter the strait.',
  'role': 'host_nova',
  'emphasis': ['stepped onto Gallipoli', 'warships'],
  'scale': 'wide',
  'scene': 'Nova arrives on the Gallipoli shore on 18 March 1915, Allied battleships advancing into the narrow Dardanelles; period wool coat and '
           'brass chronometer on her left wrist.',
  'proof': 'Allied battleships entering the Dardanelles on 18 March 1915',
  'action': 'Nova steps out of salt spray and turns toward the distant ships; her coat and hair move in the coastal wind, camera follows her gaze to '
            'the strait.',
  'lighting': 'gray dawn beneath smoke-heavy coastal cloud',
  'location_id': 'gallipoli_battery_story_hook',
  'character_reference': True},
 {'text': 'Their shells crash around the battery; smoke hides the water.',
  'role': 'narrator',
  'emphasis': ['shells crash', 'smoke'],
  'scale': 'wide',
  'scene': 'Allied battleship guns bombard an Ottoman shore battery on 18 March 1915; shell splashes rise beyond the stone position and dark powder '
           'smoke crosses the channel.',
  'proof': 'Naval bombardment of an Ottoman coastal battery during the 18 March attack',
  'action': 'A distant shell strikes the hillside beyond the battery, throwing up dust as smoke drifts across the gun position; camera tracks from '
            'shaking sandbags toward the obscured water.',
  'lighting': 'smoke-diffused cold daylight',
  'location_id': 'dardanelles_battery_under_fire'},
 {'text': 'I meet an Ottoman gunner beside his artillery crew.',
  'role': 'host_nova',
  'visual_role': 'field_interview',
  'emphasis': ['Ottoman gunner', 'crew'],
  'scale': 'medium',
  'scene': 'Nova, matching her established face and Ottoman-era wool-and-linen camouflage with brass chronometer, meets a tired Ottoman coastal '
           'gunner beside his 1915 artillery crew and heavy gun.',
  'proof': 'A time-traveler host meeting an Ottoman coastal gun crew at its battery',
  'action': 'Nova leans in to ask the gunner a question with a small hand gesture; he answers without speaking by pointing toward the next shell. '
            'Both keep neutral closed mouths; no audible dialogue or lip movement.',
  'lighting': 'warm firelight through powder smoke',
  'location_id': 'dardanelles_gunner_interview',
  'character_reference': True},
 {'text': 'He nods toward the next round. The crew begins hauling.',
  'role': 'narrator',
  'emphasis': ['next round', 'hauling'],
  'scale': 'medium',
  'scene': 'At the same Dardanelles battery, an Ottoman gun crew prepares another artillery round while Nova watches from the side; period-correct '
           'wool uniforms and sandbagged gun position.',
  'proof': 'The crew moving the next artillery round toward the gun',
  'action': 'The gunner signals toward a shell and two crewmen step in, grip it together, and begin hauling it over the rough battery floor; Nova '
            'watches beside them.',
  'lighting': 'smoke-softened daylight with warm ember highlights',
  'location_id': 'dardanelles_gunner_interview',
  'character_reference': True},
 {'text': 'They grip the shell and lift it together.',
  'role': 'narrator',
  'emphasis': ['grip the shell', 'together'],
  'scale': 'close',
  'scene': 'Close documentary view of Ottoman artillerymen lifting a heavy period shell between them inside a Dardanelles shore battery, wool '
           'sleeves, leather gloves and gun carriage visible.',
  'proof': 'Several artillerymen coordinating to lift one heavy shell',
  'action': 'Three crewmen brace their boots and raise the shell in a coordinated lift; camera moves beside their hands and the round without losing '
            'the men performing the work.',
  'lighting': 'directional daylight through powder haze',
  'location_id': 'dardanelles_shell_lift'},
 {'text': 'One steadies it as another aligns the breech.',
  'role': 'narrator',
  'emphasis': ['steadies', 'breech'],
  'scale': 'close',
  'scene': 'Ottoman artillery crew hand-guiding a shell toward the breech of a heavy 1915 coastal gun, exact mechanical scale and period gun '
           'carriage.',
  'proof': 'The shell aligned with the open breech of the coastal gun',
  'action': 'One gunner steadies the shell while a second aligns it with the open breech; hands guide the round forward in one careful motion, '
            'camera pushes in at shoulder height.',
  'lighting': 'cool reflected daylight and deep gunmetal shadows',
  'location_id': 'dardanelles_breech_load'},
 {'text': 'They ram it home, then swing the gun seaward.',
  'role': 'narrator',
  'emphasis': ['ram it home', 'seaward'],
  'scale': 'medium',
  'scene': 'A period Ottoman coastal artillery piece traversing toward the Allied fleet, crew at the breech and hand wheels, smoke and stone '
           'revetment behind.',
  'proof': 'The loaded Ottoman coastal gun being aimed toward the strait',
  'action': 'The crew secures the breech, then turns the gun toward the channel using the traversing wheels; camera tracks the barrel across the '
            'battery toward the fleet.',
  'lighting': 'gray daylight broken by powder smoke',
  'location_id': 'dardanelles_gun_traverse'},
 {'text': 'The cannon fires; the blast shakes the stone position.',
  'role': 'narrator',
  'emphasis': ['cannon fires', 'blast'],
  'scale': 'wide',
  'scene': 'Ottoman shore gun firing once toward the Allied fleet from its stone battery on 18 March 1915; visible crew, recoil, and powder smoke.',
  'proof': 'A coastal gun firing from an Ottoman battery during the naval assault',
  'action': 'The cannon fires once, recoiling along its carriage as the crew braces and dense powder smoke rolls over the stone position; camera '
            'jolts subtly with the blast.',
  'lighting': 'brief hot muzzle flash in cold smoke',
  'location_id': 'dardanelles_gun_firing'},
 {'text': 'I ask how long they can keep firing.',
  'role': 'host_nova',
  'visual_role': 'field_interview',
  'emphasis': ['keep firing'],
  'scale': 'medium',
  'scene': 'Nova and the same Ottoman gunner beside the same coastal gun, brief side-on field interview framed through drifting powder smoke; both '
           'in consistent period setting.',
  'proof': 'The field interview returns to the same gunner and active battery',
  'action': 'Nova gestures toward the gun and asks a question without speaking on camera; the gunner answers only with a determined nod and turns '
            'toward his crew, mouths neutral and closed.',
  'lighting': 'soft amber light through a thinning veil of smoke',
  'location_id': 'dardanelles_gunner_interview',
  'character_reference': True},
 {'text': 'No pause: the next shell is already moving forward.',
  'role': 'narrator',
  'emphasis': ['no pause', 'next shell'],
  'scale': 'medium',
  'scene': "The same Ottoman gun crew immediately preparing a second shell while the first shot's smoke still hangs over the battery.",
  'proof': 'The crew beginning the next loading cycle before the smoke clears',
  'action': 'Crewmen carry another round from the ammunition stack toward the open breech as the gunner checks the position; keep the movement '
            'continuous and purposeful.',
  'lighting': 'dusty daylight with residual powder haze',
  'location_id': 'dardanelles_next_round'},
 {'text': 'Beyond the battery, minesweepers probe the channel.',
  'role': 'narrator',
  'emphasis': ['minesweepers', 'channel'],
  'scale': 'wide',
  'scene': 'Small period minesweeping trawlers work ahead of the Allied battleships in the Dardanelles on 18 March 1915, under fire from shore '
           'batteries.',
  'proof': 'Minesweeping vessels working ahead of the Allied fleet',
  'action': 'A trawler pulls sweep gear through choppy water while nearby shells splash and crewmen haul taut lines; camera tracks low along the '
            'moving wake.',
  'lighting': 'flat gray daylight and drifting gun smoke',
  'location_id': 'dardanelles_minesweepers_under_fire'},
 {'text': 'Ottoman shore guns fire as the fleet pushes on.',
  'role': 'narrator',
  'emphasis': ['shore guns', 'fleet pushes on'],
  'scale': 'wide',
  'scene': 'Allied battleships continue through the Dardanelles while Ottoman coastal guns fire from the rocky shore, 18 March 1915.',
  'proof': 'The Allied fleet advancing under fire from shore batteries',
  'action': 'Battleships move forward as a shore gun flashes and water bursts near a trawler; smoke streams with the wind while the camera pans from '
            'battery to fleet.',
  'lighting': 'cold, smoke-filtered afternoon daylight',
  'location_id': 'dardanelles_fleet_under_fire'},
 {'text': 'Then the French battleship Bouvet strikes a mine.',
  'role': 'narrator',
  'emphasis': ['Bouvet', 'strikes a mine'],
  'scale': 'wide',
  'scene': 'The French battleship Bouvet in the Dardanelles on 18 March 1915, period pre-dreadnought silhouette on rough gray water.',
  'proof': 'Bouvet struck by a mine during the 18 March naval assault',
  'action': "A mine detonates beside Bouvet's hull; the ship shudders and begins to list as water surges across its deck, camera sweeps over the "
            'disturbed surface.',
  'lighting': 'cold daylight through blast smoke',
  'location_id': 'dardanelles_bouvet_strike'},
 {'text': 'It sinks; two other ships are abandoned, another damaged.',
  'role': 'narrator',
  'emphasis': ['two other ships', 'another damaged'],
  'scale': 'wide',
  'scene': 'A distant historical tableau of Allied fleet losses on 18 March 1915: one sinking ship, rescue boats beside an abandoned battleship, and '
           'another damaged vessel withdrawing.',
  'proof': 'Bouvet, Irresistible, and Ocean lost; Inflexible damaged in the 18 March attack',
  'action': 'Rescue boats pull sailors from the water beside a disabled ship as another damaged battleship turns away through smoke; keep ships '
            'distinct and the action non-graphic.',
  'lighting': 'late afternoon haze over rough water',
  'location_id': 'dardanelles_fleet_losses'},
 {'text': 'By evening the fleet retreats. The sea attack has failed.',
  'role': 'host_nova',
  'emphasis': ['fleet retreats', 'attack has failed'],
  'scale': 'wide',
  'scene': 'Nova stands on the Gallipoli shore at dusk watching the surviving Allied fleet withdraw from the Dardanelles; same face, wool-and-linen '
           'period camouflage and left-wrist brass chronometer.',
  'proof': 'The Allied fleet withdrawing from the Dardanelles at evening',
  'action': 'Nova lowers a field map and watches the ships turn toward open water; wind pulls at her coat as the camera moves from her shoulder to '
            'the receding formation.',
  'lighting': 'restrained dusk light with smoke fading into the horizon',
  'location_id': 'gallipoli_fleet_retreat',
  'character_reference': True}]

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
        # Dynamic sensory generation (Script-Weaver pattern without repetitive robotic boilerplate)
        base_phases = sheet.narrative_beats or []
        num_phases = len(base_phases)
        GENERIC_SENSORY_PATTERNS = [
            "Stepping past the outer threshold, {mat_text} creates an imposing barrier against the horizon.",
            "Examining the stone face up close, {sen_text} reveals the sheer labor behind each block.",
            "The physical craftsmanship is striking: {mat_text} fitted together with astonishing precision.",
            "Sunlight cuts across the weathered surface, where {sen_text} emphasizes deep ancient grooves.",
            "Running a hand along the bedrock seam, {mat_text} demonstrates advanced prehistoric planning.",
            "Deep inside the perimeter, {sen_text} reverberates through the enduring stone architecture.",
        ]

        for i in range(total_blocks):
            beat_idx = i + 1
            phase_obj = base_phases[min(num_phases - 1, int(i * num_phases / max(1, total_blocks)))]
            role_info = classify_shot_role(beat_idx, total_blocks)

            if role_info.get("is_witness_interview"):
                slot = int(role_info.get("witness_slot") or 1)
                witness = w1 if slot == 1 else w2
                role = f"witness:{witness['name']} ({witness['era_label']})"
                text = (
                    f"{sheet.verified_facts[slot - 1] if len(sheet.verified_facts) >= slot else 'We carved these stones to honor our ancestors.'} "
                    "Every angle was shaped with deep purpose."
                )
                emphasis = ["carved", "honor", "ancestors"]
            elif role_info.get("is_speaking_avatar"):
                role = "host_nova"
                if beat_idx == 1:
                    text = f"I arrived at {sheet.location_name or topic}, where ancient stonework defies modern explanations."
                    emphasis = ["arrived", "ancient stonework"]
                elif beat_idx == total_blocks:
                    text = f"Before my temporal chronometer returns me to the present, one truth is clear: the brilliance of {sheet.location_name} lives on."
                    emphasis = ["chronometer", "brilliance", "lives on"]
                else:
                    text = f"Standing inside this inner chamber, the acoustic resonance through the {sheet.architecture_and_materials[0] if sheet.architecture_and_materials else 'megalith'} is unmistakable."
                    emphasis = ["acoustic resonance", "chamber"]
            else:
                role = "host_nova"
                materials = sheet.architecture_and_materials
                mat_text = materials[i % len(materials)] if materials else "monolithic stone blocks"
                sensory = sheet.sensory_details
                sen_text = sensory[i % len(sensory)] if sensory else "atmospheric light"
                pattern = GENERIC_SENSORY_PATTERNS[i % len(GENERIC_SENSORY_PATTERNS)]
                text = pattern.format(mat_text=mat_text, sen_text=sen_text)
                emphasis = [mat_text.split()[-1] if mat_text else "stone", "craftsmanship"]

            beats.append(Beat(
                index=beat_idx,
                text=text,
                role=role,
                emphasis=emphasis,
            ))

    # 2. Assign flexible durations (6.0s - 15.0s for longform documentary pacing)
    # Default documentary blocks are 8.0s - 12.0s rather than 4s Shorts fragments
    durations: list[float] = []
    native_one_minute_flow = bool(
        total_blocks >= 15
        and timeline is not None
        and timeline.motion_model == "providers_4s"
        and timeline.total_duration >= 60.0
    )
    for i in range(total_blocks):
        role_info = classify_shot_role(i + 1, total_blocks)
        if (curated_role := curated_shot_map.get(i + 1)) is not None and curated_role.get("action"):
            visual_role = curated_role.get("visual_role") or curated_role.get("role")
            role_info = {"is_speaking_avatar": visual_role == "host_nova", "is_witness_interview": False}
        if native_one_minute_flow:
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
    if timeline and hasattr(timeline, "shot_durations") and any(d >= 5.5 for d in timeline.shot_durations) and timeline.motion_model != "providers_4s":
        active_timeline = timeline
    else:
        active_timeline = TimelinePlan(
            source="explorer_longform",
            motion_model="longform_hybrid",
            motion_model_name="Longform Hybrid (flexible)",
            native_clip_duration=8.0,
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
            from services.prompt_compiler import format_veo_cinematography_prompt
            motion_prompt = format_veo_cinematography_prompt(
                shot_type=f"Cinematic {scale} documentary camera move",
                subject_labor=str(curated_entry.get("action")) if curated_entry and curated_entry.get("action") else f"slow camera glide revealing {proof_target}",
                lighting=str(curated_entry.get("lighting")) if curated_entry and curated_entry.get("lighting") else "golden hour morning light with volumetric dust motes",
                historical_atmosphere=f"historically accurate {era} documentary scene",
                camera_vector="slow steady cinematic dolly in",
                fps="24fps",
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
