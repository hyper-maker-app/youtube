# -*- coding: utf-8 -*-
"""Archived hand-written legacy-schema payloads for three prompt-study topics.

They are fixtures only and are not production input. Their old phase/annotation fields
are preserved so historical studies remain reproducible."""

# ---------------------------------------------------------------- breath (body_dive)
KF_B = {
    1: dict(subject_id="freediver_woman",
            subject_description="a young woman freediver in a sleek dark wetsuit, hair tied back, calm expression",
            journey_phase="establish", scale="wide",
            image_prompt="A young woman freediver in a sleek dark wetsuit floating vertically in deep open ocean, "
                         "calm expression, eyes closed, arms relaxed at her sides, suspended in a cathedral of "
                         "fading blue light, full body centred in frame, tiny against the vast water column",
            target_quadrant="center", asset_refs=[]),
    2: dict(subject_id="freediver_woman",
            subject_description="a young woman freediver in a sleek dark wetsuit, hair tied back, calm expression",
            journey_phase="descend", scale="medium",
            image_prompt="Torso of the young woman freediver filling the frame, chest wall gently rising, wetsuit "
                         "surface stretching over the ribcage, a neon-green arrow baked into the frame pointing at "
                         "the sternum in the upper-centre of the frame, hint of translucency at the skin",
            target_quadrant="upper_center", asset_refs=[]),
    3: dict(subject_id="freediver_woman",
            subject_description="a young woman freediver in a sleek dark wetsuit, hair tied back, calm expression",
            journey_phase="explore", scale="close",
            image_prompt="Clean cross-section through the freediver's chest revealing both lungs as glossy "
                         "translucent pink sacs, millions of tiny alveoli visible at the lung surface like sea foam, "
                         "a neon-green outline tracing the inflated alveolar clusters in the lower-right of the frame",
            target_quadrant="bottom_right", asset_refs=[]),
    4: dict(subject_id="alveolus_cluster",
            subject_description="a cluster of grape-like alveoli sacs, thin translucent membranes glistening with surfactant",
            journey_phase="explore", scale="macro",
            image_prompt="Macro view of a cluster of grape-like alveoli sacs, thin translucent membranes glistening "
                         "with surfactant, oxygen molecules diffusing across the membrane into a web of red capillaries, "
                         "a neon-green arrow pointing at the gas-exchange surface in the upper-left of the frame",
            target_quadrant="top_left", asset_refs=[]),
    5: dict(subject_id="glomus_cell",
            subject_description="a single glomus cell of the carotid body, studded with receptor proteins",
            journey_phase="explore", scale="micro",
            image_prompt="A single glomus cell of the carotid body studded with receptor proteins, CO2 molecules as "
                         "small dark spheres docking onto the receptors, each docking event triggering a tiny amber "
                         "calcium flash inside the cell, a neon-green outline ringing the most active receptor in the "
                         "upper-right of the frame",
            target_quadrant="top_right", asset_refs=[]),
    6: dict(subject_id="spleen",
            subject_description="the spleen, a dark red fist-sized organ with a fibrous capsule and spongy interior",
            journey_phase="reveal", scale="macro",
            image_prompt="The spleen, a dark red fist-sized organ, its fibrous capsule contracting and squeezing a "
                         "visible surge of extra red blood cells into an adjacent vessel, red trajectory lines baked "
                         "into the frame showing the cells erupting from the lower-left toward the vessel",
            target_quadrant="bottom_left", asset_refs=[]),
    7: dict(subject_id="spleen",
            subject_description="the spleen, a dark red fist-sized organ with a fibrous capsule and spongy interior",
            journey_phase="reveal", scale="macro",
            image_prompt="The same spleen now fully contracted and smaller, the last of the squeezed red blood cells "
                         "streaming into the vessel and dispersing, red trajectory lines fading as the surge settles, "
                         "vessel glowing faintly warmer from the oxygen-rich blood",
            target_quadrant="lower_center", asset_refs=[]),
    8: dict(subject_id="freediver_woman",
            subject_description="a young woman freediver in a sleek dark wetsuit, hair tied back, calm expression",
            journey_phase="resolve", scale="medium",
            image_prompt="The young woman freediver at the ocean surface, waterline cutting the frame, her head "
                         "breaking the surface as she exhales a visible plume of bubbles, chest fully expanded",
            target_quadrant="center", asset_refs=[]),
    9: dict(subject_id="freediver_woman",
            subject_description="a young woman freediver in a sleek dark wetsuit, hair tied back, calm expression",
            journey_phase="resolve", scale="medium",
            image_prompt="The young woman freediver at the surface, having just exhaled, now breaking into a wide "
                         "smile as she inhales deeply, droplets on her face, morning light on the water, calm and "
                         "triumphant, clean cinematic frame with no annotations",
            target_quadrant="center", asset_refs=[]),
}

SHOTS_B = [
    dict(block=1, start_keyframe_index=1, end_keyframe_index=2,
         motion_prompt="The freediver's chest wall rises on a held breath, the wetsuit surface stretching over her ribs",
         chain_from_prev=False, transition_hint="zoom_in"),
    dict(block=2, start_keyframe_index=2, end_keyframe_index=3,
         motion_prompt="The skin and ribs of the chest peel open in a single clean plane to expose the lungs",
         chain_from_prev=True, transition_hint="cross_section"),
    dict(block=3, start_keyframe_index=3, end_keyframe_index=4,
         motion_prompt="The lungs inflate and the alveoli swell, the viewpoint sinking toward one cluster",
         chain_from_prev=False, transition_hint="zoom_in"),
    dict(block=4, start_keyframe_index=4, end_keyframe_index=5,
         motion_prompt="CO2 molecules dock onto the glomus receptors, each docking triggering a small amber flash",
         chain_from_prev=False, transition_hint="zoom_in"),
    dict(block=5, start_keyframe_index=5, end_keyframe_index=6,
         motion_prompt="The spleen's capsule contracts and squeezes a surge of red blood cells into the vessel",
         chain_from_prev=False, transition_hint="zoom_out"),
    dict(block=6, start_keyframe_index=6, end_keyframe_index=7,
         motion_prompt="The squeezed cells stream out of the spleen and disperse into the bloodstream",
         chain_from_prev=True, transition_hint="zoom_out"),
    dict(block=7, start_keyframe_index=7, end_keyframe_index=8,
         motion_prompt="The freediver rises through the water column toward the brightening surface",
         chain_from_prev=False, transition_hint="zoom_out"),
    dict(block=8, start_keyframe_index=8, end_keyframe_index=9,
         motion_prompt="The freediver exhales a plume of bubbles and then smiles as she draws a full breath",
         chain_from_prev=True, transition_hint="none"),
]

BREATH = dict(
    journey=dict(type="body_dive", anchor_character_id="freediver_woman",
                 anchor_character_description="a young woman freediver in a sleek dark wetsuit, hair tied back, calm expression"),
    beats=[
        dict(index=1, role="myth", text="Holding your breath is pure willpower. Push harder, last longer.", emphasis=["willpower"]),
        dict(index=2, role="twist", text="But your second attempt always beats the first. And it has nothing to do with practice.",
             emphasis=["second", "always"]),
        dict(index=3, role="mechanism_a", text="Your carotid body reads carbon dioxide, not oxygen. It triggers the urge long before you are actually empty.",
             emphasis=["carbon", "dioxide"]),
        dict(index=4, role="mechanism_b", text="Then your spleen contracts, squeezing out a hidden reserve of oxygen-rich red cells, like a built-in scuba tank.",
             emphasis=["spleen", "reserve"]),
        dict(index=5, role="kicker", text="Your body was holding back on you the whole time.", emphasis=["holding"]),
    ],
    keyframes=[dict(index=i, **KF_B[i]) for i in range(1, 10)],
    shots=SHOTS_B,
)

# --------------------------------------------------------------- octopus (object_explode)
KF_O = {
    1: dict(subject_id="octopus",
            subject_description="a large Pacific octopus, russet-orange textured mantle, intelligent amber eyes",
            journey_phase="establish", scale="wide",
            image_prompt="A large Pacific octopus resting on a dark rocky reef, russet-orange textured mantle, "
                         "intelligent amber eyes, arms curled beneath it, full animal centred, moody underwater gloom",
            target_quadrant="center", asset_refs=[]),
    2: dict(subject_id="octopus",
            subject_description="a large Pacific octopus, russet-orange textured mantle, intelligent amber eyes",
            journey_phase="descend", scale="close",
            image_prompt="Close view of the octopus mantle, skin texture glistening, a neon-green arrow baked into "
                         "the frame pointing at the mantle cavity in the upper-centre of the frame, hint of the "
                         "organs within showing through the translucent skin",
            target_quadrant="upper_center", asset_refs=[]),
    3: dict(subject_id="octopus_hearts",
            subject_description="the three octopus hearts: one large central systemic heart and two smaller branchial hearts",
            journey_phase="explore", scale="macro",
            image_prompt="Cross-section of the octopus mantle revealing three hearts: one large central systemic heart "
                         "and two smaller branchial hearts flanking the gills, all glossy and faintly pulsing, a "
                         "neon-green outline tracing the central systemic heart in the lower-right of the frame",
            target_quadrant="bottom_right", asset_refs=[]),
    4: dict(subject_id="hemocyanin",
            subject_description="hemocyanin molecules, large pale blue-grey ring-shaped protein complexes with a copper centre",
            journey_phase="explore", scale="micro",
            image_prompt="Hemocyanin molecules drifting through blue-tinged blood plasma, large pale blue-grey "
                         "ring-shaped protein complexes, each with a copper atom at the binding centre glowing faint "
                         "turquoise, a neon-green arrow pointing at one copper centre in the upper-left of the frame",
            target_quadrant="top_left", asset_refs=[]),
    5: dict(subject_id="hemocyanin",
            subject_description="hemocyanin molecules, large pale blue-grey ring-shaped protein complexes with a copper centre",
            journey_phase="explore", scale="nano",
            image_prompt="A single hemocyanin complex at atomic scale, the copper atom at its centre now glowing bright "
                         "cyan-blue as it binds an oxygen molecule, protein ring flexing, absolute void around it, a "
                         "neon-green outline ringing the glowing copper in the upper-right of the frame",
            target_quadrant="top_right", asset_refs=[]),
    6: dict(subject_id="octopus_hearts",
            subject_description="the three octopus hearts: one large central systemic heart and two smaller branchial hearts",
            journey_phase="reveal", scale="macro",
            image_prompt="The systemic heart fibrillating and stalling during mating, its rhythm breaking into chaotic "
                         "flutters, red trajectory lines showing the faltering blood flow radiating from the heart in "
                         "the lower-left of the frame, the two branchial hearts dimming",
            target_quadrant="bottom_left", asset_refs=[]),
    7: dict(subject_id="octopus",
            subject_description="a large Pacific octopus, russet-orange textured mantle, intelligent amber eyes",
            journey_phase="reveal", scale="close",
            image_prompt="The octopus's eye in extreme close-up, a single droplet of water sliding from beneath the "
                         "eye like a tear, skin paling to grey, red trajectory lines faintly marking the slowing "
                         "pulse in the lower-right, the eye unblinking and fixed on the viewer",
            target_quadrant="bottom_right", asset_refs=[]),
    8: dict(subject_id="octopus",
            subject_description="a large Pacific octopus, russet-orange textured mantle, intelligent amber eyes",
            journey_phase="resolve", scale="medium",
            image_prompt="The octopus drifting slowly into a dark den in the reef, arms trailing, body pale and still, "
                         "beginning to turn away from the viewer into the shadows",
            target_quadrant="center", asset_refs=[]),
    9: dict(subject_id="octopus",
            subject_description="a large Pacific octopus, russet-orange textured mantle, intelligent amber eyes",
            journey_phase="resolve", scale="medium",
            image_prompt="The octopus settled into the dark den, arms curling around itself, one eye closing as it "
                         "turns fully away into the black, a final still and mournful pose, clean cinematic frame",
            target_quadrant="center", asset_refs=[]),
}

SHOTS_O = [
    dict(block=1, start_keyframe_index=1, end_keyframe_index=2,
         motion_prompt="The octopus breathes, its mantle slowly expanding and relaxing on the reef",
         chain_from_prev=False, transition_hint="zoom_in"),
    dict(block=2, start_keyframe_index=2, end_keyframe_index=3,
         motion_prompt="The mantle skin splits open in a single clean plane to reveal the three hearts",
         chain_from_prev=True, transition_hint="cross_section"),
    dict(block=3, start_keyframe_index=3, end_keyframe_index=4,
         motion_prompt="The viewpoint sinks into the bloodstream as hemocyanin rings drift past",
         chain_from_prev=False, transition_hint="match_cut"),
    dict(block=4, start_keyframe_index=4, end_keyframe_index=5,
         motion_prompt="A copper atom binds an oxygen molecule and flares bright cyan",
         chain_from_prev=True, transition_hint="zoom_in"),
    dict(block=5, start_keyframe_index=5, end_keyframe_index=6,
         motion_prompt="The systemic heart fibrillates and stalls, its rhythm breaking apart",
         chain_from_prev=False, transition_hint="zoom_out"),
    dict(block=6, start_keyframe_index=6, end_keyframe_index=7,
         motion_prompt="A single droplet of water slides from beneath the octopus's unblinking eye",
         chain_from_prev=False, transition_hint="whip"),
    dict(block=7, start_keyframe_index=7, end_keyframe_index=8,
         motion_prompt="The octopus drifts slowly back into the dark den, arms trailing",
         chain_from_prev=True, transition_hint="zoom_out"),
    dict(block=8, start_keyframe_index=8, end_keyframe_index=9,
         motion_prompt="The octopus turns away into the shadows and slowly closes its eye",
         chain_from_prev=True, transition_hint="none"),
]

OCTOPUS = dict(
    journey=dict(type="object_explode", anchor_character_id="octopus",
                 anchor_character_description="a large Pacific octopus, russet-orange textured mantle, intelligent amber eyes"),
    beats=[
        dict(index=1, role="myth", text="Octopuses have three hearts. More heart means more life.", emphasis=["three", "hearts"]),
        dict(index=2, role="twist", text="Wrong. That extra heart is exactly what kills them.", emphasis=["Wrong", "kills"]),
        dict(index=3, role="mechanism_a", text="Their blood runs on copper, not iron. It carries oxygen well in the cold, but it tires the main heart fast.",
             emphasis=["copper", "oxygen"]),
        dict(index=4, role="mechanism_b", text="When an octopus mates, the systemic heart simply stops. The body begins digesting itself from within.",
             emphasis=["systemic", "stops"]),
        dict(index=5, role="kicker", text="Three hearts, and still not enough to survive love.", emphasis=["survive"]),
    ],
    keyframes=[dict(index=i, **KF_O[i]) for i in range(1, 10)],
    shots=SHOTS_O,
)

# ----------------------------------------------------------------- bones (body_dive)
KF_N = {
    1: dict(subject_id="athlete_man",
            subject_description="a lean male athlete in dark training gear, short hair, focused expression",
            journey_phase="establish", scale="wide",
            image_prompt="A lean male athlete in dark training gear standing in a dark void, body angled, faint "
                         "warm glow seeping from within his torso and limbs as if his bones were lit from inside, "
                         "full body centred, dramatic and mysterious",
            target_quadrant="center", asset_refs=[]),
    2: dict(subject_id="athlete_man",
            subject_description="a lean male athlete in dark training gear, short hair, focused expression",
            journey_phase="descend", scale="close",
            image_prompt="Close view of the athlete's forearm, skin becoming translucent, a neon-green arrow baked "
                         "into the frame pointing at the radius bone glowing through the flesh in the upper-centre "
                         "of the frame",
            target_quadrant="upper_center", asset_refs=[]),
    3: dict(subject_id="bone_matrix",
            subject_description="cortical bone in cross-section, concentric osteon rings around a central canal",
            journey_phase="explore", scale="macro",
            image_prompt="Cross-section of cortical bone, concentric osteon rings around a central canal, the bone "
                         "surface shimmering and flowing like liquid metal, a neon-green outline tracing the molten "
                         "boundary in the lower-right of the frame",
            target_quadrant="bottom_right", asset_refs=[]),
    4: dict(subject_id="osteoclast",
            subject_description="a large multinucleated osteoclast cell, ruffled border pressed against bone",
            journey_phase="explore", scale="micro",
            image_prompt="A large multinucleated osteoclast cell pressed against the bone surface, its ruffled border "
                         "secreting acid that dissolves the mineral, bone matrix melting away in streams, a neon-green "
                         "arrow pointing at the dissolving front in the upper-left of the frame",
            target_quadrant="top_left", asset_refs=[]),
    5: dict(subject_id="hydroxyapatite",
            subject_description="hydroxyapatite mineral, hexagonal calcium phosphate crystals",
            journey_phase="explore", scale="nano",
            image_prompt="Hexagonal hydroxyapatite calcium phosphate crystals, calcium ions streaming off the lattice "
                         "like molten rivulets and being re-deposited, crystals glowing teal, a neon-green outline "
                         "ringing an active crystal face in the upper-right of the frame",
            target_quadrant="top_right", asset_refs=[]),
    6: dict(subject_id="osteoblast",
            subject_description="a cuboidal osteoblast cell laying down new bone matrix",
            journey_phase="reveal", scale="micro",
            image_prompt="A cuboidal osteoblast cell laying down fresh bone matrix, new hydroxyapatite crystallising "
                         "behind it like cooling metal, red trajectory lines showing calcium ions being driven into "
                         "the new lattice from the lower-left of the frame",
            target_quadrant="bottom_left", asset_refs=[]),
    7: dict(subject_id="bone_matrix",
            subject_description="cortical bone in cross-section, concentric osteon rings around a central canal",
            journey_phase="reveal", scale="macro",
            image_prompt="The bone cross-section now visibly remodelled, new brighter osteon rings layered over the "
                         "old, the molten glow settling as the surface re-hardens, red trajectory lines fading along "
                         "the rebuilt boundary in the lower-right",
            target_quadrant="bottom_right", asset_refs=[]),
    8: dict(subject_id="athlete_man",
            subject_description="a lean male athlete in dark training gear, short hair, focused expression",
            journey_phase="resolve", scale="medium",
            image_prompt="The athlete seen from the side, clenching his fist, the inner glow along his forearm bones "
                         "brightening for a moment through the translucent skin",
            target_quadrant="center", asset_refs=[]),
    9: dict(subject_id="athlete_man",
            subject_description="a lean male athlete in dark training gear, short hair, focused expression",
            journey_phase="resolve", scale="medium",
            image_prompt="The athlete looking down at his own clenched fist, raising it slightly as the inner glow "
                         "settles to a calm ember, a quiet knowing expression, clean cinematic frame with no annotations",
            target_quadrant="center", asset_refs=[]),
}

SHOTS_N = [
    dict(block=1, start_keyframe_index=1, end_keyframe_index=2,
         motion_prompt="The athlete's forearm bones begin to glow through the translucent skin",
         chain_from_prev=False, transition_hint="zoom_in"),
    dict(block=2, start_keyframe_index=2, end_keyframe_index=3,
         motion_prompt="The skin and muscle part in a single clean plane to expose the bone",
         chain_from_prev=True, transition_hint="cross_section"),
    dict(block=3, start_keyframe_index=3, end_keyframe_index=4,
         motion_prompt="The bone surface flows like liquid metal as the viewpoint sinks toward an osteoclast",
         chain_from_prev=False, transition_hint="match_cut"),
    dict(block=4, start_keyframe_index=4, end_keyframe_index=5,
         motion_prompt="Calcium ions stream off the hydroxyapatite lattice like molten rivulets",
         chain_from_prev=True, transition_hint="zoom_in"),
    dict(block=5, start_keyframe_index=5, end_keyframe_index=6,
         motion_prompt="An osteoblast lays down fresh matrix and new mineral crystallises behind it",
         chain_from_prev=False, transition_hint="zoom_out"),
    dict(block=6, start_keyframe_index=6, end_keyframe_index=7,
         motion_prompt="New bright osteon rings settle and re-harden over the remodelled bone",
         chain_from_prev=True, transition_hint="match_cut"),
    dict(block=7, start_keyframe_index=7, end_keyframe_index=8,
         motion_prompt="The athlete clenches his fist as the glow brightens along his forearm",
         chain_from_prev=False, transition_hint="zoom_out"),
    dict(block=8, start_keyframe_index=8, end_keyframe_index=9,
         motion_prompt="The athlete raises his fist slightly and looks at it as the glow settles",
         chain_from_prev=True, transition_hint="none"),
]

BONES = dict(
    journey=dict(type="body_dive", anchor_character_id="athlete_man",
                 anchor_character_description="a lean male athlete in dark training gear, short hair, focused expression"),
    beats=[
        dict(index=1, role="myth", text="Your bones are solid. Permanent. Dead scaffolding.", emphasis=["solid", "Dead"]),
        dict(index=2, role="twist", text="They are none of those things. Your skeleton is alive, and quietly flowing.",
             emphasis=["alive", "flowing"]),
        dict(index=3, role="mechanism_a", text="Cells called osteoclasts dissolve your bone from the inside, releasing calcium straight into your blood.",
             emphasis=["osteoclasts", "dissolve"]),
        dict(index=4, role="mechanism_b", text="Then osteoblasts rebuild it, crystal by crystal. You replace your entire skeleton roughly every ten years.",
             emphasis=["osteoblasts", "rebuild"]),
        dict(index=5, role="kicker", text="You are not the skeleton you were born with.", emphasis=["not"]),
    ],
    keyframes=[dict(index=i, **KF_N[i]) for i in range(1, 10)],
    shots=SHOTS_N,
)

RAW = {"breath": BREATH, "octopus": OCTOPUS, "bones": BONES}
