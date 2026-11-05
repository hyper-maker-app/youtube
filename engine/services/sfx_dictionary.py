"""Tactile ASMR Foley Generator and Acoustic Prompt Translator.

Provides generic, dynamic translation of scene sound cues and physical event
descriptions into tactile, acoustic Foley prompts without hardcoded keyword
lookup tables or static narrative dictionaries.
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

# Generic empty registry preserved for backward compatibility
_TACTILE_FOLEY_CATEGORIES: Final[list[dict[str, Any]]] = []


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
    """Translate scene sound cues and physical events into concrete tactile Foley prompts.

    Purely dynamic: synthesizes Foley prompts directly from scene descriptions and cues,
    without hardcoded keyword dictionaries or static lookup tables.
    """
    raw_event = f"{dominant_event} {proof_on_screen}".strip()
    cleaned = sanitize_foley_text(raw_event)
    if not cleaned:
        cleaned = sanitize_foley_text(narration_context)

    if cleaned:
        words = [
            w for w in re.findall(r"[a-z0-9_-]+", cleaned.lower())
            if len(w) >= 3 and w not in _FOLEY_STOP_WORDS
        ][:8]
        desc = " ".join(words)
        if desc:
            domain_part = f" [{domain}]" if domain else ""
            return f"{desc}{domain_part}, acoustic physical foley, crisp tactile sound"

    if domain:
        return f"{domain} acoustic physical foley, crisp tactile sound"
    return "acoustic physical foley, crisp tactile sound"


def get_tactile_sfx_tags(prompt: str, domain: str = "") -> list[str]:
    """Derive semantic search tags dynamically from Foley prompt and domain."""
    tags: list[str] = []
    if domain:
        tags.append(domain.lower().strip())
    tags.extend(["foley", "diegetic"])

    clean = sanitize_foley_text(prompt).lower()
    words = [
        w for w in re.findall(r"[a-z0-9_-]+", clean)
        if len(w) >= 3
        and w not in _FOLEY_STOP_WORDS
        and w not in {"foley", "diegetic", "tactile", "acoustic", "sound", "physical"}
    ]
    tags.extend(words)

    # Deduplicate while preserving order
    return list(dict.fromkeys(tags))
