from __future__ import annotations

"""Universal Multi-Genre Narrative Engine for Grok Imagine Cinematic Studio v4.0.

Encodes the viral 2nd-person retention architecture across 5 canonical genre archetypes:
1. Sci-Fi / Deep Space (O2 PSI, coolant temp, airlock seal, helmet HUD POV)
2. Cyberpunk / Infiltration (ICE countdown, neural RAM %, 9mm ammo, retinal overlay POV)
3. Deep-Sea / Submarine (Atmospheric pressure ATM, hull fracture rate, ballast PSI, periscope POV)
4. Survival Horror (Decibel meter dB, potable water ml, barricade tape layers, peephole POV)
5. Historical / Medieval Siege (Torches left, arrow count, hours till dawn, arrow slit POV)

Mandatory Invariants:
- 100% English spoken narration and visual prompts ('en' / 'en-US').
- 2nd-person singular perspective ('You / Your'). Zero 3rd-person narration.
- In-media-res crisis hook within the first 3 seconds.
- Tangible, measurable high-stakes metrics (PSI, ATM, dB, %, ml, arrows).
- Diegetic & situational framing (zero human facial close-ups).
- Aspect-Aware Smart Endings:
  - 16:9 Landscape -> Unresolved micro-crisis cliffhanger forcing next episode.
  - 9:16 Vertical -> Seamless audio loop flowing directly back into Scene 1.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from services.text_sanitizer import sanitize_spoken_text

logger = logging.getLogger(__name__)


def snap_to_veo_duration(duration: float) -> float:
    """Snap a duration to the nearest supported Google Veo tier: [4.0, 6.0, 8.0, 10.0]."""
    tiers = [4.0, 6.0, 8.0, 10.0]
    return min(tiers, key=lambda t: abs(t - duration))


@dataclass(frozen=True)
class GenreArchetype:
    slug: str
    display_name: str
    protagonist_role: str
    tangible_metrics: str
    diegetic_framing: str
    beats_16_9: list[tuple[str, str, float]]
    beats_9_16: list[tuple[str, str, float]]


# 1. SCI-FI / DEEP SPACE
_SCIFI_BEATS_16_9: list[tuple[str, str, float]] = [
    (
        "Your breath fogs the gold-tinted visor of your pressurized EVA helmet. The bulkhead oxygen gauge pulses red: eight point four PSI and dropping rapidly.",
        "Macro push-in on a gold-tinted EVA helmet visor reflecting a blinking digital diagnostic HUD showing red pressure warnings.",
        6.0,
    ),
    (
        "You slap the manual seal override. Hydraulic clamps screech under the sudden vacuum differential, vibrating through your magnetic boots.",
        "Low-angle camera focusing on heavy magnetic mag-boots locking onto steel grating as a mechanical airlock door slams shut with violent force.",
        6.0,
    ),
    (
        "You watch external radiation monitors spike at four hundred rads per hour. Through your reinforced observation quartz, the dying star pulses with erratic coronal mass.",
        "Slow atmospheric dolly across reinforced quartz viewport, revealing blinding solar flare turbulence illuminating the dark cockpit in stark white light.",
        8.0,
    ),
    (
        "You grab the emergency coolant shunt. The primary reactor core is screaming at eight hundred and forty degrees, nine seconds from critical runaway.",
        "Extreme macro shot of gloved thermal gauntlets gripping an industrial coolant lever, pulling it downward against violent mechanical resistance.",
        6.0,
    ),
    (
        "Your digital timer counts down: zero three, zero two, zero one. The manual lever snaps loose in your grip. Deep within the reactor belly, the warning siren falls dead silent. You watch the blast doors slowly begin to unseal.",
        "Suffocating high-contrast silhouette shot of astronaut standing before the unsealing reactor bulkhead as ominous blinding white light floods the deck.",
        8.0,
    ),
]

_SCIFI_BEATS_9_16: list[tuple[str, str, float]] = [
    (
        "Your helmet oxygen gauge flickers at eight point four PSI. The airlock door shudders under explosive vacuum decompression.",
        "Vertical macro push-in on helmet visor reflecting flashing red decompression readouts, sparks showering in the background.",
        4.0,
    ),
    (
        "You slam the manual override lever with your shoulder. The coolant core is cooking at eight hundred degrees.",
        "Dynamic vertical downward tilt as gloved gauntlet wrenches a heavy emergency bypass valve amid venting nitrogen gas.",
        6.0,
    ),
    (
        "Your external sensors scream. You brace as a coronal storm wave slams into the outer hull, killing your backup generator.",
        "Shaky-cam vertical POV looking up through maintenance shaft as warning strobes die, plunging the corridor into stark emergency amber.",
        4.0,
    ),
    (
        "You have eighteen seconds of auxiliary air remaining in your tank. You reach for the final emergency seal because...",
        "Extreme vertical macro shot of trembling fingers gripping the final pneumatic seal release as the airlock rattles violently.",
        6.0,
    ),
]


# 2. CYBERPUNK / INFILTRATION
_CYBERPUNK_BEATS_16_9: list[tuple[str, str, float]] = [
    (
        "Your retinal overlay flickers in high-contrast cyan. The corporate ICE firewall gives you twenty-four seconds before total neural fry.",
        "Suffocating macro shot of a cracked cybernetic retinal implant reflecting cascading terminal hexadecimal code in saturated cyan and amber.",
        6.0,
    ),
    (
        "You crouch behind the server rack. A security drone's lidar grid sweeps within fourteen meters, neon rain sizzling against wet asphalt outside.",
        "Low-angle dolly track behind humming industrial server stacks, red lidar beams slicing through thick smoke and condensation.",
        6.0,
    ),
    (
        "You check your suppressed automatic. Seven armor-piercing rounds remaining in the magazine. No backup on this frequency.",
        "Extreme macro shot of tactical gloved hands sliding a polymer magazine into a matte-black sidearm with quiet mechanical precision.",
        6.0,
    ),
    (
        "Your intrusion counter hits zero. Heavy magnetic blast doors lock down the hall, and the drone's searchlight freezes directly on your cover.",
        "Dramatic Dutch-angle silhouette shot as a blinding white drone spotlight cuts through the neon haze, silhouetting the operative against wet concrete.",
        8.0,
    ),
    (
        "You pull the trigger and dive through the shattering glass. The terminal begins downloading the encrypted payload, but your biometric tracker flatlines. A second red laser appears on the wall beside your head.",
        "Slow-motion tracking shot of operative bursting through shattered window into midnight rain as neon city towers blur in the backdrop.",
        8.0,
    ),
]

_CYBERPUNK_BEATS_9_16: list[tuple[str, str, float]] = [
    (
        "Your retinal display counts down eighteen seconds until terminal ICE lockout. Combat drones are scanning the hallway.",
        "Vertical high-contrast POV looking down a rain-soaked neon corridor as red laser grids sweep across industrial server racks.",
        4.0,
    ),
    (
        "You rack the slide of your sidearm. Seven rounds left in the mag, sixty percent neural buffer.",
        "Vertical macro close-up on gloved fingers checking a digital ammo readout on the pistol slide under neon blue backlight.",
        4.0,
    ),
    (
        "The security blast doors slam shut behind you. You dodge showers of sparks as enemy footsteps accelerate toward your position.",
        "Rapid vertical tilt down a dark corporate stairwell as emergency sirens strobe and steel security grates crash down.",
        6.0,
    ),
    (
        "You dive behind the reinforced firewall console, finger tightening on the cold steel trigger because...",
        "Vertical low-angle silhouette shot bracing behind a glowing terminal rack as footsteps halt directly outside the doorway.",
        6.0,
    ),
]


# 3. DEEP-SEA / SUBMARINE THRILLER
_DEEPSEA_BEATS_16_9: list[tuple[str, str, float]] = [
    (
        "Four hundred and fifty atmospheres of black ocean press against your submarine hull. A rusted rivet snaps with the sound of a rifle shot beside your ear.",
        "Extreme macro shot of a pressurized brass rivet sheering off a dark steel bulkhead, high-pressure jet of icy seawater spraying across the frame.",
        6.0,
    ),
    (
        "Your analog depth gauge trembles at six thousand eight hundred meters. Your emergency battery reserve registers eighteen percent.",
        "Tight circular POV of a vibrating brass depth gauge surrounded by condensation beads, emergency amber floodlights flickering.",
        6.0,
    ),
    (
        "Through your periscope slit, the abyssal sonar sweeps out. You watch a massive acoustic return pulse on the phosphor screen: something living is rising from the trench.",
        "Green phosphor radar screen sweeping in circular rhythm, illuminating a tense silhouette peering through a rubber periscope eyepiece.",
        8.0,
    ),
    (
        "You haul on the emergency ballast blow valve with both hands. Fourteen hundred PSI of pressurized air roars into your tanks.",
        "Low-angle dynamic push-in on gloved hands straining against a rusted red wheel valve, muscle fibers tightening under extreme exertion.",
        6.0,
    ),
    (
        "Your vessel lurches upward, but the hull fracture splits another three inches down the center seam. The sonar ping returns in zero point two seconds. It is directly under your keel.",
        "Suffocating wide shot of the dark submarine control room tilting violently as water rushes across floorboards into the battery wells.",
        8.0,
    ),
]

_DEEPSEA_BEATS_9_16: list[tuple[str, str, float]] = [
    (
        "Four hundred atmospheres of ocean crush against your submarine hull. Cold water is spraying from your ceiling rivets.",
        "Vertical claustrophobic shot of high-pressure water blasting through a bulkhead seam under flashing crimson emergency beacons.",
        4.0,
    ),
    (
        "Your emergency battery is at eighteen percent. Your depth gauge shows six thousand meters and dropping.",
        "Vertical macro focus on an analog brass depth needle vibrating wildly as condensation streams down the scratched glass face.",
        4.0,
    ),
    (
        "You throw your entire weight against the emergency ballast wheel, forcing fourteen hundred PSI into your tanks.",
        "Vertical upward tracking shot of two hands wrenching a rusted valve wheel amid rising bilge water.",
        6.0,
    ),
    (
        "Your hull groans in agony as the sonar screen detects a gargantuan silhouette rising beneath your rudder because...",
        "Vertical POV looking down into dark flooded bilges as a deep sub-bass vibration shakes the entire frame.",
        6.0,
    ),
]


# 4. SURVIVAL HORROR (PROVEN PROTOCOL)
_SURVIVAL_BEATS_16_9: list[tuple[str, str, float]] = [
    (
        "Your breath fogs the inside of your gas mask. Outside your reinforced door, forty-two decibels of shuffling footsteps echo down the corridor. You do not move.",
        "Suffocating macro push-in on a reinforced steel door sealed with industrial duct tape under flickering amber emergency lighting.",
        6.0,
    ),
    (
        "You check your canteen. Seven hundred milliliters of clean water left. Forty-eight hours until extraction.",
        "Tight macro shot of gloved tactical fingers tilting an aluminum military canteen, gauging remaining fluid in shadow.",
        4.0,
    ),
    (
        "Through your brass peephole, you watch three pale infected silhouettes stagger past, their jerking rigor illuminated by distant strobe flares.",
        "Distorted point-of-view shot through a circular scratched brass peephole, pale silhouettes shambling past a dark flooded corridor.",
        8.0,
    ),
    (
        "Your digital audio meter flickers at sixty-four decibels. Sixty-five brings them clawing at your hinges.",
        "Extreme macro shot of a worn digital sensor display pulsing amber numbers: 64.2 dB, rain drumming against concrete outside.",
        4.0,
    ),
    (
        "A violent collision shakes your door frame. Multiple clawing hands breach the gap, tearing through three layers of duct tape. You strike your emergency magnesium flare, but the deadbolt snaps in two. Silence falls, and the doorknob begins to turn.",
        "Sudden Dutch-angle camera push on the buckling steel door as silver duct tape peels away, darkness engulfing the frame.",
        8.0,
    ),
]

_SURVIVAL_BEATS_9_16: list[tuple[str, str, float]] = [
    (
        "Your breath fogs your gas mask. Outside your reinforced door, footsteps echo down the wet corridor.",
        "Vertical macro push-in on reinforced door sealed with duct tape under amber strobe lighting.",
        4.0,
    ),
    (
        "Your decibel meter flickers at sixty-four. Sixty-five brings the horde tearing through your barricade.",
        "Vertical macro view of worn sensor screen flashing 64.2 dB as shadows glide beneath the door gap.",
        4.0,
    ),
    (
        "You tighten three more layers of heavy silver tape around the lock. Four hundred milliliters of water left in your canteen.",
        "Vertical downward tracking shot of gloved hands pulling duct tape across bent steel hinges.",
        6.0,
    ),
    (
        "Your door frame cracks inward under sudden violent impact. You grip your pry-bar and hold your breath because...",
        "Vertical silhouette shot of survivor raising crowbar in darkness as door hinges buckle toward the camera.",
        6.0,
    ),
]


# 5. HISTORICAL / MEDIEVAL SIEGE
_MEDIEVAL_BEATS_16_9: list[tuple[str, str, float]] = [
    (
        "Pitch-black midnight covers the ramparts. In your trembling grip, your last pine-pitch torch crackles against freezing rain, casting shadows over stone battlements.",
        "Atmospheric macro shot of rain hissing against a flaming pitch torch held in an iron gauntlet over dark wet fortress masonry.",
        6.0,
    ),
    (
        "You draw an iron bodkin arrow from your quiver. Four arrows left. Three hours until the first light of dawn breaks over your valley.",
        "Extreme macro shot of steel gauntlet fingers drawing a feathered bodkin arrow across a rough wooden longbow rest.",
        6.0,
    ),
    (
        "Through your stone arrow slit, you watch hundreds of enemy campfires stretch across the forest ridge, their war drums thumping at the rhythm of a heartbeat.",
        "Claustrophobic point-of-view shot through a narrow stone arrow slit, revealing sea of flickering torches in driving sleet.",
        8.0,
    ),
    (
        "A thunderous crash echoes through the flagstones beneath your boots. The iron chains of the inner portcullis shriek under the blows of an armored battering ram.",
        "Low-angle camera looking up at the groaning iron chains of a massive wooden portcullis as rust and stone dust rain down.",
        6.0,
    ),
    (
        "You draw your longbow to your cheek. The heavy oak gate splinters inward with a deafening roar. In the darkness below, the first iron scaling ladder slams against your parapet. Your torch sputters and goes out.",
        "Chiaroscuro silhouette of lone archer drawn at full draw on rain-swept castle battlements as darkness swallows the horizon.",
        8.0,
    ),
]

_MEDIEVAL_BEATS_9_16: list[tuple[str, str, float]] = [
    (
        "Your torch crackles in freezing rain. Down below your castle wall, hundreds of iron shields are marching.",
        "Vertical high-angle shot from stone battlements looking down into dark forest illuminated by enemy torchlight.",
        4.0,
    ),
    (
        "You check your quiver. Four bodkin arrows left. Three hours until sunrise.",
        "Vertical macro shot of iron gauntlet checking arrow fletchings in the shadow of stone ramparts.",
        4.0,
    ),
    (
        "The inner portcullis chains shriek as the battering ram smashes through the outer wooden gate beneath your feet.",
        "Vertical dynamic camera shake looking down castle stairwell as stone dust showers from vibrating arches.",
        6.0,
    ),
    (
        "You draw your bowstring back to your jawline, staring into the dark breach where the iron ladders slam because...",
        "Vertical low-angle silhouette of archer drawn against stormy night sky as grappling hooks catch the stone parapet.",
        6.0,
    ),
]


# REGISTRY OF ALL 5 ARCHETYPES
_ARCHETYPES: dict[str, GenreArchetype] = {
    "sci_fi": GenreArchetype(
        slug="sci_fi",
        display_name="Sci-Fi / Deep Space",
        protagonist_role="Stranded Ship Engineer / Astronaut",
        tangible_metrics="Oxygen PSI (8.4 PSI), Coolant Core Temp (840°C), Airlock Vacuum Differential, Radiation Rads/hr",
        diegetic_framing="Gold-tinted helmet HUD reflection, airlock override lever, observation quartz, magnetic boots",
        beats_16_9=_SCIFI_BEATS_16_9,
        beats_9_16=_SCIFI_BEATS_9_16,
    ),
    "cyberpunk": GenreArchetype(
        slug="cyberpunk",
        display_name="Cyberpunk / Infiltration",
        protagonist_role="Covert Netrunner / Rogue Infiltrator",
        tangible_metrics="ICE Counter Countdown (24s), Drone Lidar Radius (14m), Magazine Rounds (7), Neural Buffer %",
        diegetic_framing="Cracked retinal HUD overlay, suppressed pistol slide, server stacks, neon rain reflections",
        beats_16_9=_CYBERPUNK_BEATS_16_9,
        beats_9_16=_CYBERPUNK_BEATS_9_16,
    ),
    "deep_sea": GenreArchetype(
        slug="deep_sea",
        display_name="Deep-Sea / Submarine",
        protagonist_role="Deep-Sea Submarine Pilot",
        tangible_metrics="Atmospheric Pressure (450 ATM), Depth Gauge (6800m), Battery Reserve (18%), Ballast Valve (1400 PSI)",
        diegetic_framing="Scratched brass depth gauge, leaking ceiling rivets, periscope rubber eyepiece, emergency blow wheel",
        beats_16_9=_DEEPSEA_BEATS_16_9,
        beats_9_16=_DEEPSEA_BEATS_9_16,
    ),
    "survival_horror": GenreArchetype(
        slug="survival_horror",
        display_name="Survival Horror / Post-Apocalyptic",
        protagonist_role="Barricaded Urban Survivor",
        tangible_metrics="Decibel Meter (64.2 dB), Potable Water (700 ml), Barricade Duct Tape Layers (3), Flashlight Battery %",
        diegetic_framing="Scratched brass peephole POV, gloved pry-bar grip, amber LED meter, backlit silhouette in rain",
        beats_16_9=_SURVIVAL_BEATS_16_9,
        beats_9_16=_SURVIVAL_BEATS_9_16,
    ),
    "medieval_siege": GenreArchetype(
        slug="medieval_siege",
        display_name="Historical / Medieval Siege",
        protagonist_role="Lone Castle Defender / Parapet Archer",
        tangible_metrics="Pine-Pitch Torches (1), Bodkin Arrows (4), Hours Until Dawn (3 hrs), Portcullis Chain Stress",
        diegetic_framing="Stone arrow slit POV, wooden bow grip, vibrating portcullis chains, chiaroscuro torchlight on stone",
        beats_16_9=_MEDIEVAL_BEATS_16_9,
        beats_9_16=_MEDIEVAL_BEATS_9_16,
    ),
}


def detect_genre_archetype(genre: str) -> GenreArchetype:
    """Normalize input genre string into one of the 5 canonical archetypes."""
    g = (genre or "").lower().strip()
    if any(k in g for k in ("space", "sci-fi", "scifi", "alien", "star", "cosmic", "astronaut", "orbit")):
        return _ARCHETYPES["sci_fi"]
    if any(k in g for k in ("cyber", "punk", "hack", "noir", "infiltrat", "drone", "tactical", "matrix", "agent")):
        return _ARCHETYPES["cyberpunk"]
    if any(k in g for k in ("sea", "ocean", "sub", "abyss", "underwater", "trench", "marine", "nautical")):
        return _ARCHETYPES["deep_sea"]
    if any(k in g for k in ("medieval", "castle", "knight", "siege", "sword", "arrow", "ancient", "fantasy", "viking")):
        return _ARCHETYPES["medieval_siege"]
    # Default: Survival Horror / Post-Apocalyptic
    return _ARCHETYPES["survival_horror"]


def generate_universal_scenes(
    title: str,
    genre: str,
    duration: int = 40,
    aspect: str = "16:9",
) -> list[dict[str, Any]]:
    """Synthesize structured scenes for any genre adhering to the universal retention architecture.

    Features:
    - 100% English 2nd-person singular narration ("You / Your").
    - Tangible high-stakes metrics tailored to the genre.
    - Diegetic camera framing with zero facial uncanny valley.
    - Aspect-ratio tailored smart endings:
      - 16:9 -> Dramatic unresolved crisis cliffhanger beat.
      - 9:16 -> Seamless audio loop hook ('because...') flowing directly back to Scene 1.
    """
    archetype = detect_genre_archetype(genre)
    beats_pool = archetype.beats_16_9 if aspect == "16:9" else archetype.beats_9_16
    scales = ["close", "close", "medium", "close", "medium", "wide", "close", "medium", "wide"]

    hook_beat = beats_pool[0]
    middle_beats = beats_pool[1:-1] if len(beats_pool) > 2 else [beats_pool[0]]
    closing_beat = beats_pool[-1]

    # Calculate approximate number of scenes based on average beat duration (~6.0s)
    avg_dur = sum(b[2] for b in beats_pool) / len(beats_pool)
    num_scenes = max(3, round(duration / avg_dur))

    chosen_beats: list[tuple[str, str, float]] = [hook_beat]
    for i in range(num_scenes - 2):
        chosen_beats.append(middle_beats[i % len(middle_beats)])
    chosen_beats.append(closing_beat)

    nominal_total = sum(b[2] for b in chosen_beats)
    ratio = duration / nominal_total if nominal_total > 0 else 1.0

    scenes: list[dict[str, Any]] = []
    accumulated = 0.0

    for idx, (narration_raw, motion, default_dur) in enumerate(chosen_beats):
        if idx == len(chosen_beats) - 1:
            rem = duration - accumulated
            cur_dur = snap_to_veo_duration(rem) if rem > 0 else 4.0
        else:
            cur_dur = snap_to_veo_duration(default_dur * ratio)

        clean_narration = sanitize_spoken_text(narration_raw)
        aspect_style = "Cinematic 16:9 landscape still." if aspect == "16:9" else "Cinematic 9:16 vertical mobile still."
        visual_prompt = (
            f"{aspect_style} {title} - {clean_narration} "
            f"Hyper-realistic {archetype.display_name} cinematography, {archetype.diegetic_framing}, "
            f"chiaroscuro shadows, zero face distortion, volumetric lighting, 8k resolution."
        )

        sc = {
            "id": f"scene_{len(scenes)+1:02d}",
            "scene_number": len(scenes) + 1,
            "narration": clean_narration,
            "visual_prompt": visual_prompt,
            "motion_prompt": f"{motion} Continuous physical realism and natural momentum.",
            "camera_scale": scales[len(scenes) % len(scales)],
            "duration": cur_dur,
        }
        scenes.append(sc)
        accumulated += cur_dur

    return scenes


def build_llm_genre_system_prompt(title: str, genre: str, duration: int, aspect: str = "16:9") -> str:
    """Build high-fidelity LLM prompt instructing Grok to author genre-accurate 2nd-person scripts."""
    archetype = detect_genre_archetype(genre)
    ending_rule = (
        "SMART ENDING (16:9 CLIFFHANGER): The final scene must cut on an immediate, unresolved crisis that leaves the audience desperate for the next episode."
        if aspect == "16:9"
        else "SMART ENDING (9:16 SEAMLESS LOOP): The final scene's last sentence must be an open-ended clause ('because...', 'as you realize that...') that flows grammatically and rhythmically straight back into the very first words of Scene 1."
    )

    return (
        f"You are the master director for the high-end cinematic production '{title}'.\n"
        f"Genre: {archetype.display_name}. Protagonist Role: {archetype.protagonist_role}.\n"
        f"Target duration: {duration} seconds | Aspect Ratio: {aspect}.\n\n"
        "MANDATORY PRODUCTION INVARIANTS (Universal Retention Standard v4.0):\n"
        "- 100% English Only ('en' / 'en-US'). Zero Turkish or non-English text.\n"
        "- Narrative POV: Strictly 2nd-person singular ('You', 'Your'). Viewer IS the protagonist. 3rd-person narrator is strictly FORBIDDEN.\n"
        "- Opening Hook: In-media-res crisis within the first 3 seconds. Zero slow establishing shots.\n"
        f"- Tangible High-Stakes Metrics: Explicitly incorporate numerical constraints: {archetype.tangible_metrics}.\n"
        f"- Zero Facial Hallucination: Frame visually around situational perspective: {archetype.diegetic_framing}. Avoid close-up human faces.\n"
        "- Spoken Narration: 100% clean spoken prose. Do NOT include 'Act 1:', 'Scene 02:', or bracketed directives like '[Sound of sirens]'.\n"
        f"- {ending_rule}\n"
        "- Dynamic Block Durations: Choose durations from [4.0, 6.0, 8.0, 10.0] seconds.\n"
        f"- Scene count: Provide tightly connected scenes totaling approximately {duration} seconds."
    )
