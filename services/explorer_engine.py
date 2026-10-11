"""Explorer screenplay and narrative engine for first-person global investigative videos.

Transforms topic investigations into immersive first-person explorer narratives
(Nova persona) featuring balanced A-Roll on-camera host moments and high-impact
cinematic B-Roll environments in 16:9 widescreen long-form format.
Zero network/provider calls are made in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

import config
from services.character import (
    classify_shot_role,
    compile_character_shot_prompt,
    compile_witness_shot_prompt,
    detect_era,
    get_active_character,
    get_era_witness,
)
from services.script_engine import Beat, Script, Shot
from timeline import TimelinePlan


EXPLORER_BEAT_TEMPLATES = [
    {
        "phase": "arrival",
        "beat_index": 1,
        "role": "host_nova",
        "default_text": "I just locked my temporal chronometer onto {topic}, and the moment I step into this era, the sheer scale takes your breath away.",
        "emphasis": ["temporal chronometer", "era", "sheer scale"],
    },
    {
        "phase": "context",
        "beat_index": 2,
        "role": "host_nova",
        "default_text": "Centuries later, modern textbooks will claim this complex was merely a myth, yet the colossal stone courtyards stand right in front of me.",
        "emphasis": ["textbooks", "colossal stone", "courtyards"],
    },
    {
        "phase": "investigation",
        "beat_index": 3,
        "role": "host_nova",
        "default_text": "Look closely at these interlocking granite blocks; the joints are cut with sub-millimeter precision without a single drop of mortar.",
        "emphasis": ["interlocking granite", "sub-millimeter", "mortar"],
    },
    {
        "phase": "turning_point",
        "beat_index": 4,
        "role": "witness",
        "default_text": "We carved three thousand subterranean chambers beneath this plateau to guard the sacred astronomy and royal records for eternity.",
        "emphasis": ["three thousand", "subterranean chambers", "eternity"],
    },
    {
        "phase": "climax",
        "beat_index": 5,
        "role": "host_nova",
        "default_text": "Descending down the torchlit limestone staircase, the acoustic resonance inside these hidden lower vaults vibrates through the bedrock itself.",
        "emphasis": ["torchlit", "acoustic resonance", "lower vaults"],
    },
    {
        "phase": "verdict",
        "beat_index": 6,
        "role": "host_nova",
        "default_text": "Before my chronometer pulls me back to the present, one truth is undeniable: our ancestors engineered wonders still waiting beneath the sand.",
        "emphasis": ["chronometer", "undeniable", "beneath the sand"],
    },
]


_LONGFORM_28_BEAT_BLUEPRINTS: list[dict[str, Any]] = [
    {"phase": "establish", "role": "host_nova", "text": "Calibrating my chronometer, I enter {topic}.", "emphasis": ["chronometer"]},
    {"phase": "establish", "role": "host_nova", "text": "White limestone walls gleam across the plateau.", "emphasis": ["white limestone", "plateau"]},
    {"phase": "establish", "role": "host_nova", "text": "Weathered surface ruins still divide modern historians.", "emphasis": ["weathered", "historians"]},
    {"phase": "establish", "role": "host_nova", "text": "Time travel reveals the intact ancient architecture.", "emphasis": ["intact", "architecture"]},
    {"phase": "explore", "role": "host_nova", "text": "Twelve roofed courts align along astronomical axes.", "emphasis": ["twelve roofed courts", "astronomical"]},
    {"phase": "explore", "role": "host_nova", "text": "Red granite columns support massive ceiling slabs.", "emphasis": ["red granite", "ceiling slabs"]},
    {"phase": "explore", "role": "host_question", "text": "In the courtyard, I questioned {w1_name}.", "emphasis": ["courtyard"]},
    {"phase": "explore", "role": "witness_1", "text": "We built fifteen hundred vaults with granite plug-stones.", "emphasis": ["fifteen hundred", "granite plug-stones"]},
    {"phase": "explore", "role": "host_nova", "text": "His papyrus schematic reveals acoustic corridor traps.", "emphasis": ["papyrus schematic", "acoustic"]},
    {"phase": "descend", "role": "host_nova", "text": "Copper saws left striations across polished basalt.", "emphasis": ["copper saws", "polished basalt"]},
    {"phase": "descend", "role": "host_nova", "text": "A concealed stone doorway leads deep underground.", "emphasis": ["stone doorway", "underground"]},
    {"phase": "descend", "role": "host_nova", "text": "Oil lamps light passages turning at right angles.", "emphasis": ["oil lamps", "right angles"]},
    {"phase": "descend", "role": "host_nova", "text": "Subterranean canals regulate pressure beneath the bedrock.", "emphasis": ["subterranean canals", "bedrock"]},
    {"phase": "escalate", "role": "host_nova", "text": "My chronometer dial detects a low acoustic hum.", "emphasis": ["chronometer dial", "acoustic hum"]},
    {"phase": "escalate", "role": "host_nova", "text": "When this stone door shuts, the hall thunders!", "emphasis": ["stone door", "thunders"]},
    {"phase": "escalate", "role": "host_nova", "text": "Ancient travelers in darkness believed these walls lived.", "emphasis": ["darkness", "walls lived"]},
    {"phase": "escalate", "role": "host_nova", "text": "Inner reliefs depict zodiac stars and flood cycles.", "emphasis": ["zodiac stars", "flood cycles"]},
    {"phase": "escalate", "role": "host_nova", "text": "Centuries later, classical chroniclers documented this marvel.", "emphasis": ["classical chroniclers", "marvel"]},
    {"phase": "reveal", "role": "host_question", "text": "At the colonnade, I met {w2_name}.", "emphasis": ["colonnade"]},
    {"phase": "reveal", "role": "witness_2", "text": "I saw the pyramids, yet this labyrinth surpasses all.", "emphasis": ["pyramids", "labyrinth"]},
    {"phase": "reveal", "role": "host_nova", "text": "His account proves antiquity ranked this above all.", "emphasis": ["antiquity", "above all"]},
    {"phase": "reveal", "role": "host_nova", "text": "Later empires quarried limestone and cut canals.", "emphasis": ["quarried limestone", "canals"]},
    {"phase": "reveal", "role": "host_nova", "text": "Desert sand and groundwater sealed the lower vaults.", "emphasis": ["desert sand", "lower vaults"]},
    {"phase": "resolve", "role": "host_nova", "text": "Satellite radar detects massive stone structures underground.", "emphasis": ["satellite radar", "stone structures"]},
    {"phase": "resolve", "role": "host_nova", "text": "Core samples reveal red granite beneath the bedrock.", "emphasis": ["core samples", "red granite"]},
    {"phase": "resolve", "role": "host_nova", "text": "Ground scans confirm the lower foundation grid survived.", "emphasis": ["ground scans", "foundation grid"]},
    {"phase": "resolve", "role": "host_nova", "text": "My chronometer flashes amber; my time window closes.", "emphasis": ["flashes amber", "time window"]},
    {"phase": "resolve", "role": "host_nova", "text": "Standing here, we know history waits beneath us.", "emphasis": ["history waits", "beneath us"]},
]


_BROLL_SCENE_BLUEPRINTS: list[dict[str, str]] = [
    {"scene": "panoramic aerial establishing vista of {topic} gleaming in golden morning sunlight with monumental stone courtyards", "proof": "colossal twin limestone pylons casting long morning shadows across paved courtyard", "scale": "wide", "domain": "archaeology"},
    {"scene": "wide architectural shot of massive white limestone enclosure walls and colonnaded courts at {topic}", "proof": "intact megalithic limestone perimeter wall with precision beveled masonry joints", "scale": "wide", "domain": "architecture"},
    {"scene": "split temporal comparison feel showing weathered desert surface ruins above bedrock foundations at {topic}", "proof": "eroded limestone column drums resting on intact buried foundation pavement", "scale": "wide", "domain": "archaeology"},
    {"scene": "grand open-air peristyle courtyard surrounded by forty monolithic red granite columns at {topic}", "proof": "rows of carved monolithic red granite columns supporting massive stone architraves", "scale": "wide", "domain": "architecture"},
    {"scene": "northern monumental stone gateway aligned with solar shafts piercing into the roofed hypostyle hall", "proof": "diagonal shafts of golden sunlight illuminating dust motes across stone floor slabs", "scale": "wide", "domain": "architecture"},
    {"scene": "low-angle view of cyclopean single-piece sandstone ceiling slabs resting atop lotus-capital columns", "proof": "massive monolithic ceiling slabs spanning between carved stone capitals", "scale": "medium", "domain": "architecture"},
    {"scene": "ancient architectural worktable holding unrolled papyrus floorplans, bronze calipers, and wooden cubit rods in courtyard shade", "proof": "inked geometric labyrinth grid drawn on authentic fibrous papyrus scroll beside bronze plumb-bob", "scale": "close", "domain": "archaeology"},
    {"scene": "historical witness interview setting in sunlit colonnade", "proof": "authentic historical architectural tools and stonework", "scale": "medium", "domain": "character"},
    {"scene": "extreme close-up of ancient papyrus architectural diagram and bronze plumb-bob resting on carved limestone block", "proof": "fine black and red reed-ink grid lines on papyrus texture beside bronze measuring weight", "scale": "macro", "domain": "archaeology"},
    {"scene": "macro close-up of interlocking black basalt masonry blocks showing microscopic copper-saw striations and zero mortar gap", "proof": "razor-thin seam between two polished basalt blocks with parallel tool striations", "scale": "macro", "domain": "engineering"},
    {"scene": "concealed pivoting stone doorway recessed into a shadow-draped limestone wall leading to subterranean stairs", "proof": "cylindrical granite pivot socket carved directly into the upper stone lintel", "scale": "medium", "domain": "architecture"},
    {"scene": "torchlit subterranean limestone corridor turning at sharp ninety-degree angles deep underground", "proof": "flickering bronze oil lamp mounted in carved wall niche illuminating narrow stone passage", "scale": "medium", "domain": "archaeology"},
    {"scene": "underground hydraulic stone canal channel carved into bedrock with clear dark water flowing beneath vaulted arches", "proof": "chiseled limestone sluice gate channeling subterranean water flow", "scale": "wide", "domain": "engineering"},
    {"scene": "macro shot of glowing brass temporal chronometer dial resting near vibrating ancient stone wall relief", "proof": "rotating gyroscopic brass rings reflecting warm torchlight against carved limestone", "scale": "macro", "domain": "archaeology"},
    {"scene": "midpoint host reaction inside cavernous subterranean sanctuary chamber", "proof": "massive sliding granite portcullis block in background behind host", "scale": "medium", "domain": "character"},
    {"scene": "cavernous subterranean acoustic chamber with high corbeled stone ceiling and sliding granite portcullis block", "proof": "multi-ton granite plug-stone seated inside grooved limestone guide rails", "scale": "wide", "domain": "engineering"},
    {"scene": "close-up of deeply incised hieroglyphic and astronomical zodiac bas-reliefs illuminated by raking side light", "proof": "crisp sunken relief carvings of stars and water glyphs in golden limestone", "scale": "close", "domain": "archaeology"},
    {"scene": "time-lapse style golden sunbeam sweeping across ancient carved stone sundial and courtyard obelisk", "proof": "sharp shadow line moving across engraved stone degree markers", "scale": "medium", "domain": "archaeology"},
    {"scene": "classical era outer colonnade overlooking turquoise lake waters and white stone terraces", "proof": "weathered limestone colonnade overlooking shimmering water basin", "scale": "wide", "domain": "architecture"},
    {"scene": "historical chronicler interview setting beside classical colonnade", "proof": "wax writing tablet and bronze stylus held during historical testimony", "scale": "medium", "domain": "character"},
    {"scene": "close-up of ancient wooden wax diptych tablet inscribed with Greek text via a pointed bronze stylus", "proof": "freshly incised letters on dark beeswax tablet surface beside bronze stylus tip", "scale": "macro", "domain": "archaeology"},
    {"scene": "late-antiquity stone quarry cut across the upper courtyard showing half-removed limestone blocks and wooden wedges", "proof": "chisel wedge slots lined up along a fractured limestone block face", "scale": "wide", "domain": "archaeology"},
    {"scene": "desert sandstorm sweeping golden dunes over the sunken stone roofs of the ancient complex at dusk", "proof": "windblown ripples of desert sand burying carved stone cornices", "scale": "wide", "domain": "environment"},
    {"scene": "modern archaeological survey tripod and ground-penetrating radar antenna positioned on the desert plateau at dawn", "proof": "archaeological survey grid markers and radar sled tracks across sandy limestone plain", "scale": "wide", "domain": "archaeology"},
    {"scene": "macro close-up of cylindrical geological core drill samples showing red granite and polished quartzite layers", "proof": "labeled wooden core box holding smooth cylindrical red granite rock cores", "scale": "close", "domain": "archaeology"},
    {"scene": "high-angle drone perspective showing rectilinear subsurface foundation outlines visible through morning desert dew", "proof": "geometric grid of buried stone wall foundations traced across the desert floor", "scale": "wide", "domain": "archaeology"},
    {"scene": "macro close-up of brass temporal chronometer wrist device glowing warm amber against twilight desert ruins", "proof": "illuminated amber sapphire dial and engraved celestial rings on brass chronometer", "scale": "macro", "domain": "archaeology"},
    {"scene": "closing host verdict standing before twilight ruins at golden hour", "proof": "host with brass chronometer against sunset panorama of ancient monument", "scale": "medium", "domain": "character"},
]


def create_explorer_beats(topic: str, beat_count: int = 5) -> list[Beat]:
    """Generate first-person conversational Beats (Nova + Historical Witnesses) matching beat_count."""
    clean_topic = re.sub(r"[^\w\s-]", "", topic).strip() or "this ancient site"
    era = detect_era(topic)
    w1 = get_era_witness(era, 1)
    w2 = get_era_witness(era, 2)

    from services.historical_research import get_historical_truth_sheet
    sheet = get_historical_truth_sheet(topic)
    curated = list(getattr(sheet, "curated_beats", []) or [])
    if curated and len(curated) >= beat_count:
        if len(curated) == beat_count:
            chosen = curated
        else:
            step = (len(curated) - 1) / max(1, beat_count - 1)
            indices = [min(len(curated) - 1, int(round(i * step))) for i in range(beat_count)]
            indices[0] = 0
            indices[-1] = len(curated) - 1
            chosen = [curated[idx] for idx in indices]
        beats: list[Beat] = []
        for i, c_beat in enumerate(chosen):
            beats.append(Beat(
                index=i + 1,
                text=c_beat["text"],
                role=c_beat.get("role", "host_nova"),
                emphasis=list(c_beat.get("emphasis", ["ancient", "monument"])),
            ))
        return beats

    if beat_count <= 6:
        count = max(3, min(len(EXPLORER_BEAT_TEMPLATES), beat_count))
        beats: list[Beat] = []
        for i in range(count):
            template = EXPLORER_BEAT_TEMPLATES[i]
            text = template["default_text"].format(topic=clean_topic)
            role = template.get("role", "host_nova")
            if role == "witness":
                role = f"witness:{w1['name']} ({w1['era_label']})"
            beats.append(Beat(
                index=i + 1,
                text=text,
                role=role,
                emphasis=list(template["emphasis"]),
            ))
        return beats

    # Align beats 1:1 with classify_shot_role so opening, midpoint, closing, and witness
    # interviews match their exact visual shot indices for any beat_count (e.g. 15 or 28).
    reserved_bp_indices = {0, 6, 7, 14, 18, 19, len(_LONGFORM_28_BEAT_BLUEPRINTS) - 1}
    broll_pool = [
        bp for idx_bp, bp in enumerate(_LONGFORM_28_BEAT_BLUEPRINTS)
        if idx_bp not in reserved_bp_indices
    ]
    role_map: dict[int, dict[str, Any]] = {}
    for shot_idx in range(1, beat_count + 1):
        role_map[shot_idx] = classify_shot_role(shot_idx, beat_count)

    chosen_bps: list[dict[str, Any]] = [{} for _ in range(beat_count)]
    for shot_idx in range(1, beat_count + 1):
        r_info = role_map[shot_idx]
        if shot_idx == 1:
            chosen_bps[shot_idx - 1] = _LONGFORM_28_BEAT_BLUEPRINTS[0]
        elif shot_idx == beat_count:
            chosen_bps[shot_idx - 1] = _LONGFORM_28_BEAT_BLUEPRINTS[-1]
        elif r_info.get("is_speaking_avatar"):
            chosen_bps[shot_idx - 1] = _LONGFORM_28_BEAT_BLUEPRINTS[14]
        elif r_info.get("is_witness_interview"):
            slot = int(r_info.get("witness_slot") or 1)
            if slot == 1:
                chosen_bps[shot_idx - 1] = _LONGFORM_28_BEAT_BLUEPRINTS[7]
                if shot_idx >= 2 and not chosen_bps[shot_idx - 2]:
                    chosen_bps[shot_idx - 2] = _LONGFORM_28_BEAT_BLUEPRINTS[6]
            else:
                chosen_bps[shot_idx - 1] = _LONGFORM_28_BEAT_BLUEPRINTS[19]
                if shot_idx >= 2 and not chosen_bps[shot_idx - 2]:
                    chosen_bps[shot_idx - 2] = _LONGFORM_28_BEAT_BLUEPRINTS[18]

    unfilled = [i for i, bp in enumerate(chosen_bps) if not bp]
    for pos_idx, slot_i in enumerate(unfilled):
        pool_idx = min(len(broll_pool) - 1, int(pos_idx * len(broll_pool) / max(1, len(unfilled))))
        chosen_bps[slot_i] = broll_pool[pool_idx]

    beats = []
    for i, bp in enumerate(chosen_bps):
        text = bp["text"].format(
            topic=clean_topic,
            w1_name=w1["name"],
            w2_name=w2["name"],
        )
        raw_role = bp["role"]
        if raw_role == "witness_1":
            role = f"witness:{w1['name']} ({w1['era_label']})"
        elif raw_role == "witness_2":
            role = f"witness:{w2['name']} ({w2['era_label']})"
        else:
            role = raw_role
        beats.append(Beat(
            index=i + 1,
            text=text,
            role=role,
            emphasis=list(bp["emphasis"]),
        ))
    return beats


def build_explorer_shots(
    topic: str,
    timeline: TimelinePlan,
    beats: list[Beat],
    aspect_ratio: str = "16:9",
) -> list[Shot]:
    """Construct Shot storyboard with Nova Solo A-Roll, Historical Witness Interviews, and People-Free B-Roll."""
    character = get_active_character()
    era = detect_era(topic)
    w1 = get_era_witness(era, 1)
    w2 = get_era_witness(era, 2)
    total_shots = timeline.block_count
    shots: list[Shot] = []

    for block in range(1, total_shots + 1):
        t_start, t_end = timeline.shot_window(block)
        beat_idx = min(len(beats), max(1, int((block - 1) * len(beats) / max(1, total_shots)) + 1))
        beat_obj = beats[beat_idx - 1] if beats else None
        bp_idx = min(
            len(_BROLL_SCENE_BLUEPRINTS) - 1,
            int((block - 1) * (len(_BROLL_SCENE_BLUEPRINTS) - 1) / max(1, total_shots - 1)),
        )
        bp_entry = _BROLL_SCENE_BLUEPRINTS[bp_idx]
        journey_phase = ("establish", "explore", "descend", "escalate", "reveal", "resolve")[
            min(5, (block - 1) * 6 // max(1, total_shots))
        ]

        role_info = classify_shot_role(block, total_shots, journey_phase)
        is_witness = role_info.get("is_witness_interview", False)
        is_a_roll = role_info.get("is_speaking_avatar", False) and not is_witness

        from services.historical_research import get_historical_truth_sheet
        sheet = get_historical_truth_sheet(topic)
        curated = list(getattr(sheet, "curated_beats", []) or [])

        scene_desc = bp_entry["scene"].format(topic=topic)
        authored_proof = bp_entry["proof"]

        if curated and beat_idx <= len(curated):
            c_entry = curated[beat_idx - 1]
            if c_entry.get("scene"):
                scene_desc = c_entry["scene"]
            if c_entry.get("proof"):
                authored_proof = c_entry["proof"]

        if is_a_roll:
            start_prompt = compile_character_shot_prompt(character, scene_desc, role_info, aspect_ratio, era=era)
            end_prompt = compile_character_shot_prompt(character, scene_desc, role_info, aspect_ratio, era=era)
            motion_prompt = (
                f"{character.name} speaks with natural subtle head motion and authentic facial expressions, "
                "complete head and shoulders framed comfortably with generous headroom, "
                "addressing the camera in documentary style, steady camera with subtle natural handheld float"
            )
            subj_id = f"host_{character.name.lower()}"
            subj_desc = character.anchor_description(era=era)
            vis_domain = "character"
            dominant_ev = f"{character.name} addresses the viewer on location at {topic}"
            proof_str = f"{character.name}'s brass temporal chronometer wrist device and {era} architecture in background"
            cont_anchor = f"{character.name} in {era} wardrobe camouflage"
        elif is_witness:
            slot = int(role_info.get("witness_slot") or (1 if block < total_shots // 2 else 2))
            witness = w1 if slot == 1 else w2
            start_prompt = compile_witness_shot_prompt(witness, scene_desc, aspect_ratio=aspect_ratio, era=era)
            end_prompt = compile_witness_shot_prompt(witness, scene_desc, aspect_ratio=aspect_ratio, era=era)
            motion_prompt = (
                f"{witness['name']} speaks with expressive historical gravitas and natural mouth articulation, "
                "holding authentic period architectural instruments in a steady 16:9 documentary interview frame"
            )
            subj_id = witness["id"]
            subj_desc = witness["appearance"]
            vis_domain = "character"
            dominant_ev = f"Historical eyewitness {witness['name']} gives first-hand testimony"
            proof_str = f"{witness['name']} holding period architectural tool in {era} setting"
            cont_anchor = witness["name"]
        else:
            start_prompt = (
                f"Photorealistic 8k National Geographic and BBC Earth 35mm documentary B-roll frame of {scene_desc}. "
                f"Visible physical evidence: {authored_proof}. "
                f"Atmospheric volumetric lighting, {aspect_ratio} widescreen, authentic weathered stone and natural materials, "
                "deep shadow contrast. If the authored historical scene includes people, show period-correct workers performing the specific action, never posing. "
                "Natural continuous body movement, shifting weight, moving fabric, coordinated purposeful labor. No modern archaeologists, no text."
            )
            end_prompt = (
                f"Cinematic perspective across {scene_desc} highlighting {authored_proof}, "
                f"dynamic camera push-in revealing intricate architectural or archaeological textures, "
                f"{aspect_ratio} widescreen. Show only people and actions explicitly supported by the authored historical scene; "
                "period-correct clothing and purposeful movement, no modern archaeologists, no text."
            )
            from services.prompt_compiler import format_veo_cinematography_prompt
            motion_prompt = format_veo_cinematography_prompt(
                shot_type=f"Cinematic {bp_entry.get('scale', 'medium')} shot",
                subject_labor=f"slow camera glide revealing {authored_proof}",
                lighting="golden hour morning light with volumetric dust motes",
                historical_atmosphere=f"authentic {era} sanctuary",
                camera_vector="slow steady cinematic dolly in",
                fps="24fps",
            )
            subj_id = f"broll_{block:02d}_{journey_phase}"
            subj_desc = f"historical environment showing {scene_desc}; include period-correct people only when the authored scene assigns them an action"
            vis_domain = bp_entry.get("domain", "archaeology")
            dominant_ev = f"camera reveals {authored_proof}"
            proof_str = authored_proof
            cont_anchor = f"{topic} {journey_phase} stonework"

        shots.append(Shot(
            block=block,
            beat_index=beat_idx,
            t_start=t_start,
            t_end=t_end,
            subject_id=subj_id,
            subject_description=subj_desc,
            start_image_prompt=start_prompt,
            end_image_prompt=end_prompt,
            motion_prompt=motion_prompt,
            target_quadrant="center" if (is_a_roll or is_witness) else ("top_left", "center", "top_right", "center")[block % 4],
            dominant_event=dominant_ev,
            proof_on_screen=proof_str,
            entry_state=f"{journey_phase}_shot_{block:02d}_entry",
            exit_state=f"{journey_phase}_shot_{block:02d}_exit",
            scale="medium" if (is_a_roll or is_witness) else bp_entry.get("scale", "wide"),
            journey_phase=journey_phase,
            transition_kind="location_change" if block > 1 else "same_subject",
            visual_domain=vis_domain,
            continuity_anchor=cont_anchor,
            detail_target=authored_proof,
            quality_critical=["authentic lighting", "zero text", "full headroom" if (is_a_roll or is_witness) else "period-correct people only when assigned an authored action"],
            location_id=f"site_{era}_{journey_phase}",
            endpoint_mode="first_only",
        ))

    return shots


def build_explorer_script(topic: str, timeline: TimelinePlan, lang: str = "en") -> Script:
    """Build full Script object for an Explorer production."""
    aspect_ratio = "16:9" if (getattr(config, "LONGFORM_MODE", False) or getattr(config, "WIDTH", 1080) >= 1280) else "9:16"
    target_beats = timeline.block_count if timeline.block_count >= 8 else min(6, timeline.block_count)
    beats = create_explorer_beats(topic, beat_count=target_beats)
    shots = build_explorer_shots(topic, timeline, beats, aspect_ratio=aspect_ratio)
    return Script(
        topic=topic,
        beats=beats,
        shots=shots,
        lang=lang,
        timeline=timeline,
        mode="explorer",
    )

