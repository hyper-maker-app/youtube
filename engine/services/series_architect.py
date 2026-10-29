"""Series Architect service for Grok Imagine Cinematic Studio (Grok 4.6 UDSE v4.2).

Orchestrates 3-act organic narrative structures, word budgeting calibrated for Deepgram
Aura-2 TTS (~2.4 words/second), and piecewise-linear quantized telemetry envelopes.
Compiles scenes with Entity-Attribute Binding (EAB), metric spatial separation, and
contrastive material clauses.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from services.director_agent import Entity, WorldState
from services.prompt_compiler import (
    build_contrastive_barrier_clause,
    build_scoped_negatives_for_barrier,
    compile_udse_prompt,
)
from services.text_sanitizer import sanitize_spoken_text

logger = logging.getLogger(__name__)


def snap_to_veo_duration(duration: float) -> float:
    """Snap a duration to the nearest supported Google Veo tier: [4.0, 6.0, 8.0, 10.0]."""
    tiers = [4.0, 6.0, 8.0, 10.0]
    return min(tiers, key=lambda t: abs(t - duration))


def build_canonical_rigor_mortis_world_state() -> WorldState:
    """Construct the canonical WorldState for Project Rigor Mortis."""
    door_entity = Entity(
        id="E_DOOR_01",
        kind="barrier_door",
        material_class="solid_white_oak",
        opacity=1.0,
        transmission=0.0,
        scale="full",
        freeze_attributes=["material_class", "opacity", "hinge_side"],
        active_wear={"tape_layers": 3, "deadbolt_integrity_pct": 100, "splinter_map": "none"},
    )
    window_entity = Entity(
        id="E_WIN_PORCH",
        kind="aperture_window",
        material_class="porch_window_glass",
        opacity=0.8,
        transmission=0.85,
        scale="small",
        active_wear={"crack_status": "single_hairline_upper_pane"},
    )
    bottles_entity = Entity(
        id="E_FLOOR_BOTTLES",
        kind="tripwire_prop",
        material_class="green_bottle_glass",
        opacity=0.9,
        scale="small",
    )
    peephole_entity = Entity(
        id="E_PEEP_01",
        kind="viewing_optic",
        material_class="brass_rim_optic_glass",
        scale="macro_16mm",
    )

    return WorldState(
        project_id="project-rigor-mortis",
        entities={
            "E_DOOR_01": door_entity,
            "E_WIN_PORCH": window_entity,
            "E_FLOOR_BOTTLES": bottles_entity,
            "E_PEEP_01": peephole_entity,
        },
        invariants={
            "lighting": "camera_mounted_6000k_tactical_led",
            "ambient_fill": "pitch_black_shadows",
            "primary_barrier": "solid_reinforced_white_oak",
        },
        active_camera_axis=0.0,
    )


def generate_rigor_mortis_episode_01_scenes() -> list[dict[str, Any]]:
    """Synthesize the canonical 9-block, 74-second screenplay for Project Rigor Mortis Episode 01.
    
    Calibrated strictly for Deepgram Aura-2 (~2.4 words/second) and Google Veo block durations.
    Enforces EAB, metric spatial separation (no coplanar bleed), and scoped negatives.
    """
    contrastive_oak = build_contrastive_barrier_clause("E_DOOR_01")
    barrier_negatives = build_scoped_negatives_for_barrier()

    raw_scenes = [
        # Act 1: Status Quo & In-Media-Res Crisis Hook (0 - 22s)
        {
            "id": "scene_01",
            "act": 1,
            "shot_number": 1,
            "duration": 8.0,
            "camera_scale": "wide",
            "framing": "35mm locked eye-level master",
            "delta_state": {"interior_tape_layers": 3, "battery_pct": 42, "decibel_db": 64.2},
            "narration": "You press your eye to the brass peephole as the corridor siren wails. Outside, footsteps drag across wet concrete.",
            "visual_prompt": (
                "INT. FOYER — NIGHT. 35mm master shot of L-shaped entryway. "
                "E_DOOR_01 occupies center frame: a solid 44mm quarter-sawn white-oak slab with vertical grain, iron hinges on right jamb, sealed with three taut layers of silver duct tape across interior frame. "
                "CAMERA LEFT, on a different wall 2.1 meters from the door jamb: E_WIN_PORCH, a small porch window with one hairline crack in the upper glass pane and rain streaming outside. The crack exists only on that window. "
                f"Floor shows scuffed timber floorboards. Cold 6000K tactical flashlight illuminates the scene from camera. {contrastive_oak}"
            ),
            "motion_prompt": "Slow deliberate camera creep forward. Cold flashlight beam wavers slightly across the oak wood grain. A distant muffled metallic thud vibrates the hallway air without dislodging the door.",
            "negative_prompt": barrier_negatives,
        },
        {
            "id": "scene_02",
            "act": 1,
            "shot_number": 2,
            "duration": 6.0,
            "camera_scale": "close",
            "framing": "100mm extreme close-up peephole insert",
            "delta_state": {"interior_tape_layers": 3, "battery_pct": 42, "decibel_db": 64.2},
            "narration": "Through the scratched circular optic glass, three silhouettes stagger through driving rain. Sixty-four point two decibels.",
            "visual_prompt": (
                "ECU 100mm macro insert of E_PEEP_01: a 16mm circular convex glass optic set in an aged brass rim, embedded in the heavy dark oak door slab. "
                "Through the 16mm optic disc: blurred rain-swept darkness and dim flashes of distant strobe flares. Around the brass rim: sharp dark oak wood pores and grain. "
                "The door slab is solid opaque wood; only the tiny 16mm aperture is glass."
            ),
            "motion_prompt": "Micro camera breathing motion. Rain streaks blur through the miniature optic aperture. Silhouette forms drift past outside. Sharp focus remains locked on the brass rim and oak grain.",
            "negative_prompt": "full glass door, modern peephole, wide shot, studio lighting",
        },
        {
            "id": "scene_03",
            "act": 1,
            "shot_number": 3,
            "duration": 8.0,
            "camera_scale": "close",
            "framing": "35mm low-angle floor insert",
            "delta_state": {"interior_tape_layers": 3, "battery_pct": 41, "decibel_db": 65.0},
            "narration": "Two glass bottles rest against the baseboard, tripwire taut. If the outer latch yields, the glass shatters.",
            "visual_prompt": (
                "Low-angle 35mm floor shot looking down at the scuffed floorboards by the entryway baseboard. "
                "E_FLOOR_BOTTLES: two dark green glass bottles upright on the timber floor, connected by a taut monofilament wire at ankle height. "
                "E_DOOR_01 is visible only at the top of frame as the bottom 15 centimeters of an opaque dark oak slab with weatherstripping. No full doorway in frame."
            ),
            "motion_prompt": "Low tracking crawl along the taut wire. Flashlight beam catches the green glass bottle shoulder in specular highlights. Subtle floor vibration shakes dust motes around the bottle base.",
            "negative_prompt": "glass door, full door view, broken glass everywhere, daylight",
        },

        # Act 2: Siege & Escalation (22 - 54s)
        {
            "id": "scene_04",
            "act": 2,
            "shot_number": 4,
            "duration": 8.0,
            "camera_scale": "medium",
            "framing": "50mm medium close-up door slab",
            "delta_state": {"interior_tape_layers": 3, "battery_pct": 40, "decibel_db": 67.4},
            "narration": "You check your tactical flashlight. Forty percent battery. Three layers of silver duct tape bind the interior frame.",
            "visual_prompt": (
                "MCU 50mm shot focused squarely on E_DOOR_01. The solid white-oak slab fills the entire frame. Window is OUT OF FRAME. "
                "Three parallel strips of industrial silver duct tape run taut from the timber door slab across to the reinforced drywall frame. "
                "Tactical gloved hand in foreground checks the amber LED battery readout on the flashlight body showing 40 percent. "
                f"Chiaroscuro lighting with deep pitch-black shadows. {contrastive_oak}"
            ),
            "motion_prompt": "Static handheld tension frame. Flashlight beam pulses slightly with low battery jitter. A sudden violent physical slam hits the outside of the door, causing the tape strips to stretch.",
            "negative_prompt": barrier_negatives,
        },
        {
            "id": "scene_05",
            "act": 2,
            "shot_number": 5,
            "duration": 8.0,
            "camera_scale": "close",
            "framing": "macro close-up tape seam",
            "delta_state": {"interior_tape_layers": 2, "battery_pct": 39, "decibel_db": 70.1},
            "narration": "A heavy impact shudders through the timber core. The top layer of duct tape peels back two inches.",
            "visual_prompt": (
                "Extreme close-up macro shot of the top silver duct tape layer across the oak door jamb. "
                "The adhesive edge has peeled back two inches under exterior mechanical shock, exposing white woven thread fibers under tension. "
                "Dark solid oak grain and steel mounting screws clearly visible under cold 6000K rake lighting. No window or exterior in frame."
            ),
            "motion_prompt": "Macro camera shiver synced to a resonant sub-bass thud. The silver tape edge curls back micro-millimeters in slow motion as dust puffs from the door seam.",
            "negative_prompt": "glass, transparent surface, daylight, human face",
        },
        {
            "id": "scene_06",
            "act": 2,
            "shot_number": 6,
            "duration": 8.0,
            "camera_scale": "medium",
            "framing": "tactical first-person POV pry-bar",
            "delta_state": {"interior_tape_layers": 2, "battery_pct": 37, "decibel_db": 72.8},
            "narration": "You tighten your gloved grip on the forged steel pry-bar. The decibel meter spikes to seventy-two.",
            "visual_prompt": (
                "First-person tactical POV. Weathered black nomex tactical gloves gripping the chipped hexagon shaft of a 30-inch forged steel pry-bar. "
                "Wrist-mounted digital sensor display glowing amber: 72.8 dB. In the background, the heavy oak door slab groans under repeated violent impacts. "
                "Rain visible only as rhythmic condensation droplets vibrating on the interior frame molding."
            ),
            "motion_prompt": "Gloves flex and tighten around the cold steel pry-bar bevel. Camera breathing accelerates in panic cadence. Flashlight beam flickers erratically at 80Hz.",
            "negative_prompt": barrier_negatives,
        },
        {
            "id": "scene_07",
            "act": 2,
            "shot_number": 7,
            "duration": 8.0,
            "camera_scale": "close",
            "framing": "50mm Dutch-angle deadbolt latch",
            "delta_state": {"interior_tape_layers": 2, "battery_pct": 35, "decibel_db": 76.5},
            "narration": "Metal screams against metal. The deadbolt brackets flex inward under sustained exterior weight. Sixty seconds of structural integrity.",
            "visual_prompt": (
                "Tight Dutch-angle 50mm shot on the heavy forged steel deadbolt mechanism on E_DOOR_01. "
                "The steel mounting plate shows hairline metal stress flaking around the screw heads. The heavy oak jamb beneath the plate resists deformation. "
                f"Cold harsh directional lighting casting elongated mechanical shadows across the door face. {contrastive_oak}"
            ),
            "motion_prompt": "Violent mechanical shuddering of the deadbolt cylinder. Metal bracket strains inward 2 millimeters against the timber core. Concrete dust falls from the upper door header.",
            "negative_prompt": barrier_negatives,
        },

        # Act 3: Climax & Unresolved Cliffhanger (54 - 74s)
        {
            "id": "scene_08",
            "act": 3,
            "shot_number": 8,
            "duration": 10.0,
            "camera_scale": "close",
            "framing": "macro strike plate fracture",
            "delta_state": {"interior_tape_layers": 1, "battery_pct": 32, "decibel_db": 81.0},
            "narration": "A sudden sickening crack splits the oak grain beside the strike plate. Then, absolute dead silence in the hallway.",
            "visual_prompt": (
                "Extreme macro shot of E_DOOR_01 beside the strike plate. A jagged radiating splinter fracture splits the deep dark oak grain vertically. "
                "A comma-shaped smear of dark fluid appears on the lower wood lip. "
                "The top two duct tape layers have torn in half, leaving only the single bottom reinforcement strip intact. "
                "Total pitch blackness in the background."
            ),
            "motion_prompt": "The jagged wood splinter widens 3 millimeters with a sharp acoustic crack, then all exterior hammering stops abruptly into suffocating dead silence. Camera holds breathless stillness.",
            "negative_prompt": barrier_negatives,
        },
        {
            "id": "scene_09",
            "act": 3,
            "shot_number": 9,
            "duration": 10.0,
            "camera_scale": "medium",
            "framing": "dynamic push-in first-person climax",
            "delta_state": {"interior_tape_layers": 0, "battery_pct": 30, "decibel_db": 84.5},
            "narration": "The center tape layer snaps. The door buckles four inches inward as you raise the pry-bar into darkness.",
            "visual_prompt": (
                "Dynamic medium push-in from survivor POV toward E_DOOR_01. "
                "The final silver tape strip snaps cleanly with frayed adhesive threads. The solid oak door slab violently buckles four inches inward into the apartment foyer. "
                "In foreground, survivor raises the forged steel pry-bar into striking posture. "
                "Through the four-inch black breach, wet dark shapes surge forward into the flashlight beam. Abrupt cut to black."
            ),
            "motion_prompt": "Violent sudden inward burst of the oak door slab. Pry-bar arcs upward into frame in defensive reaction. Flashlight beam illuminates airborne splinter shards and rushing shadows. Hard cut to black on impact.",
            "negative_prompt": "glass door, French door, bright room, CGI look",
        },
    ]

    # Run each scene's visual prompt through the compiler and text sanitizer
    for sc in raw_scenes:
        sc["narration"] = sanitize_spoken_text(sc["narration"])
        sc["visual_prompt"] = compile_udse_prompt(sc["visual_prompt"])

    return raw_scenes
