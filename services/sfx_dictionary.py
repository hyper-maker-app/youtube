"""Tactile ASMR Foley Dictionary and Academic-to-Physical Prompt Translator.

Converts abstract scientific, biomedical, and mechanical event descriptions into
concrete, tactile, physical Foley terms understood by audio synthesis models
(ElevenLabs, MMAudio) following the Zack D. Films acoustic benchmark.
"""
from __future__ import annotations

import re
from typing import Any, Final

# ---------------------------------------------------------------------------
# Abstract academic / cinematography terms to strip before translation
# ---------------------------------------------------------------------------

_CINEMATOGRAPHY_JARGON: Final[re.Pattern[str]] = re.compile(
    r"\b(?:camera|at\s*t\s*=\s*[\d.]+s?|rapid|macro|push-?in|pull-?back|zoom|framing|"
    r"view|close-?up|shot|storyboard|interpolation|cinematic|render|visual|3d|cycles|"
    r"octane|blender|lighting|ultra-detailed|photorealistic)\b",
    re.IGNORECASE,
)

_ACADEMIC_ABSTRACTIONS: Final[re.Pattern[str]] = re.compile(
    r"\b(?:freezing point depression|massive convective heat transfer|dissolved electrolytes?|"
    r"colligative propert(?:y|ies)|osmotic pressure|solute concentration|hydrochloric acid secretion|"
    r"enzymatic degradation|peptic digestion|interfacial tension|pneumatic differential|"
    r"aerodynamic boundary layer|mechanical impedance|kinetic energy dissipation|"
    r"superficial lipid monolayer|transudate filtration|hemodynamic shear stress|"
    r"thermodynamic equilibrium|molecular kinetic motion|epithelial barrier integrity|"
    r"piezoelectric effect|triboelectric charging|cavitation erosion|viscoelastic deformation|"
    r"shear stress failure|microvascular occlusion|hydrostatic pressure gradient|"
    r"thermal shock resistance|fluid dynamic shear|tensile yield strength|dielectric breakdown|"
    r"vasoconstriction|vasodilation|action potentials?|intracellular fluids?|extracellular matrix|"
    r"adenosine triphosphate|mitochondrial respiration|ischemic reperfusion|microcellular apoptosis|"
    r"photoelastic stress)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Stop words to exclude from Foley prompt synthesis and tag extraction
# ---------------------------------------------------------------------------

_FOLEY_STOP_WORDS: Final[set[str]] = {
    "the", "and", "for", "with", "from", "that", "this", "into", "onto", "across",
    "along", "under", "over", "each", "every", "some", "such", "than", "then", "when",
    "where", "which", "while", "also", "just", "about", "above", "after", "again",
    "been", "being", "both", "down", "have", "here", "more", "most", "only", "other",
    "same", "their", "them", "there", "these", "they", "through", "very", "were",
    "what", "will", "your", "visible", "state", "changes", "moves", "transfers",
    "causes", "results", "shows", "appears", "undergoes", "produces", "generates",
    "induces", "exhibits", "displays",
}

# ---------------------------------------------------------------------------
# Tactile Foley semantic categories mapping keywords to physical ASMR sound
# ---------------------------------------------------------------------------

_TACTILE_FOLEY_CATEGORIES: Final[list[dict[str, Any]]] = [
    {
        "category": "freezing_ice",
        "keywords": (
            "freeze", "freezing", "frozen", "ice", "frost", "crystal", "crystallize",
            "crystallization", "sub-zero", "cold", "glaze", "chill", "rime", "frozen water",
            "ice sheet", "frostbite", "ice crack", "brittle",
        ),
        "foley": "crisp ice cracking snap, brittle crystallization crunch, high-frequency frost snap, ASMR tactile impact",
        "tags": ["ice", "frost", "snap", "crack", "crunch", "brittle", "break"],
    },
    {
        "category": "skin_contact_pinch",
        "keywords": (
            "pinch", "pinching", "nostril", "nostrils", "clamp mouth", "skin contact",
            "fingers press", "airtight seal", "soft skin squeeze", "holding nose",
        ),
        "foley": "soft tactile skin contact, subtle fleshy finger press, muted organic squeeze, clean ASMR touch",
        "tags": ["contact", "skin", "squeeze", "soft", "foley"],
    },
    {
        "category": "tympanic_eardrum_burst",
        "keywords": (
            "eardrum", "tympanic", "tympanic membrane", "eardrums", "middle ear",
            "eardrum rupture", "ear pop", "tympanic rupture", "rupture your eardrums",
            "eustachian tube opening", "eustachian orifice",
        ),
        "foley": "deep internal ear canal pressure pop, sudden tympanic membrane burst, muffled pneumatic release snap, crisp ASMR pressure pop",
        "tags": ["pop", "ear", "tympanic", "burst", "pressure", "snap"],
    },
    {
        "category": "tissue_tear_fissure",
        "keywords": (
            "tissue tear", "mucosal tear", "mucosal fissure", "mucosal lining", "throat tissue",
            "pharyngeal tissue", "pharyngeal lining", "microscopic tear", "lining tear", "tissue injury",
            "tear tiny holes", "radial tear", "micro-fissure", "tearing tissue", "fascial space",
            "pharyngeal mucosa", "separation fissure",
        ),
        "foley": "microscopic tissue tension tear, subtle fibrous mucosal snap, crisp ASMR micro-burst",
        "tags": ["tear", "tissue", "mucosal", "snap", "fissure", "organic"],
    },
    {
        "category": "fluid_wet",
        "keywords": (
            "fluid", "tears", "lacrimal", "tear droplet", "blood", "liquid", "droplet", "saliva", "mucus",
            "secretion", "wet", "slime", "aqueous", "water", "splash", "ooze", "stream",
            "lubricant", "lubricating", "moisture", "droplets", "secreting", "slosh",
            "squelch", "drip", "trickle", "bubble", "soap", "flow",
        ),
        "foley": "viscous liquid squelch, wet droplet surface tension pop, smooth fluid rush, tactile macro ASMR",
        "tags": ["liquid", "squish", "wet", "fluid", "slide", "viscous", "slosh"],
    },
    {
        "category": "heat_vascular",
        "keywords": (
            "heat", "thermal", "radiator", "vessel", "vessels", "bloodstream", "capillary",
            "circulation", "warm", "warmth", "dilation", "artery", "arteries", "pulse",
            "blood flow", "convection",
        ),
        "foley": "warm low-frequency sub pulse, deep vascular rush, subtle atmospheric whoosh",
        "tags": ["deep", "pulse", "rush", "whoosh", "warmth"],
    },
    {
        "category": "eyelid_wipe",
        "keywords": (
            "eyelid", "blink", "blinking", "wipe", "wiping", "cornea", "eye", "swipe",
            "eyelash", "membrane slide", "blinks", "eyelids", "slide",
        ),
        "foley": "soft fleshy eyelid sweep, subtle wet skin slide, gentle organic wipe",
        "tags": ["slide", "squish", "membrane", "wipe", "wet"],
    },
    {
        "category": "hydraulic_hiss",
        "keywords": (
            "hydraulic fluid", "hydraulic hiss", "hydraulic leak", "pinhole leak", "fluid jet",
            "pressurized spray", "brake line", "hydraulic cylinder", "actuator hiss",
            "hydraulic pressure", "hydraulic release", "actuator spray", "fluid pinhole",
        ),
        "foley": "high-pressure hydraulic fluid hiss, pressurized fluid jet spray, sharp hydraulic pinhole release, crisp ASMR micro-jet",
        "tags": ["hydraulic", "hiss", "pressure", "jet", "spray", "fluid", "release"],
    },
    {
        "category": "rotary_drill_cavitation",
        "keywords": (
            "drilling", "rotary burr", "dental drill", "ultrasonic cavitation",
            "cavitation erosion", "high-speed burr", "rotary tool", "drill bit", "cavitation hiss",
        ),
        "foley": "high-speed micro-drill buzz, rotary burr contact hum, ultrasonic cavitation hiss, crisp mechanical whine",
        "tags": ["drill", "rotary", "buzz", "hum", "mechanical", "whine"],
    },
    {
        "category": "metal_mechanical",
        "keywords": (
            "metal", "metallic", "steel", "iron", "door", "latch", "lock", "brake",
            "wedge", "gear", "piston", "clamp", "clamping", "lever", "shaft", "bolt",
            "cable", "pulley", "winch", "rail", "rails", "mechanism", "chassis", "friction brake",
            "clunk", "clank", "slam", "click", "buckle", "strap", "hydraulic", "spring",
            "hinge", "bearing", "torque", "grind", "drill",
        ),
        "foley": "heavy metallic clunk, mechanical latch snap, precision steel click, sub-bass mechanical punch",
        "tags": ["metal", "clunk", "snap", "mechanical", "click", "punch", "slam"],
    },
    {
        "category": "pressure_pneumatic",
        "keywords": (
            "pressure", "pneumatic", "steam", "decompression", "vacuum", "burst",
            "puncture", "valve", "release", "vent", "blowout", "pop", "hiss", "rupture",
            "alveoli", "expansion", "rebound", "pressurized", "suction", "deflate", "inflate",
        ),
        "foley": "explosive pneumatic hiss, pressurized burst pop, high-pressure release whoosh",
        "tags": ["chamber", "pop", "burst", "pressure", "release", "snap", "hiss"],
    },
    {
        "category": "cartilage_strain",
        "keywords": (
            "cartilage strain", "cartilage friction", "joint pop", "knuckle crack",
            "joint cavitation", "cavitation pop", "synovial", "crepitus", "tendon strain",
            "ligament strain", "ligament tension", "tendon snap",
        ),
        "foley": "sharp joint cavitation pop, fibrous tendon strain creak, organic cartilage friction snap, dense ASMR impact",
        "tags": ["pop", "snap", "cavitation", "joint", "creak", "tendon", "impact"],
    },
    {
        "category": "bone_cartilage",
        "keywords": (
            "bone", "skeleton", "skeletal", "fracture", "break", "breaking",
            "calcified cartilage", "cartilage fracture", "joint fracture",
            "spine", "vertebra", "skull", "rib", "tooth", "teeth", "calcified",
            "femur", "jaw", "crack", "cracking", "thud", "impact", "strike", "smash",
        ),
        "foley": "sharp bone snap crack, calcified structural snap, dense skeletal impact thud",
        "tags": ["crack", "snap", "break", "thud", "impact"],
    },
    {
        "category": "glass_crack_fissure",
        "keywords": (
            "glass crack", "hairline crack", "hairline fracture", "glass fissure", "brittle fissure", "stress fracture",
            "crazing", "brittle micro-crack", "surface crack", "glass stress", "cracking sound", "fracture line",
        ),
        "foley": "sharp hairline glass crack ping, brittle micro-fracture snap, delicate crystalline stress ticking, ASMR tactile fissure",
        "tags": ["glass", "crack", "snap", "ping", "fissure", "brittle", "stress"],
    },
    {
        "category": "glass_shatter",
        "keywords": (
            "glass", "shatter", "shattering", "crash", "crashing", "splinter", "windshield",
        ),
        "foley": "sharp glass shatter crack, brittle crystalline crash, explosive high-frequency debris snap",
        "tags": ["glass", "shatter", "crack", "crash", "debris", "snap"],
    },
    {
        "category": "muscle_tissue",
        "keywords": (
            "muscle", "contraction", "tissue", "flesh", "fleshy", "tendon", "ligament",
            "organ", "stomach wall", "membrane", "elastic", "stretch", "mucosal",
            "cellular", "contracting", "strain",
        ),
        "foley": "soft organic impact, damp tissue compression squelch, fleshy muscle thud",
        "tags": ["squish", "tissue", "organic", "impact", "thud"],
    },
    {
        "category": "acid_digestive",
        "keywords": (
            "acid", "gastric", "hydrochloric", "pepsin", "digest", "digestion", "dissolve",
            "dissolving", "corrosion", "corrosive", "enzymatic", "sizzle", "bubble", "bubbling",
            "fizz", "chyme",
        ),
        "foley": "bubbling acidic fizz, viscous enzymatic simmer, subtle organic digestive sizzle",
        "tags": ["liquid", "bubble", "fizz", "viscous", "acid"],
    },
    {
        "category": "micro_static_electricity",
        "keywords": (
            "electrostatic", "static charge", "static electricity", "triboelectric",
            "dielectric", "piezoelectric", "static shock", "ionization", "hair standing",
            "static crackle", "micro-spark", "electrostatic discharge", "static discharge",
        ),
        "foley": "crisp electrostatic snap, sharp micro-static crackle, dielectric ionization pop, subtle electric fizz",
        "tags": ["static", "snap", "crackle", "electric", "spark", "pop"],
    },
    {
        "category": "electrical",
        "keywords": (
            "electric", "electrical", "spark", "arc", "current", "voltage", "shock",
            "discharge", "static", "neural", "nerve", "synapse", "impulse",
        ),
        "foley": "sharp electric arc crackle, high-voltage spark snap, crisp dielectric pop",
        "tags": ["spark", "snap", "pop", "electric", "crackle"],
    },
    {
        "category": "rubber_friction_squeal",
        "keywords": (
            "rubber friction", "gasket drag", "seal friction", "elastomer scrub",
            "tire squeal", "tyre skid", "tread friction", "rubber drag", "rubber squeeze",
            "rubber seal", "elastomeric friction", "rubber scrub", "wiper squeak",
            "rubber", "gasket", "tire", "tyre", "wiper",
        ),
        "foley": "high-friction rubber squeal, tactile elastomeric gasket drag, dry rubber friction scrub, ASMR contact",
        "tags": ["friction", "rubber", "squeal", "drag", "scrub", "seal"],
    },
    {
        "category": "wind_aerodynamic",
        "keywords": (
            "wind", "air", "airflow", "aerodynamic", "turbine", "vortex", "draft",
            "suction", "gust", "atmosphere", "exhaust", "propulsion", "airframe", "turbulence",
        ),
        "foley": "turbulent air suction whoosh, atmospheric aerodynamic roar, rapid pressure vortex rush",
        "tags": ["whoosh", "deep", "rush", "air", "motion"],
    },
]


def sanitize_foley_text(text: str) -> str:
    """Strip cinematography directions and academic abstractions from input text."""
    if not text:
        return ""
    cleaned = _CINEMATOGRAPHY_JARGON.sub(" ", text)
    cleaned = _ACADEMIC_ABSTRACTIONS.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-;")
    return cleaned


def translate_to_tactile_foley(
    dominant_event: str,
    proof_on_screen: str = "",
    domain: str = "",
    narration_context: str = "",
) -> str:
    """Translate abstract narrative/scientific events into concrete tactile Foley prompts.

    Ensures that audio generation models (ElevenLabs, MMAudio) receive physical,
    tactile onomatopoeias matching the Zack D. Films sound design standard rather
    than academic or chemical abstractions.
    """
    raw_combined = f"{dominant_event} {proof_on_screen} {narration_context}".lower()
    cleaned_event = sanitize_foley_text(f"{dominant_event}, {proof_on_screen}")

    matched_categories: list[dict[str, Any]] = []
    seen_categories: set[str] = set()

    for entry in _TACTILE_FOLEY_CATEGORIES:
        category = entry["category"]
        if category in seen_categories:
            continue
        for kw in entry["keywords"]:
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, raw_combined):
                matched_categories.append(entry)
                seen_categories.add(category)
                break

    if matched_categories:
        # Prioritize top 2 categories to keep the prompt focused and punchy
        primary = matched_categories[0]["foley"]
        if len(matched_categories) > 1:
            secondary_part = matched_categories[1]["foley"].split(",")[0].strip()
            prompt = f"{primary}, {secondary_part}"
        else:
            prompt = primary
        return prompt

    # Fallback: synthesize a clean tactile Foley prompt from sanitized event text
    if cleaned_event:
        # Shorten, sanitize, and exclude non-descriptive stop words
        words = [
            w for w in re.findall(r"[a-z0-9]+", cleaned_event.lower())
            if len(w) >= 3 and w not in _FOLEY_STOP_WORDS
        ][:6]
        short_desc = " ".join(words)
        if short_desc:
            return f"{short_desc}, tactile acoustic foley, crisp ASMR micro-hit, authentic physical sound"

    # Default domain-matched tactile prompt
    if domain == "mechanical":
        return "heavy metallic clunk, mechanical latch snap, precision steel click, sub-bass mechanical punch"
    if domain == "incident":
        return "sharp physical impact thud, sudden mechanical release snap, crisp ASMR foley"
    return "viscous liquid squelch, wet surface tension pop, crisp ASMR tactile impact"


def get_tactile_sfx_tags(prompt: str, domain: str = "") -> list[str]:
    """Derive semantic search tags from tactile Foley prompt and domain for catalog matching."""
    tags: list[str] = []
    if domain:
        tags.append(domain)
    tags.extend(["foley", "diegetic"])

    prompt_lower = prompt.lower()
    for entry in _TACTILE_FOLEY_CATEGORIES:
        for kw in entry["keywords"]:
            if re.search(rf"\b{re.escape(kw)}\b", prompt_lower):
                tags.extend(entry["tags"])
                break

    # Add individual salient words excluding stop words and generic metadata tags
    words = [
        w for w in re.findall(r"[a-z0-9]+", prompt_lower)
        if len(w) >= 3
        and w not in _FOLEY_STOP_WORDS
        and w not in {"foley", "diegetic", "tactile", "asmr", "sound", "impact", "acoustic"}
    ]
    tags.extend(words)

    # Deduplicate while preserving order
    return list(dict.fromkeys(tags))

