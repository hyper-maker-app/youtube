"""Historical Truth Sheet ledger and source-grounded research service.

Implements the HiAPIAI pattern for documentary storytelling:
Compiles an immutable Historical Truth Sheet before script and prompt generation,
recording verified historical dates, historical eyewitness figures, authentic
period architecture/materials, sensory ground-level details ('In Media Res'),
and strictly prohibited anachronisms.

Zero network/transport calls are made in this module (strictly AST-clean).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from services.character import detect_era, get_era_witness


@dataclass
class HistoricalTruthSheet:
    """Authoritative historical ground-truth ledger for a documentary topic."""

    topic: str
    era: str
    civilization: str
    location_name: str
    time_period: str
    verified_dates: list[str] = field(default_factory=list)
    historical_figures: list[dict[str, str]] = field(default_factory=list)
    architecture_and_materials: list[str] = field(default_factory=list)
    sensory_details: list[str] = field(default_factory=list)
    prohibited_anachronisms: list[str] = field(default_factory=list)
    verified_facts: list[str] = field(default_factory=list)
    narrative_beats: list[dict[str, Any]] = field(default_factory=list)
    curated_beats: list[dict[str, Any]] = field(default_factory=list)

    def summary_for_prompt(self) -> str:
        """Render a concise summary block for LLM system prompts or prompt compiler injection."""
        anachronisms = ", ".join(self.prohibited_anachronisms[:6])
        materials = "; ".join(self.architecture_and_materials[:4])
        sensory = "; ".join(self.sensory_details[:3])
        dates = ", ".join(self.verified_dates[:3])
        return (
            f"HISTORICAL TRUTH SHEET [{self.era.upper()} — {self.location_name} ({dates})]:\n"
            f"- Authentic Materials: {materials}\n"
            f"- Ground-level Sensory Details: {sensory}\n"
            f"- STRICTLY FORBIDDEN ANACHRONISMS: {anachronisms}\n"
            "- Host Perspective: First-person ground-level sensory immersion ('In Media Res')."
        )


_CURATED_ERA_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "egyptian": {
        "civilization": "Ancient Egyptian Middle/New Kingdom",
        "location_name": "Faiyum Oasis & Hawara Plateau",
        "time_period": "c. 1850 BC – 450 BC",
        "verified_dates": ["c. 1840 BC (12th Dynasty reign of Amenemhat III)", "450 BC (Herodotus Visit)"],
        "architecture_and_materials": [
            "massive dressed white Tura limestone perimeter walls and lintels",
            "monolithic polished red Aswan granite columns and sliding portcullis blocks",
            "dense black basalt floor pavements with copper-saw striations",
            "fine unbleached linen kalasiris tunics with natural reed-fiber weaving",
            "bronze plumb-bobs, wooden cubit measuring rods, and papyrus architectural floorplans",
        ],
        "sensory_details": [
            "fine airborne limestone dust catching sharp diagonal shafts of golden morning sunlight",
            "the dry heat of the desert plateau contrasting with cool, damp subterranean air deep underground",
            "low reverberating acoustic resonance vibrating through multi-ton granite chamber slabs",
            "faint scent of sacred cedar resin, beeswax seals, and ancient desert groundwater canals",
        ],
        "prohibited_anachronisms": [
            "modern cranes", "steel rebar", "hydraulic excavators", "electric torches/flashlights",
            "modern cement/mortar", "sunglasses", "synthetic nylon ropes", "modern hardhats",
            "generic ancient costumes", "casual uncoordinated idle crowds",
        ],
        "verified_facts": [
            "The Labyrinth contained an estimated 3,000 rooms split between above-ground courts and subterranean crypts.",
            "Classical historians including Herodotus, Strabo, and Diodorus Siculus ranked it above the Giza Pyramids.",
            "Massive granite sliding plug-stones were engineered to seal the royal burial crypts permanently.",
        ],
    },
    "neolithic": {
        "civilization": "Pre-Pottery Neolithic A/B Anatolia",
        "location_name": "Göbeklitepe & Germuş Mountain Range",
        "time_period": "c. 9500 BC – 8000 BC",
        "verified_dates": ["c. 9500 BC (Enclosure D Construction)", "c. 8200 BC (Deliberate Backfilling)"],
        "architecture_and_materials": [
            "monolithic T-shaped limestone megaliths quarried from local plateau bedrock",
            "high-relief zoomorphic carvings of boars, foxes, vultures, and crawling serpents",
            "dry-stone circular enclosure perimeter walls bonded with clay mortar",
            "expertly dressed deerskin and flax tunics stitched with animal sinew",
            "hard flint chisels, basalt hammerstones, and wooden transport sledges",
        ],
        "sensory_details": [
            "rhythmic rhythmic thud of basalt hammerstones fracturing crystalline limestone bedrock",
            "scent of crushed wild grasses, woodsmoke from hearth fires, and damp red ochre paint",
            "cool mountain breeze whistling across the exposed hilltop megalithic circle",
            "tactile grit of limestone spalls under leather-wrapped footwear",
        ],
        "prohibited_anachronisms": [
            "metal tools", "bronze", "iron", "pottery/ceramic vessels", "wheeled carts",
            "domesticated horses", "written inscriptions", "glass", "modern survey tripods",
        ],
        "verified_facts": [
            "Göbeklitepe represents the oldest known monumental megalithic architecture on Earth, pre-dating Stonehenge by 6,000 years.",
            "T-shaped pillars symbolize stylized anthropomorphic figures with hands meeting above loincloths.",
            "The monumental enclosures were intentionally buried under hundreds of cubic meters of refuse around 8000 BC.",
        ],
        "curated_beats": [
            {
                "phase": "establish",
                "role": "host_nova",
                "text": "The wind howls across this ancient ridge; twelve thousand years ago, human civilization began right here.",
                "emphasis": ["ancient ridge", "twelve thousand years", "civilization began"],
                "scene": "panoramic sweeping establishing shot of Göbeklitepe limestone ridge under dramatic morning sky",
                "proof": "megalithic limestone enclosure circles carved into the Anatolian plateau bedrock",
                "scale": "wide",
            },
            {
                "phase": "establish",
                "role": "host_nova",
                "text": "Towering limestone megaliths rise on the hilltop, predating Stonehenge and agriculture by six millennia.",
                "emphasis": ["limestone megaliths", "predating Stonehenge", "six millennia"],
                "scene": "monumental T-shaped limestone pillars standing erect within circular stone enclosure D",
                "proof": "sixteen-ton dressed limestone megaliths quarried from bedrock without metal tools",
                "scale": "wide",
            },
            {
                "phase": "establish",
                "role": "host_nova",
                "text": "Prehistoric builders fractured sixteen-ton monoliths from solid bedrock using only heavy basalt hammerstones.",
                "emphasis": ["sixteen-ton", "solid bedrock", "basalt hammerstones"],
                "scene": "ancient bedrock quarry plateau showing deep chiseled channels around a half-extracted megalith",
                "proof": "fractured limestone bedrock trenches with basalt hammerstone impact craters",
                "scale": "medium",
            },
            {
                "phase": "explore",
                "role": "host_nova",
                "text": "Stepping into Enclosure D, massive circular dry-stone walls enclose colossal twin central pillars.",
                "emphasis": ["Enclosure D", "dry-stone walls", "central pillars"],
                "scene": "circular dry-stone enclosure perimeter walls stepping down to the central terrazzo floor",
                "proof": "concentric limestone rubble walls surrounding twin 5.5-meter central T-pillars",
                "scale": "medium",
            },
            {
                "phase": "explore",
                "role": "witness:Master Stone Carver Torkhan (9600 BC — Pre-Pottery Neolithic)",
                "text": "We do not build for shelter; these megaliths are living guardians between our ancestors and the sky.",
                "emphasis": ["shelter", "living guardians", "ancestors"],
                "scene": "documentary interview framing of Master Carver Torkhan holding knapped flint chisel",
                "proof": "authentic deerskin tunic, knapped flint chisel, and weathered prehistoric face",
                "scale": "medium",
            },
            {
                "phase": "explore",
                "role": "host_nova",
                "text": "Every joint was shaped with knapped flint blades, achieving razor-thin seams without mortar.",
                "emphasis": ["knapped flint", "razor-thin seams", "without mortar"],
                "scene": "macro close-up of limestone masonry joints showing microscopic flint chisel marks",
                "proof": "crystalline limestone surface bearing parallel percussion flake scar patterns",
                "scale": "macro",
            },
            {
                "phase": "descend",
                "role": "host_nova",
                "text": "Snarling foxes, predatory vultures, and venomous scorpions leap out from the stone in three dimensions.",
                "emphasis": ["snarling foxes", "predatory vultures", "three dimensions"],
                "scene": "extreme close-up of high-relief animal zoomorphic carvings on the flank of pillar 43",
                "proof": "high-relief carved snarling fox and predatory vulture with wings spread in stone",
                "scale": "close",
            },
            {
                "phase": "descend",
                "role": "host_nova",
                "text": "Carved arms and slender fingers wrap around each pillar, revealing stylized faceless human giants.",
                "emphasis": ["slender fingers", "faceless human giants"],
                "scene": "low-angle view of anthropomorphic central T-pillar showing carved relief arms and hands",
                "proof": "slender carved limestone arms and fingers meeting above a carved fox-pelt loincloth",
                "scale": "close",
            },
            {
                "phase": "escalate",
                "role": "host_nova",
                "text": "Touching these chisel marks, the sheer sophistication of prehistoric humans completely shatters modern assumptions.",
                "emphasis": ["chisel marks", "prehistoric humans", "shatters modern assumptions"],
                "scene": "host Nova examining tactile stone carvings inside Enclosure D at golden hour",
                "proof": "Nova's brass temporal chronometer reflecting warm sunset light against the carved T-pillar",
                "scale": "medium",
            },
            {
                "phase": "escalate",
                "role": "host_nova",
                "text": "Inside this megalithic circle, low acoustic reverberations echo like deep prehistoric ritual drums.",
                "emphasis": ["megalithic circle", "acoustic reverberations", "ritual drums"],
                "scene": "ground-level wide perspective inside the circular enclosure as shadows stretch across the floor",
                "proof": "concentric acoustic stone enclosure bouncing natural hilltop wind reverberations",
                "scale": "wide",
            },
            {
                "phase": "escalate",
                "role": "host_nova",
                "text": "The twin central pillars align toward the southern sky, tracking ancient seasonal constellations.",
                "emphasis": ["twin central pillars", "southern sky", "constellations"],
                "scene": "nighttime sky view above Enclosure D showing the central monoliths aligned with bright stars",
                "proof": "astronomical sightline framed between the twin limestone T-shaped monoliths",
                "scale": "wide",
            },
            {
                "phase": "reveal",
                "role": "host_nova",
                "text": "Nomadic hunter-gatherers organized hundreds of workers centuries before writing, pottery, or wheels.",
                "emphasis": ["nomadic hunter-gatherers", "organized hundreds", "before writing"],
                "scene": "cinematic wide vista across the Göbeklitepe hill showing multiple circular temple depressions",
                "proof": "terrace cutaways revealing monumental communal labor without domestic agriculture",
                "scale": "wide",
            },
            {
                "phase": "reveal",
                "role": "host_nova",
                "text": "Then, around eight thousand BC, they intentionally buried the entire sanctuary under tons of earth.",
                "emphasis": ["eight thousand BC", "intentionally buried", "tons of earth"],
                "scene": "cross-section view of intentional backfill layers composed of limestone spalls and animal bone fragments",
                "proof": "stratigraphic soil layers proving deliberate backfilling of the stone enclosures",
                "scale": "close",
            },
            {
                "phase": "resolve",
                "role": "host_nova",
                "text": "Subsurface radar scans reveal over twenty more monumental circular enclosures still sleeping underground.",
                "emphasis": ["radar scans", "twenty more", "underground"],
                "scene": "aerial drone perspective over the Germuş ridge showing buried circular geophysical anomalies",
                "proof": "ground-penetrating radar false-color overlay showing geometric subterranean circles",
                "scale": "wide",
            },
            {
                "phase": "resolve",
                "role": "host_nova",
                "text": "My temporal window closes, but Göbekli Tepe proves ancient humans mastered stone long before history recorded.",
                "emphasis": ["temporal window", "mastered stone", "history recorded"],
                "scene": "host Nova standing before the silhouette of Göbeklitepe at sunset as chronometer glows",
                "proof": "Nova's glowing temporal chronometer against the timeless horizon of Taş Tepeler",
                "scale": "medium",
            },
        ],
    },
    "greco_roman": {
        "civilization": "Classical Greco-Roman Antiquity",
        "location_name": "Mediterranean Basin & Rome",
        "time_period": "c. 500 BC – 200 AD",
        "verified_dates": ["c. 25 BC (Vitruvius De Architectura)", "79 AD (Pompeii Eruption)", "160 AD (Pausanias)"],
        "architecture_and_materials": [
            "pozzolanic hydraulic volcanic ash concrete and fired terracotta brick coursing",
            "monolithic fluted pentelic marble and travertine colonnades with Corinthian capitals",
            "hypocaust underfloor radiant heating flues and lead/terracotta water aqueducts",
            "draped hand-spun wool chitons, himations, and togas fastened with bronze fibulae",
            "groma surveying cross-staves, bronze water-levels (chorobates), and wax diptych tablets",
        ],
        "sensory_details": [
            "echoing murmur of market debate and sandals clapping across polished travertine paving",
            "pungent tang of lime mortar, olive oil lamps, and damp stone aqueduct vaults",
            "warm Mediterranean sunlight filtering through colonnaded peristyle courtyards",
            "tactile coolness of smooth marble revetment slabs under fingertip inspection",
        ],
        "prohibited_anachronisms": [
            "modern steel cables", "electric bulbs", "sunglasses", "synthetic textiles",
            "printed books", "wristwatches", "modern asphalt", "plastic containers",
        ],
        "verified_facts": [
            "Roman hydraulic concrete grew stronger over centuries due to saltwater reactions with aluminum tobermorite crystals.",
            "Vitruvius established the classical architectural triad of firmitas (strength), utilitas (utility), and venustas (beauty).",
        ],
    },
    "ottoman": {
        "civilization": "Classical Ottoman Empire",
        "location_name": "Konstantiniyye / Istanbul & Anatolia",
        "time_period": "c. 1453 AD – 1650 AD",
        "verified_dates": ["1557 AD (Süleymaniye Mosque Completion)", "1648 AD (Evliya Çelebi Expeditions)"],
        "architecture_and_materials": [
            "dense fossiliferous küfeki limestone ashlar masonry with Khorasan brick-dust mortar",
            "massive lead-sheathed central domes with interlocking acoustic cavity jars in pendentives",
            "subterranean cistern chambers with recycled Byzantine marble Corinthian capitals",
            "tailored wool kaftans and silk-woven entari robes with natural madder-root dye",
            "brass celestial astrolabes, illuminated architect parchment scrolls, and iron compasses",
        ],
        "sensory_details": [
            "subterranean water dripping in steady rhythmic drops across submerged marble cistern foundations",
            "scent of damp limestone, burning olive-oil lanterns, and rosewater from courtyard fountains",
            "magnificent acoustic resonance where a whisper under the dome carries across sixty paces",
            "cool, humid breeze rising from underground aqueduct shafts beneath the city streets",
        ],
        "prohibited_anachronisms": [
            "modern motorboats", "reinforced steel beams", "electric neon signs", "nylon umbrellas",
            "plastic piping", "digital cameras", "modern asphalt paving",
        ],
        "verified_facts": [
            "Imperial architect Mimar Sinan engineered flexible lead-and-iron masonry joints to withstand major Marmara earthquakes.",
            "Subterranean cisterns and aqueducts supplied freshwater across miles of hilly terrain beneath the capital.",
        ],
    },
}


def _build_pluggable_narrative_beats(topic: str, truth: dict[str, Any], era: str) -> list[dict[str, Any]]:
    """Construct standard 5-phase pluggable documentary beats (Script-Weaver pattern)."""
    clean_topic = re.sub(r"[^\w\s-]", "", topic).strip() or "this ancient site"
    materials = truth["architecture_and_materials"]
    sensory = truth["sensory_details"]
    facts = truth["verified_facts"]
    w1 = get_era_witness(era, 1)

    return [
        {
            "phase": "arrival_hook",
            "name": "Arrival Hook (In Media Res)",
            "role": "host_nova",
            "duration_hint": (6.0, 9.0),
            "summary": f"Immediate sensory immersion as Nova arrives at {clean_topic}.",
            "core_text": (
                f"The moment I step out onto the plateau of {clean_topic}, {sensory[0].lower()}. "
                f"Modern history told us this site was nearly forgotten, but standing directly before it, the sheer magnitude is impossible to ignore."
            ),
            "camera_style": "vlog_selfie_host",
            "is_a_roll": True,
        },
        {
            "phase": "street_life_and_context",
            "name": "Sensory Life & Context",
            "role": "host_nova",
            "duration_hint": (7.0, 11.0),
            "summary": f"Ground-level perspective exploring the environment and architecture of {clean_topic}.",
            "core_text": (
                f"Looking closely at the perimeter, {materials[0]}. "
                f"In this era, every surface is alive with activity—laborers cutting stone and priests charting celestial alignments."
            ),
            "camera_style": "cinematic_documentary",
            "is_a_roll": False,
        },
        {
            "phase": "investigation_mystery",
            "name": "Investigation / Core Mystery",
            "role": "host_nova",
            "duration_hint": (8.0, 12.0),
            "summary": f"Nova examines tactile tool marks and architectural anomalies at {clean_topic}.",
            "core_text": (
                f"Notice these joint seams in the masonry: {materials[1] if len(materials) > 1 else materials[0]}. "
                f"There is zero mortar gap between them. How ancient engineers achieved this tolerance without modern machinery remains the true mystery."
            ),
            "camera_style": "cinematic_documentary",
            "is_a_roll": False,
        },
        {
            "phase": "archaeological_reality",
            "name": "Historical Reality & Testimony",
            "role": f"witness:{w1['name']} ({w1['era_label']})",
            "duration_hint": (8.0, 14.0),
            "summary": f"Authentic historical eyewitness {w1['name']} reveals the construction secrets.",
            "core_text": (
                f"{facts[0] if facts else 'We carved these monumental chambers to withstand the test of millennia.'} "
                "Every angle was aligned with the sacred axes so the memory of our kingdom would outlast the stars."
            ),
            "camera_style": "historical_witness_interview",
            "is_a_roll": False,
            "is_witness": True,
        },
        {
            "phase": "legacy_reflection",
            "name": "Legacy & Modern Reflection",
            "role": "host_nova",
            "duration_hint": (7.0, 10.0),
            "summary": "Nova reflects on the lasting endurance of the site as her temporal window closes.",
            "core_text": (
                f"My chronometer indicates my time window here is closing, but radar scans in the present confirm {clean_topic}'s lower foundations still survive. "
                "History is not dead stone—it is waiting right beneath our feet."
            ),
            "camera_style": "vlog_selfie_host",
            "is_a_roll": True,
        },
    ]


def get_historical_truth_sheet(topic: str) -> HistoricalTruthSheet:
    """Compile or retrieve the authoritative Historical Truth Sheet for any topic."""
    era = detect_era(topic)
    raw = _CURATED_ERA_KNOWLEDGE.get(era)

    if not raw:
        # Dynamic synthesis for unrecognized eras
        clean_name = re.sub(r"[^\w\s-]", "", topic).strip() or "Ancient Sanctuary"
        raw = {
            "civilization": f"Historical Era of {clean_name}",
            "location_name": clean_name,
            "time_period": "Antiquity – Classical Period",
            "verified_dates": ["Historical Epoch of Construction", "Documented Archaeological Discovery"],
            "architecture_and_materials": [
                f"monolithic dressed limestone and regional ashlar stone masonry at {clean_name}",
                "hand-hewn timber support beams and authentic mortar joints",
                "hand-forged metal chisels, wooden wedges, and leveling plumb-bobs",
                "natural hand-spun wool and woven flax linen garments",
            ],
            "sensory_details": [
                f"cool air rising from shaded interior stone corridors at {clean_name}",
                "fine mineral dust catching shafts of golden natural daylight",
                "quiet echoing acoustics inside thick-walled stone sanctuaries",
            ],
            "prohibited_anachronisms": [
                "modern cranes", "steel scaffolding", "electric work-lights",
                "modern cement/rebar", "sunglasses", "synthetic clothing", "wristwatches",
            ],
            "verified_facts": [
                f"Archaeological excavations revealed complex foundational engineering at {clean_name}.",
                f"Surface ruins indicate advanced geometric planning across the {clean_name} complex.",
            ],
        }

    witnesses = [get_era_witness(era, 1), get_era_witness(era, 2)]
    beats = _build_pluggable_narrative_beats(topic, raw, era)

    return HistoricalTruthSheet(
        topic=topic,
        era=era,
        civilization=raw["civilization"],
        location_name=raw["location_name"],
        time_period=raw["time_period"],
        verified_dates=list(raw["verified_dates"]),
        historical_figures=witnesses,
        architecture_and_materials=list(raw["architecture_and_materials"]),
        sensory_details=list(raw["sensory_details"]),
        prohibited_anachronisms=list(raw["prohibited_anachronisms"]),
        verified_facts=list(raw["verified_facts"]),
        narrative_beats=beats,
        curated_beats=list(raw.get("curated_beats") or []),
    )
