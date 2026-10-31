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

__all__ = [
    "GENRE_CATASTROPHE",
    "GenreArchetype",
    "detect_genre_archetype",
    "generate_catastrophe_scenes",
    "generate_universal_scenes",
    "build_llm_genre_system_prompt",
    "build_llm_catastrophe_system_prompt",
    "standardize_catastrophe_title",
    "format_catastrophe_title",
    "is_catastrophe_title",
    "snap_to_veo_duration",
]


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


# 6. PROCEDURAL CATASTROPHE / MEGA-DISASTER (PROVEN PROTOCOL)
GENRE_CATASTROPHE: str = "catastrophe"


def standardize_catastrophe_title(title: str) -> str:
    """Standardize catastrophe film titles into the canonical format:
    'What if [large number] [threat] hit [specific location]?'

    If the title already closely conforms, it is normalized and polished.
    Otherwise, keywords are extracted to construct the canonical title.
    """
    raw = (title or "").strip()
    if not raw:
        return "What if 1000 Volcanoes Hit Earth?"

    # If title already matches 'What if ...'
    m = re.match(r"^(what\s+if)\s+(.+)", raw, re.IGNORECASE)
    if m:
        body = m.group(2).strip().rstrip("?.!")
        return f"What if {body}?"

    # Check if title has a quantity and threat e.g. "1000 Volcanoes Erupting"
    m_qty = re.match(r"^(\d+|one\s+thousand|ten\s+thousand|a\s+thousand|hundreds\s+of)\s+(.+)", raw, re.IGNORECASE)
    if m_qty:
        qty = m_qty.group(1).title()
        threat = m_qty.group(2).strip().rstrip("?.!")
        return f"What if {qty} {threat} Hit Earth?"

    raw_lower = raw.lower()
    if "volcano" in raw_lower:
        return "What if 1000 Volcanoes Hit Earth?"
    if "asteroid" in raw_lower or "meteor" in raw_lower:
        return "What if 500 Asteroids Hit Earth?"
    if "tsunami" in raw_lower:
        return "What if an 80-Meter Tsunami Hit the Pacific Coast?"
    if "earthquake" in raw_lower:
        return "What if a Magnitude 10 Earthquake Hit San Francisco?"

    return f"What if {raw.title()} Hit Earth?"


def format_catastrophe_title(
    threat: str = "Volcanoes",
    number: int | str = 1000,
    location: str = "Earth",
) -> str:
    """Format title according to canonical niche template: 'What if [large number] [threat] hit [specific location]?'"""
    return f"What if {number} {threat} Hit {location}?"


def is_catastrophe_title(title: str) -> bool:
    """Check if title matches the Procedural Catastrophe niche title convention."""
    if not title:
        return False
    t = title.strip()
    pattern = r"(?i)^what\s+if\s+(\d+|[a-zA-Z]+)\s+.+"
    return bool(re.match(pattern, t))


_CATASTROPHE_BEATS_16_9: list[tuple[str, str, float]] = [
    (
        "Your world fractures into pure deafening pandemonium. The ground beneath your boots heaves upward by seven meters as the seismic needle shatters its glass housing.",
        "Macro push-in on a shattered seismic instrument gauge vibrating violently as hairline cracks spread across the glass face under flashing red emergency strobes.",
        4.0,
    ),
    (
        "You look to the horizon as a colossal wall of pressurized black ash punches thirty kilometers straight into the stratosphere at Mach three.",
        "Extreme wide-angle shot of towering pyroclastic eruption columns detonating into the upper atmosphere backlit by jagged volcanic lightning.",
        8.0,
    ),
    (
        "You wipe sulfur dust from your visor as the air pressure plunges by ninety millibars in ninety seconds, pulling hurricane-force winds of two hundred and forty kilometers per hour toward the caldera.",
        "Low-angle camera tracking heavy debris and glowing embers swept violently across wet buckled asphalt in gale-force winds.",
        8.0,
    ),
    (
        "Your digital dosimeter alarms at four hundred and fifty parts per million of toxic sulfur dioxide. Within twenty minutes, unprotected lungs will dissolve from acid fallout.",
        "Extreme macro shot of an industrial gas mask filter gauge pulsing deep amber as acid raindrops hiss against titanium casing.",
        8.0,
    ),
    (
        "You witness the entire tectonic shelf give way as an eighty-kilometer chasm tears open and liquid magma geysers shoot twelve hundred meters into the black sky. Silence falls, and the countdown to the next extinction begins.",
        "Suffocating high-contrast silhouette of survivor standing before a glowing tectonic rift as incandescent lava curtains illuminate the dark horizon.",
        8.0,
    ),
]

_CATASTROPHE_BEATS_9_16: list[tuple[str, str, float]] = [
    (
        "Your seismic needle shatters at magnitude nine. A wall of black ash punches thirty kilometers into the sky.",
        "Vertical macro push-in on cracked seismic needle vibrating violently as red warning strobes pulse in darkness.",
        4.0,
    ),
    (
        "You wipe burning sulfur from your visor. Atmospheric pressure is plunging ninety millibars a minute.",
        "Vertical low-angle shot of gloved gauntlet clearing volcanic ash from scratched visor as lightning illuminates falling debris.",
        4.0,
    ),
    (
        "You watch a pyroclastic shockwave roar downhill at three hundred kilometers per hour, vaporizing bridges under eight hundred degrees Celsius.",
        "Vertical tracking shot following tumbling burning debris and glowing pumice rushing past buckled guardrails.",
        6.0,
    ),
    (
        "You feel the ground liquefy beneath your boots as deep mantle fissures open because...",
        "Vertical downward silhouette shot bracing on crumbling rock ledge as glowing magma fissures split the ground apart.",
        6.0,
    ),
]


# REGISTRY OF ALL ARCHETYPES
_ARCHETYPES: dict[str, GenreArchetype] = {
    "catastrophe": GenreArchetype(
        slug="catastrophe",
        display_name="Procedural Catastrophe / Mega-Disaster",
        protagonist_role="Firsthand Witness / Planetary Survivor",
        tangible_metrics="Crust Displacement (420m), Atmospheric Ash (1.2B tons), Thermal Core Temp (5,000°C), Shockwave Mach (3.2), Decibel Level (180 dB)",
        diegetic_framing="Cracked glass barometer POV, vibrating seismic needle, molten horizon reflection in cracked thermal shield, macro dust fallout on steel",
        beats_16_9=_CATASTROPHE_BEATS_16_9,
        beats_9_16=_CATASTROPHE_BEATS_9_16,
    ),
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
    """Normalize input genre string into one of the canonical archetypes."""
    g = (genre or "").lower().strip()
    if any(k in g for k in ("catastrophe", "disaster", "volcano", "tsunami", "meteor", "asteroid", "earthquake", "apocalypse", "extinction", "caldera", "eruption")):
        return _ARCHETYPES["catastrophe"]
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


def _extract_event_hook_phrase(title: str, genre_slug: str) -> str:
    """Extract or formulate the high-stakes event phrase [X] for Scene 1 HOOK."""
    clean = re.sub(r"^(what\s+if\s+|the\s+day\s+|when\s+|how\s+)", "", title.strip(), flags=re.IGNORECASE)
    clean = clean.rstrip(".?!")
    clean_lower = clean.lower()

    if "volcano" in clean_lower:
        return "one thousand supervolcanoes erupt simultaneously across the tectonic crust"
    if "asteroid" in clean_lower or "meteor" in clean_lower:
        return "the colossal kinetic impact fractures the planetary crust"
    if "tsunami" in clean_lower:
        return "the eighty-meter mega-tsunami strikes the continental shelf"
    if "earthquake" in clean_lower:
        return "the magnitude ten fault rupture shears the bedrock"
    if genre_slug == "sci_fi":
        return "the primary reactor core containment fails"
    if genre_slug == "cyberpunk":
        return "the corporate ICE firewall initiates fatal neural lockout"
    if genre_slug == "deep_sea":
        return "the submarine hull buckles under four hundred atmospheres"
    if genre_slug == "survival_horror":
        return "the reinforced security deadbolt snaps in two"
    if genre_slug == "medieval_siege":
        return "the heavy iron portcullis shatters under the battering ram"
    if clean:
        return f"the catastrophe of {clean}"
    return "the global crust rupture"


_CATASTROPHE_MICRO_MATH: list[str] = [
    "At 5,000°C — 200x hotter than your oven; 7m vertical crust displacement in 0.4s",
    "Mach 3.0 pyroclastic column (3,700 km/h) reaching 30 km altitude; daylight lost in 40s",
    "28 Hz infrasound resonance at 130 dB; ionospheric disruption severing comms for 8B people",
    "90 millibars barometric plunge in 90s; 240 km/h inflow hurricane winds",
    "450 ppm toxic SO2 (15x lethal threshold); 20 minutes to hydrofluoric lung dissolution",
    "1,200 km/h shockwave; 40 km³ rock vaporized = 3,000,000 megatons TNT equivalent",
    "480°C autoignition at 20 miles; 600 mph pyroclastic surge vaporizing steel in 4s",
    "Magnitude 9.4 earthquake; 12m fault fissure; 2.1 Gs vertical ground acceleration",
    "200 billion tons seawater displaced; 80m tsunami wave traveling at 600 km/h",
    "0.02 lux light level (darker than moonless midnight); 1.8B tons aerosol blocking 92% solar flux",
    "350 km/h density current; house-sized granite boulders; 850°C local ground temp spike",
    "30,000 volcanic lightning strikes/hr; EMP destroying 70% microchips across 400 km",
    "pH 1.2 sulfuric acid rain; 80M metric tons SO3; 20 mm/hr concrete erosion rate",
    "400 high-voltage substations failed; 10,000,000 homes blackout in under 15s",
    "1,080 millibar pressure spike; acoustic pulse circling Earth 4x at 340 m/s",
    "15-ton volcanic bombs from 60,000 ft; 30m craters detonating with 500 lbs TNT equivalent",
    "300 million m³ boiling lahar volume; 80 km/h surge destroying bridges within 40 miles",
    "O2 level drops from 21.0% to 14.5% (critical hypoxia); CO2 pooling below 200m elevation",
    "50 cm ash accumulation = 300 kg/m² structural load; 85% roof collapse rate across 4 states",
    "5,000,000,000 gallons reservoir water lost; river temps surge to 72°C in 90 minutes",
    "48-foot tectonic displacement in 3 mins; 500,000 m³/s methane venting",
    "185 dB acoustic roar (45 dB above immediate human eardrum rupture threshold at 50 miles)",
    "60 million acres buried under 8 inches glass ash; global grain reserves exhausted in <42 days",
    "8°C temperature drop in 3 hours; 300 million metric tons stratospheric sulfate veil",
    "64% GPS signal degradation; 300 km emergency perimeter breached",
    "80 km crustal chasm; 1,200m mantle magma geysers shoot into stratosphere",
    "1,200-foot diameter fire tornado; 320 mph core vortex winds",
    "1,400°C exterior heat load; titanium bulkheads softening at 80% tensile limit",
    "200 purple lightning discharges/sec; 100% magnetic compass field distortion",
    "50 billion tons collapsing granite; 10 km wide vacuum sink caldera",
    "100-meter boiling wave wall; 250,000 tons/m² hydrostatic impact pressure",
    "80 mph soil liquefaction landslide; 4.2 Gs lateral shear stress",
    "360-degree circum-planetary ring of fire; 190 dB continuous acoustic energy",
    "2,500°C thermal wavefront; 0.5s emergency throttle response window",
    "100% ground defoliation; 2.4 million km² obsidian fallout crust",
    "6-year global volcanic winter; 15°C global temp drop; 1 in 10,000 survival ratio (0.01%)",
    "3% remaining battery; 48-hour secondary fault rupture countdown",
    "100% retention cliffhanger; 0-second gap to next simulation episode",
]


def _build_5act_scenes(
    title: str,
    archetype: GenreArchetype,
    duration: int = 300,
    aspect: str = "16:9",
) -> list[dict[str, Any]]:
    """Synthesize 38 structured scenes across 5 narrative acts for 4:30+ longform video."""
    event_hook = _extract_event_hook_phrase(title, archetype.slug)
    aspect_prefix = "Cinematic 16:9 landscape still." if aspect == "16:9" else "Cinematic 9:16 vertical mobile still."
    style_suffix = (
        f"Hyper-realistic {archetype.display_name} cinematography, {archetype.diegetic_framing}, "
        f"chiaroscuro shadows, zero face distortion, volumetric lighting, 8k resolution."
    )

    # 38 scene definitions: (narration, motion_prompt, camera_scale, duration)
    # Act 1: Scene 1 (0-4s, dur 4.0s) -> HOOK: "The moment [X] begins..."
    # Act 2: Scenes 2-5 (4-40s, dur [8.0, 10.0, 8.0, 10.0] = 36.0s) -> What is happening / Why it matters
    # Act 3: Scenes 6-25 (40-200s, 20 * 8.0s = 160.0s) -> Build-up (staged destruction + numerical data)
    # Act 4: Scenes 26-34 (200-270s, 8 * 8.0s + 1 * 6.0s = 70.0s) -> CLIMAX: Peak chaos
    # Act 5: Scenes 35-38 (270-300s, 3 * 8.0s + 1 * 6.0s = 30.0s) -> Aftermath + Subscribe hook
    raw_specs: list[tuple[str, str, str, float]] = [
        # --- ACT 1: HOOK (0-4s) ---
        (
            f"The moment {event_hook} begins, your world fractures into pure deafening pandemonium. The ground beneath your boots heaves upward by seven meters as the seismic needle shatters its glass housing.",
            "Suffocating macro push-in on a shattered seismic instrument gauge vibrating violently as hairline cracks spread across the glass face under flashing red emergency strobes.",
            "macro",
            4.0,
        ),
        # --- ACT 2: WHAT IS HAPPENING / WHY IT MATTERS (4-40s) ---
        (
            "You look to the horizon as a colossal wall of pressurized black ash punches thirty kilometers straight into the stratosphere at Mach three. The daylight disappears in less than forty seconds, replaced by a suffocating crimson twilight.",
            "Extreme wide-angle shot of towering pyroclastic eruption columns detonating into the upper atmosphere backlit by jagged volcanic lightning.",
            "wide",
            8.0,
        ),
        (
            "You hear the emergency sirens drown beneath a low-frequency hum that vibrates your ribcage at twenty-eight hertz. Satellites drop out of orbit as the ionizing thermal plume burns through the ionosphere, severing global communications for eight billion people.",
            "Macro shot of a tactical communication console dead with static, red warning LEDs strobing across a scratched metal panel as power lines outside flash-arc in blue sparks.",
            "close",
            10.0,
        ),
        (
            "You wipe sulfur dust from your visor as the air pressure plunges by ninety millibars in ninety seconds. The thermal radiation from expanding calderas creates a planetary vacuum, pulling hurricane-force winds of two hundred and forty kilometers per hour toward the epicenters.",
            "Low-angle camera tracking heavy debris and glowing embers swept violently across wet buckled asphalt in gale-force winds.",
            "medium",
            8.0,
        ),
        (
            "Your digital dosimeter alarms at four hundred and fifty parts per million of toxic sulfur dioxide. Within twenty minutes, unprotected lungs will dissolve from hydrofluoric acid rain. Your only route out is closing as the main highway buckles under tectonic shear.",
            "Extreme macro shot of an industrial gas mask filter gauge pulsing deep amber as acid raindrops hiss against titanium casing.",
            "macro",
            10.0,
        ),
        # --- ACT 3: BUILD-UP (STAGED DESTRUCTION + NUMERICAL DATA) (40-200s) ---
        (
            "You grip the steering wheel as a shockwave traveling at one thousand two hundred kilometers per hour slams into the valley. Over forty cubic kilometers of rock are vaporized instantly, releasing energy equal to three million megatons of TNT.",
            "Suffocating medium shot from inside the cockpit as a kinetic shockwave shatters perimeter concrete walls and sends shock ripples through reinforced safety glass.",
            "close",
            8.0,
        ),
        (
            "You watch the tree line twenty miles away spontaneously combust at four hundred and eighty degrees Celsius. A wall of superheated pyroclastic gas at six hundred miles per hour sweeps downhill, vaporizing steel bridges in less than four seconds.",
            "Wide panoramic tracking shot of an entire forested mountain range exploding into instantaneous wildfire under blinding thermal radiation.",
            "wide",
            8.0,
        ),
        (
            "Beneath your tires, a magnitude nine point four earthquake fractures the interstate, opening a twelve-meter fissure that swallows sixty-ton freight trucks whole. The bedrock accelerates upward at two point one Gs of vertical acceleration.",
            "Low-angle dynamic shot of reinforced concrete highway splitting down the median line, heavy vehicles tilting into the glowing subterranean rift.",
            "medium",
            8.0,
        ),
        (
            "In coastal sectors, underwater caldera collapses displace two hundred billion tons of seawater. You see radar telemetry warning of an eighty-meter tsunami traveling at six hundred kilometers per hour toward three continents.",
            "Extreme macro push-in on an analog green radar sweep displaying a catastrophic concentric wave wall accelerating across coastal bathymetry.",
            "macro",
            8.0,
        ),
        (
            "You check the ambient light meter: zero point zero two lux, darker than a moonless midnight at high noon. One point eight billion tons of volcanic aerosol now blanket the stratosphere, blocking ninety-two percent of incoming solar radiation.",
            "Suffocating high-contrast shot of midday sky turned into opaque obsidian pitch, illuminated only by erratic red lightning arcs in the ash clouds.",
            "close",
            8.0,
        ),
        (
            "You hear the roaring density current advancing at three hundred and fifty kilometers per hour, carrying granite boulders the size of suburban houses. The ground temperature spikes to eight hundred and fifty degrees Celsius within your five-mile sector.",
            "Medium-range telephoto shot of a towering avalanche of incandescent pumice and boulders pulverizing electrical pylons in violent slow motion.",
            "medium",
            8.0,
        ),
        (
            "Over thirty thousand volcanic lightning strikes per hour arc through the boiling plume above your head. Electromagnetic pulses fry seventy percent of all microchips within a four-hundred-kilometer radius.",
            "Wide cinematic skyward view capturing hundreds of simultaneous purple lightning bolts branching violently through an undulating black ash canopy.",
            "wide",
            8.0,
        ),
        (
            "You feel burning droplets eating through your protective coat: pure sulfuric acid with a pH of one point two. Over eighty million metric tons of sulfur trioxide mix with high-altitude moisture, corroding concrete structures at twenty millimeters per hour.",
            "Extreme macro shot of acid raindrops sizzling and bubbling against the paint of an armored hood, smoking vapor rising in sharp focus.",
            "macro",
            8.0,
        ),
        (
            "You watch the national power grid flatline as four hundred substations short-circuit simultaneously from conductive ash fallout. Ten million homes lose power in under fifteen seconds, leaving entire cities in frozen darkness around you.",
            "Distant panoramic view of a metropolitan skyline undergoing sequential blackout, transformers exploding in brilliant turquoise flashes before total darkness.",
            "wide",
            8.0,
        ),
        (
            "You watch your analog barometer spike to one thousand and eighty millibars before plunging. The acoustic shockwave circles the entire globe four times at three hundred and forty meters per second, shattering plate glass five thousand kilometers away.",
            "Macro shot of a brass aneroid barometer needle vibrating erratically against limit pins, beads of sulfur water running down the casing.",
            "close",
            8.0,
        ),
        (
            "You dodge massive volcanic bombs weighing up to fifteen tons raining down from sixty thousand feet at terminal velocity. Each impact crater measures thirty meters across beside your vehicle, detonating with the kinetic energy of five hundred pounds of high explosives.",
            "Dynamic ground-level shot of incandescent volcanic boulders crashing into wet soil, throwing geysers of burning mud and steam fifty meters into the air.",
            "medium",
            8.0,
        ),
        (
            "You watch glacial caps melt instantly atop alpine cones, unleashing three hundred million cubic meters of boiling volcanic mud. The slurry roars down river valleys at eighty kilometers per hour, obliterating every bridge within forty miles of your position.",
            "High-angle drone-style tracking shot of a boiling grey lahar surge ripping through a river basin, snapping concrete bridge piers like matchsticks.",
            "wide",
            8.0,
        ),
        (
            "Your oxygen analyzer warning chime sounds: ambient O2 levels drop from twenty-one percent to fourteen point five percent. Dense carbon dioxide pooling in low-lying valleys suffocates everything below two hundred meters elevation.",
            "Extreme macro close-up on a handheld oxygen monitor flashing 14.5% in harsh red digits against dark industrial gloves.",
            "macro",
            8.0,
        ),
        (
            "You measure ash accumulation reaching fifty centimeters on rooftops around you, weighing three hundred kilograms per square meter. Over eighty-five percent of residential structures collapse under the sheer kinetic load across four states.",
            "Low-angle medium view of industrial warehouse roofs bowing and catastrophically buckling under tons of heavy wet volcanic ash.",
            "close",
            8.0,
        ),
        (
            "You monitor the water supply: five billion gallons of freshwater reservoirs turn to caustic sludge within ninety minutes. The temperature of surrounding rivers spikes to seventy-two degrees Celsius, killing all aquatic life instantly.",
            "Atmospheric tracking shot along a steaming riverbank coated in white pumice foam, dead trees leaning into sulfurous boiling rapids.",
            "medium",
            8.0,
        ),
        (
            "Your satellite geodesy receiver reveals the tectonic plate has shifted forty-eight feet in three minutes. Deep mantle fissures release methane gas reserves at five hundred thousand cubic meters per second, turning the horizon into a wall of flame before you.",
            "Extreme wide silhouette shot of horizontal flame curtains stretching along a jagged tectonic fault line across the mountain ridge.",
            "wide",
            8.0,
        ),
        (
            "The continuous acoustic roar reaches one hundred and eighty-five decibels—loud enough to rupture human eardrums instantly at fifty miles distance. You press your hands against your helmet as sound waves physically shake your internal organs.",
            "Claustrophobic cockpit shot with vibrating rearview mirrors and acoustic shock patterns visible in liquid droplets on the dashboard.",
            "close",
            8.0,
        ),
        (
            "Across sixty million acres of farmland around you, crops are buried under eight inches of abrasive vitreous glass shards. You calculate that global grain reserves will last fewer than forty-two days under current depletion rates.",
            "Slow atmospheric pan across endless agricultural plains buried under a flat, sterile blanket of grey volcanic glass dust under an amber sky.",
            "medium",
            8.0,
        ),
        (
            "You feel the bitter chill setting in as ground temperatures drop by eight degrees Celsius in three hours. Over three hundred million metric tons of sulfate particles form an impenetrable veil across the Northern Hemisphere.",
            "Macro shot of frost crystals rapidly nucleating on a thermal metal plate alongside fine volcanic ash particles in freezing air.",
            "macro",
            8.0,
        ),
        (
            "The official safe perimeter of three hundred kilometers collapses as secondary calderas breach simultaneously. Your GPS loses satellite lock at sixty-four percent signal degradation. The point of no return has arrived.",
            "Medium shot of an in-dash navigation display showing NO SATELLITE SIGNAL flashing over an error grid as outside emergency beacons fade into black smoke.",
            "close",
            8.0,
        ),
        # --- ACT 4: CLIMAX (PEAK CHAOS) (200-270s) ---
        (
            "The entire tectonic shelf gives way. You witness the Earth's crust tear open in an eighty-kilometer chasm, exposing the glowing incandescent mantle beneath. Geysers of liquid magma shoot twelve hundred meters into the black sky.",
            "Colossal wide landscape shot of a yawning rift valley vomiting curtains of orange lava against a backdrop of towering ash pillars and purple lightning.",
            "wide",
            8.0,
        ),
        (
            "Two colliding pyroclastic hurricanes slam together directly over your escape corridor, generating a fire tornado twelve hundred feet wide with core winds of three hundred and twenty miles per hour.",
            "Terrifying low-angle tracking shot of a towering vortex of fire and swirling incandescent rock spiraling across the shattered landscape.",
            "medium",
            8.0,
        ),
        (
            "Your heat shield glows blinding orange as exterior thermal sensors max out at one thousand four hundred degrees Celsius. You can feel the metal bulkhead softening beneath your armored gloves.",
            "Suffocating interior macro view of steel bulkhead panels blistering and glowing dull crimson as thermal paint boils away.",
            "close",
            8.0,
        ),
        (
            "The sky ignites in a violent continuous web of purple volcanic lightning, firing two hundred discharges per second. Ozone and burning sulfur fill your intake valves as magnetic compasses spin uncontrollably.",
            "Extreme macro shot of an analog marine compass spinning wildly on its pivot, illuminated by rapid strobe flashes of electrical discharge.",
            "macro",
            8.0,
        ),
        (
            "You witness the central mountain cone implode into its empty magma chamber with the force of fifty billion tons of falling granite. A colossal vacuum crater forms before your eyes, sucking millions of tons of burning debris back into the abyss.",
            "Cinematic wide-angle view of a massive alpine peak collapsing inward in freefall, creating a gargantuan caldera crater ringed with flame.",
            "wide",
            8.0,
        ),
        (
            "You watch the mega-tsunami breach the outer continental shelf, throwing a hundred-meter wave of boiling water and pumice against coastal fortifications, obliterating entire cities in single impacts.",
            "Dramatic low-angle view of an immense black water wall carrying blazing debris crashing over reinforced sea walls and harbor structures.",
            "medium",
            8.0,
        ),
        (
            "High-frequency seismic tremors liquefy the soil beneath your vehicle. Entire hillsides slide downhill at eighty miles per hour as you accelerate through falling boulders and molten glass.",
            "Dynamic chase-cam angle from behind vehicle wheels fighting for traction on shifting liquefied mud and glowing pumice beds.",
            "close",
            8.0,
        ),
        (
            "Every horizon in three hundred and sixty degrees around you is now an unbroken ring of fire and boiling black columns. You hear the planet itself roaring like an industrial engine tearing its own cylinders apart.",
            "Stunning 360-degree panoramic sweep showing horizon entirely ablaze under towering columns of ash meeting at the zenith.",
            "wide",
            8.0,
        ),
        (
            "A blinding thermal flash detonates directly ahead of your path. You brace your hands, close your eyes behind your tinted visor, and punch the emergency throttle into the heart of the storm.",
            "Suffocating high-contrast silhouette of gloved hands slamming down the throttle lever as blinding white light washes over the entire cockpit frame.",
            "macro",
            6.0,
        ),
        # --- ACT 5: AFTERMATH + SUBSCRIBE HOOK (270-300s) ---
        (
            "When the roar finally subsides, an alien silence covers the continent. You step onto a new surface of cooling obsidian and grey particulate that stretches to every horizon without a single tree left standing.",
            "Slow atmospheric dolly across vast rolling dunes of dark grey volcanic ash and cooling black glass under an eerily calm amber twilight.",
            "wide",
            8.0,
        ),
        (
            "Your atmospheric models confirm the verdict: a global volcanic winter lasting six years, temperatures falling by fifteen degrees Celsius, and only one in ten thousand survivors equipped to endure the coming freeze.",
            "Macro view of an emergency weather terminal displaying falling global temperature curves and atmospheric opacity graphs in stark amber monochrome.",
            "close",
            8.0,
        ),
        (
            "You look down at your emergency transmitter, its battery down to three percent. Across the quiet airwaves, faint automated beacons begin warning that the Atlantic fault line is now preparing to breach.",
            "Extreme macro shot of a radio transceiver signal meter pulsing weakly at 3% battery, static hissing faintly from the speaker grille.",
            "macro",
            8.0,
        ),
        (
            (
                "If you want to survive the next planetary simulation, subscribe to the channel and turn on notifications now, because the countdown to the next catastrophe has already begun."
                if aspect == "16:9"
                else "If you want to survive the next planetary simulation, subscribe and turn on notifications now because..."
            ),
            "Chiaroscuro low-angle silhouette of survivor gazing toward distant smoking craters as glowing embers drift into darkness.",
            "medium",
            6.0,
        ),
    ]

    nominal_total = sum(item[3] for item in raw_specs)
    ratio = duration / nominal_total if nominal_total > 0 else 1.0

    scenes: list[dict[str, Any]] = []
    accumulated = 0.0

    for idx, (narration_raw, motion, camera_scale, default_dur) in enumerate(raw_specs):
        if idx == len(raw_specs) - 1:
            rem = duration - accumulated
            cur_dur = snap_to_veo_duration(rem) if rem > 0 else 6.0
        elif duration == 300:
            cur_dur = default_dur
        else:
            cur_dur = snap_to_veo_duration(default_dur * ratio)

        clean_narration = sanitize_spoken_text(narration_raw)
        visual_prompt = (
            f"{aspect_prefix} {title} - {clean_narration} {style_suffix}"
        )

        micro_math = _CATASTROPHE_MICRO_MATH[idx] if idx < len(_CATASTROPHE_MICRO_MATH) else f"Metrics for scene {idx + 1}"
        sc = {
            "id": f"scene_{idx + 1:02d}",
            "scene_number": idx + 1,
            "narration": clean_narration,
            "visual_prompt": visual_prompt,
            "motion_prompt": f"{motion} Continuous physical realism and natural momentum.",
            "camera_scale": camera_scale,
            "duration": cur_dur,
            "micro_math": micro_math,
            "recommended_tts_speed": 1.15,
        }
        scenes.append(sc)
        accumulated += cur_dur

    return scenes


_CATASTROPHE_5ACT_STRICT_SPECS: list[tuple[str, str, str, float]] = [
    # --- ACT 1: HOOK (0-4s) ---
    (
        "You stand frozen at ground zero as the catastrophe begins. At 5,000°C — 200x hotter than your oven, your world fractures into pure deafening pandemonium while the ground beneath your boots heaves upward by seven meters as the seismic needle shatters its glass housing.",
        "Suffocating macro push-in on a shattered seismic instrument gauge vibrating violently as hairline cracks spread across the glass face under flashing red emergency strobes.",
        "macro",
        4.0,
    ),
    # --- ACT 2: WHAT IS HAPPENING / WHY IT MATTERS (4-40s) ---
    (
        "You look to the horizon as a colossal wall of pressurized black ash punches thirty kilometers straight into the stratosphere at Mach three. The daylight disappears in less than forty seconds, replaced by a suffocating crimson twilight.",
        "Extreme wide-angle shot of towering pyroclastic eruption columns detonating into the upper atmosphere backlit by jagged volcanic lightning.",
        "wide",
        8.0,
    ),
    (
        "You hear the emergency sirens drown beneath a low-frequency hum that vibrates your ribcage at twenty-eight hertz. Satellites drop out of orbit as the ionizing thermal plume burns through the ionosphere, severing global communications for eight billion people.",
        "Macro shot of a tactical communication console dead with static, red warning LEDs strobing across a scratched metal panel as power lines outside flash-arc in blue sparks.",
        "close",
        10.0,
    ),
    (
        "You wipe sulfur dust from your visor as the air pressure plunges by ninety millibars in ninety seconds. The thermal radiation from expanding calderas creates a planetary vacuum, pulling hurricane-force winds of two hundred and forty kilometers per hour toward the epicenters.",
        "Low-angle camera tracking heavy debris and glowing embers swept violently across wet buckled asphalt in gale-force winds.",
        "medium",
        8.0,
    ),
    (
        "Your digital dosimeter alarms at four hundred and fifty parts per million of toxic sulfur dioxide. Within twenty minutes, unprotected lungs will dissolve from hydrofluoric acid rain. Your only route out is closing as the main highway buckles under tectonic shear.",
        "Extreme macro shot of an industrial gas mask filter gauge pulsing deep amber as acid raindrops hiss against titanium casing.",
        "macro",
        10.0,
    ),
    # --- ACT 3: BUILD-UP (STAGED DESTRUCTION + NUMERICAL DATA) (40-200s) ---
    (
        "You grip the steering wheel as a shockwave traveling at one thousand two hundred kilometers per hour slams into the valley. Over forty cubic kilometers of rock are vaporized instantly, releasing energy equal to three million megatons of TNT.",
        "Suffocating medium shot from inside the cockpit as a kinetic shockwave shatters perimeter concrete walls and sends shock ripples through reinforced safety glass.",
        "close",
        8.0,
    ),
    (
        "You watch the tree line twenty miles away spontaneously combust at four hundred and eighty degrees Celsius. A wall of superheated pyroclastic gas at six hundred miles per hour sweeps downhill, vaporizing steel bridges in less than four seconds.",
        "Wide panoramic tracking shot of an entire forested mountain range exploding into instantaneous wildfire under blinding thermal radiation.",
        "wide",
        8.0,
    ),
    (
        "Your vehicle shudders as a magnitude nine point four earthquake fractures the interstate beneath your tires, opening a twelve-meter fissure that swallows sixty-ton freight trucks whole. The bedrock accelerates upward at two point one Gs of vertical acceleration.",
        "Low-angle dynamic shot of reinforced concrete highway splitting down the median line, heavy vehicles tilting into the glowing subterranean rift.",
        "medium",
        8.0,
    ),
    (
        "You see radar telemetry warning of an underwater caldera collapse displacing two hundred billion tons of seawater. An eighty-meter tsunami traveling at six hundred kilometers per hour advances toward three continents.",
        "Extreme macro push-in on an analog green radar sweep displaying a catastrophic concentric wave wall accelerating across coastal bathymetry.",
        "macro",
        8.0,
    ),
    (
        "You check the ambient light meter: zero point zero two lux, darker than a moonless midnight at high noon. One point eight billion tons of volcanic aerosol now blanket the stratosphere, blocking ninety-two percent of incoming solar radiation.",
        "Suffocating high-contrast shot of midday sky turned into opaque obsidian pitch, illuminated only by erratic red lightning arcs in the ash clouds.",
        "close",
        8.0,
    ),
    (
        "You hear the roaring density current advancing at three hundred and fifty kilometers per hour, carrying granite boulders the size of suburban houses. The ground temperature spikes to eight hundred and fifty degrees Celsius within your five-mile sector.",
        "Medium-range telephoto shot of a towering avalanche of incandescent pumice and boulders pulverizing electrical pylons in violent slow motion.",
        "medium",
        8.0,
    ),
    (
        "You watch over thirty thousand volcanic lightning strikes per hour arc through the boiling plume above your head. Electromagnetic pulses fry seventy percent of all microchips within a four-hundred-kilometer radius.",
        "Wide cinematic skyward view capturing hundreds of simultaneous purple lightning bolts branching violently through an undulating black ash canopy.",
        "wide",
        8.0,
    ),
    (
        "You feel burning droplets eating through your protective coat: pure sulfuric acid with a pH of one point two. Over eighty million metric tons of sulfur trioxide mix with high-altitude moisture, corroding concrete structures at twenty millimeters per hour.",
        "Extreme macro shot of acid raindrops sizzling and bubbling against the paint of an armored hood, smoking vapor rising in sharp focus.",
        "macro",
        8.0,
    ),
    (
        "You watch the national power grid flatline as four hundred substations short-circuit simultaneously from conductive ash fallout. Ten million homes lose power in under fifteen seconds, leaving entire cities in frozen darkness around you.",
        "Distant panoramic view of a metropolitan skyline undergoing sequential blackout, transformers exploding in brilliant turquoise flashes before total darkness.",
        "wide",
        8.0,
    ),
    (
        "You watch your analog barometer spike to one thousand and eighty millibars before plunging. The acoustic shockwave circles the entire globe four times at three hundred and forty meters per second, shattering plate glass five thousand kilometers away.",
        "Macro shot of a brass aneroid barometer needle vibrating erratically against limit pins, beads of sulfur water running down the casing.",
        "close",
        8.0,
    ),
    (
        "You dodge massive volcanic bombs weighing up to fifteen tons raining down from sixty thousand feet at terminal velocity. Each impact crater measures thirty meters across beside your vehicle, detonating with the kinetic energy of five hundred pounds of high explosives.",
        "Dynamic ground-level shot of incandescent volcanic boulders crashing into wet soil, throwing geysers of burning mud and steam fifty meters into the air.",
        "medium",
        8.0,
    ),
    (
        "You watch glacial caps melt instantly atop alpine cones, unleashing three hundred million cubic meters of boiling volcanic mud. The slurry roars down river valleys at eighty kilometers per hour, obliterating every bridge within forty miles of your position.",
        "High-angle drone-style tracking shot of a boiling grey lahar surge ripping through a river basin, snapping concrete bridge piers like matchsticks.",
        "wide",
        8.0,
    ),
    (
        "Your oxygen analyzer warning chime sounds: ambient O2 levels drop from twenty-one percent to fourteen point five percent. Dense carbon dioxide pooling in low-lying valleys suffocates everything below two hundred meters elevation.",
        "Extreme macro close-up on a handheld oxygen monitor flashing 14.5% in harsh red digits against dark industrial gloves.",
        "macro",
        8.0,
    ),
    (
        "You measure ash accumulation reaching fifty centimeters on rooftops around you, weighing three hundred kilograms per square meter. Over eighty-five percent of residential structures collapse under the sheer kinetic load across four states.",
        "Low-angle medium view of industrial warehouse roofs bowing and catastrophically buckling under tons of heavy wet volcanic ash.",
        "close",
        8.0,
    ),
    (
        "You monitor the water supply: five billion gallons of freshwater reservoirs turn to caustic sludge within ninety minutes. The temperature of surrounding rivers spikes to seventy-two degrees Celsius, killing all aquatic life instantly.",
        "Atmospheric tracking shot along a steaming riverbank coated in white pumice foam, dead trees leaning into sulfurous boiling rapids.",
        "medium",
        8.0,
    ),
    (
        "Your satellite geodesy receiver reveals the tectonic plate has shifted forty-eight feet in three minutes. Deep mantle fissures release methane gas reserves at five hundred thousand cubic meters per second, turning the horizon into a wall of flame before you.",
        "Extreme wide silhouette shot of horizontal flame curtains stretching along a jagged tectonic fault line across the mountain ridge.",
        "wide",
        8.0,
    ),
    (
        "You press your hands against your helmet as the continuous acoustic roar reaches one hundred and eighty-five decibels—loud enough to rupture human eardrums instantly at fifty miles distance. Sound waves physically shake your internal organs.",
        "Claustrophobic cockpit shot with vibrating rearview mirrors and acoustic shock patterns visible in liquid droplets on the dashboard.",
        "close",
        8.0,
    ),
    (
        "You calculate that across sixty million acres of farmland around you, crops are buried under eight inches of abrasive vitreous glass shards. Global grain reserves will last fewer than forty-two days under current depletion rates.",
        "Slow atmospheric pan across endless agricultural plains buried under a flat, sterile blanket of grey volcanic glass dust under an amber sky.",
        "medium",
        8.0,
    ),
    (
        "You feel the bitter chill setting in as ground temperatures drop by eight degrees Celsius in three hours. Over three hundred million metric tons of sulfate particles form an impenetrable veil across the Northern Hemisphere.",
        "Macro shot of frost crystals rapidly nucleating on a thermal metal plate alongside fine volcanic ash particles in freezing air.",
        "macro",
        8.0,
    ),
    (
        "Your GPS loses satellite lock at sixty-four percent signal degradation as the official safe perimeter of three hundred kilometers collapses. Secondary calderas breach simultaneously, marking the arrival of the point of no return.",
        "Medium shot of an in-dash navigation display showing NO SATELLITE SIGNAL flashing over an error grid as outside emergency beacons fade into black smoke.",
        "close",
        8.0,
    ),
    # --- ACT 4: CLIMAX (PEAK CHAOS) (200-270s) ---
    (
        "You witness the entire tectonic shelf give way as the Earth's crust tears open in an eighty-kilometer chasm, exposing the glowing incandescent mantle beneath. Geysers of liquid magma shoot twelve hundred meters into the black sky.",
        "Colossal wide landscape shot of a yawning rift valley vomiting curtains of orange lava against a backdrop of towering ash pillars and purple lightning.",
        "wide",
        8.0,
    ),
    (
        "You steer through burning wreckage as two colliding pyroclastic hurricanes slam together directly over your escape corridor, generating a fire tornado twelve hundred feet wide with core winds of three hundred and twenty miles per hour.",
        "Terrifying low-angle tracking shot of a towering vortex of fire and swirling incandescent rock spiraling across the shattered landscape.",
        "medium",
        8.0,
    ),
    (
        "Your heat shield glows blinding orange as exterior thermal sensors max out at one thousand four hundred degrees Celsius. You can feel the metal bulkhead softening beneath your armored gloves as titanium begins to yield.",
        "Suffocating interior macro view of steel bulkhead panels blistering and glowing dull crimson as thermal paint boils away.",
        "close",
        8.0,
    ),
    (
        "You watch the sky ignite in a violent continuous web of purple volcanic lightning, firing two hundred discharges per second. Ozone and burning sulfur fill your intake valves as magnetic compasses spin uncontrollably.",
        "Extreme macro shot of an analog marine compass spinning wildly on its pivot, illuminated by rapid strobe flashes of electrical discharge.",
        "macro",
        8.0,
    ),
    (
        "You witness the central mountain cone implode into its empty magma chamber with the force of fifty billion tons of falling granite. A colossal vacuum crater forms before your eyes, sucking millions of tons of burning debris back into the abyss.",
        "Cinematic wide-angle view of a massive alpine peak collapsing inward in freefall, creating a gargantuan caldera crater ringed with flame.",
        "wide",
        8.0,
    ),
    (
        "You watch the mega-tsunami breach the outer continental shelf, throwing a hundred-meter wave of boiling water and pumice against coastal fortifications, obliterating entire cities in single impacts.",
        "Dramatic low-angle view of an immense black water wall carrying blazing debris crashing over reinforced sea walls and harbor structures.",
        "medium",
        8.0,
    ),
    (
        "You fight for control as high-frequency seismic tremors liquefy the soil beneath your vehicle. Entire hillsides slide downhill at eighty miles per hour as you accelerate through falling boulders and molten glass.",
        "Dynamic chase-cam angle from behind vehicle wheels fighting for traction on shifting liquefied mud and glowing pumice beds.",
        "close",
        8.0,
    ),
    (
        "You see every horizon in three hundred and sixty degrees around you become an unbroken ring of fire and boiling black columns. You hear the planet itself roaring like an industrial engine tearing its own cylinders apart.",
        "Stunning 360-degree panoramic sweep showing horizon entirely ablaze under towering columns of ash meeting at the zenith.",
        "wide",
        8.0,
    ),
    (
        "You brace your hands, close your eyes behind your tinted visor, and punch the emergency throttle into the heart of the storm as a blinding thermal flash detonates directly ahead of your path.",
        "Suffocating high-contrast silhouette of gloved hands slamming down the throttle lever as blinding white light washes over the entire cockpit frame.",
        "macro",
        6.0,
    ),
    # --- ACT 5: AFTERMATH + SUBSCRIBE HOOK (270-300s) ---
    (
        "You step onto a new surface of cooling obsidian and grey particulate that stretches to every horizon without a single tree left standing, as the roar finally subsides into an alien silence.",
        "Slow atmospheric dolly across vast rolling dunes of dark grey volcanic ash and cooling black glass under an eerily calm amber twilight.",
        "wide",
        8.0,
    ),
    (
        "Your atmospheric models confirm the verdict: a global volcanic winter lasting six years, temperatures falling by fifteen degrees Celsius, and only one in ten thousand survivors equipped to endure the coming freeze.",
        "Macro view of an emergency weather terminal displaying falling global temperature curves and atmospheric opacity graphs in stark amber monochrome.",
        "close",
        8.0,
    ),
    (
        "You look down at your emergency transmitter, its battery down to three percent. Across the quiet airwaves, faint automated beacons begin warning that the Atlantic fault line is now preparing to breach.",
        "Extreme macro shot of a radio transceiver signal meter pulsing weakly at 3% battery, static hissing faintly from the speaker grille.",
        "macro",
        8.0,
    ),
    (
        "SUBSCRIBE_PLACEHOLDER",
        "Chiaroscuro low-angle silhouette of survivor gazing toward distant smoking craters as glowing embers drift into darkness.",
        "medium",
        6.0,
    ),
]


def generate_catastrophe_scenes(
    title: str,
    duration: int = 300,
    aspect: str = "16:9",
) -> list[dict[str, Any]]:
    """Synthesize procedural catastrophe scenes adhering strictly to Protocol v4.0 & Phase 3 (R3).

    Mandatory Invariants:
    1. Title standard format: 'What if [large number] [threat] hit [specific location]?'.
    2. Strict 2nd-person singular perspective: Every scene's narration begins with 'You ' or 'Your '.
    3. Micro-mathematics required in voiceover narration and 'micro_math' metadata field.
    4. Fast-paced TTS speed recommendation 'recommended_tts_speed' (1.12–1.18, default 1.15).
    5. Scene durations conform to Google Veo tiers: [4.0, 6.0, 8.0, 10.0].
    """
    std_title = standardize_catastrophe_title(title)
    archetype = _ARCHETYPES["catastrophe"]
    aspect_prefix = "Cinematic 16:9 landscape still." if aspect == "16:9" else "Cinematic 9:16 vertical mobile still."
    style_suffix = (
        f"Hyper-realistic {archetype.display_name} cinematography, {archetype.diegetic_framing}, "
        f"chiaroscuro shadows, zero face distortion, volumetric lighting, 8k resolution."
    )

    if duration >= 180:
        specs = list(_CATASTROPHE_5ACT_STRICT_SPECS)
        nominal_total = sum(item[3] for item in specs)
        ratio = duration / nominal_total if nominal_total > 0 else 1.0

        scenes: list[dict[str, Any]] = []
        accumulated = 0.0

        for idx, (narration_raw, motion, camera_scale, default_dur) in enumerate(specs):
            if idx == len(specs) - 1:
                rem = duration - accumulated
                cur_dur = snap_to_veo_duration(rem) if rem > 0 else 6.0
                if aspect == "16:9":
                    narration_raw = (
                        "You must subscribe to the channel and turn on notifications now if you want to survive "
                        "the next planetary simulation, because the countdown to the next catastrophe has already begun."
                    )
                else:
                    narration_raw = (
                        "You must subscribe and turn on notifications now if you want to survive the next planetary simulation because..."
                    )
            elif duration == 300:
                cur_dur = default_dur
            else:
                cur_dur = snap_to_veo_duration(default_dur * ratio)

            clean_narration = sanitize_spoken_text(narration_raw)
            visual_prompt = f"{aspect_prefix} {std_title} - {clean_narration} {style_suffix}"
            micro_math = _CATASTROPHE_MICRO_MATH[idx] if idx < len(_CATASTROPHE_MICRO_MATH) else archetype.tangible_metrics

            sc = {
                "id": f"scene_{idx + 1:02d}",
                "scene_number": idx + 1,
                "narration": clean_narration,
                "visual_prompt": visual_prompt,
                "motion_prompt": f"{motion} Continuous physical realism and natural momentum.",
                "camera_scale": camera_scale,
                "duration": cur_dur,
                "micro_math": micro_math,
                "recommended_tts_speed": 1.15,
            }
            scenes.append(sc)
            accumulated += cur_dur

        return scenes

    # Shortform catastrophe mode (< 180s)
    beats_pool = _CATASTROPHE_BEATS_16_9 if aspect == "16:9" else _CATASTROPHE_BEATS_9_16
    scales = ["close", "close", "medium", "close", "medium", "wide", "close", "medium", "wide"]

    hook_beat = beats_pool[0]
    middle_beats = beats_pool[1:-1] if len(beats_pool) > 2 else [beats_pool[0]]
    closing_beat = beats_pool[-1]

    avg_dur = sum(b[2] for b in beats_pool) / len(beats_pool)
    num_scenes = max(3, round(duration / avg_dur))

    chosen_beats: list[tuple[str, str, float]] = [hook_beat]
    for i in range(num_scenes - 2):
        chosen_beats.append(middle_beats[i % len(middle_beats)])
    chosen_beats.append(closing_beat)

    nominal_total = sum(b[2] for b in chosen_beats)
    ratio = duration / nominal_total if nominal_total > 0 else 1.0

    scenes = []
    accumulated = 0.0

    for idx, (narration_raw, motion, default_dur) in enumerate(chosen_beats):
        if idx == len(chosen_beats) - 1:
            rem = duration - accumulated
            cur_dur = snap_to_veo_duration(rem) if rem > 0 else 4.0
        else:
            cur_dur = snap_to_veo_duration(default_dur * ratio)

        clean_narration = sanitize_spoken_text(narration_raw)
        visual_prompt = f"{aspect_prefix} {std_title} - {clean_narration} {style_suffix}"
        micro_math = _CATASTROPHE_MICRO_MATH[idx] if idx < len(_CATASTROPHE_MICRO_MATH) else archetype.tangible_metrics

        sc = {
            "id": f"scene_{len(scenes) + 1:02d}",
            "scene_number": len(scenes) + 1,
            "narration": clean_narration,
            "visual_prompt": visual_prompt,
            "motion_prompt": f"{motion} Continuous physical realism and natural momentum.",
            "camera_scale": scales[len(scenes) % len(scales)],
            "duration": cur_dur,
            "micro_math": micro_math,
            "recommended_tts_speed": 1.15,
        }
        scenes.append(sc)
        accumulated += cur_dur

    return scenes


def generate_universal_scenes(
    title: str,
    genre: str = "catastrophe",
    duration: int = 300,
    aspect: str = "16:9",
) -> list[dict[str, Any]]:
    """Synthesize structured scenes for any genre adhering to the universal retention architecture.

    Features:
    - 100% English 2nd-person singular narration ("You / Your").
    - Tangible high-stakes metrics tailored to the genre.
    - Diegetic camera framing with zero facial uncanny valley.
    - 5-Act longform structure for duration >= 180s (~38 scenes):
      - Scene 1 (0-4s): HOOK - "The moment [X] begins..."
      - Scenes 2-5 (4-40s): What is happening / Why it matters
      - Scenes 6-25 (40-200s): Build-up (staged destruction + numerical data)
      - Scenes 26-34 (200-270s): CLIMAX - Peak chaos
      - Scenes 35-38 (270-300s): Aftermath + Subscribe hook
    - Aspect-ratio tailored smart endings:
      - 16:9 -> Dramatic unresolved crisis cliffhanger beat / subscribe hook.
      - 9:16 -> Seamless audio loop hook ('because...') flowing directly back to Scene 1.
    """
    archetype = detect_genre_archetype(genre)

    # For longform productions (>= 180s, default 300s), execute full 5-act 38-scene generator
    if duration >= 180:
        return _build_5act_scenes(title=title, archetype=archetype, duration=duration, aspect=aspect)

    # Compact shortform mode (< 180s, e.g. 24s / 40s / 60s)
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


def build_llm_genre_system_prompt(
    title: str,
    genre: str,
    duration: int,
    aspect: str = "16:9",
) -> str:
    """Build dynamic LLM production prompt by delegating directly to live repository skills."""
    from engine.services.skill_loader import get_skill_loader

    return get_skill_loader().build_unified_system_prompt(
        title=title,
        genre=genre,
        duration=duration,
        aspect=aspect,
    )


def build_llm_catastrophe_system_prompt(
    title: str,
    duration: int = 300,
    aspect: str = "16:9",
) -> str:
    """Build high-fidelity LLM prompt instructing Grok to author Procedural Catastrophe scripts."""
    std_title = standardize_catastrophe_title(title)
    return build_llm_genre_system_prompt(
        title=std_title,
        genre="catastrophe",
        duration=duration,
        aspect=aspect,
    )
