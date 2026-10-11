"""Unit tests for Tactile ASMR Foley Dictionary and Academic-to-Physical Prompt Translator."""
from __future__ import annotations

import pytest

from services.sfx_dictionary import (
    get_tactile_sfx_tags,
    sanitize_foley_text,
    translate_to_tactile_foley,
)


def test_translate_freezing_and_ice_academics():
    """Abstract freezing point depression must translate to tactile ice cracking."""
    prompt = translate_to_tactile_foley(
        "freezing point depression caused by dissolved electrolytes",
        proof_on_screen="macro camera zoom into ice crystal lattice",
        domain="anatomical",
    )
    assert "ice cracking snap" in prompt or "crystallization crunch" in prompt
    assert "freezing point depression" not in prompt
    assert "camera" not in prompt
    assert "macro" not in prompt


def test_translate_vascular_heat_transfer():
    """Convective heat transfer must translate to warm vascular rush."""
    prompt = translate_to_tactile_foley(
        "massive convective heat transfer from internal bloodstream",
        proof_on_screen="thermal radiation gradient",
        domain="anatomical",
    )
    assert "vascular rush" in prompt or "sub pulse" in prompt
    assert "convective" not in prompt
    assert "heat transfer" not in prompt


def test_translate_eyelid_wipe():
    """Eyelid blinking and wiping must translate to fleshy eyelid sweep."""
    prompt = translate_to_tactile_foley(
        "eyelid wipe sweeping across corneal surface",
        proof_on_screen="lubricating tear film layer",
        domain="anatomical",
    )
    assert "eyelid sweep" in prompt or "wet skin slide" in prompt or "organic wipe" in prompt


def test_translate_fluid_and_tears():
    """Fluid and secretions must produce viscous squelch and droplet pop."""
    prompt = translate_to_tactile_foley(
        "tear fluid secreting through lacrimal ducts",
        proof_on_screen="droplet surface tension",
        domain="anatomical",
    )
    assert "viscous liquid squelch" in prompt or "wet droplet" in prompt


def test_translate_mechanical_metal_latch():
    """Elevator wedge clamping or mechanical latching must produce heavy metallic clunk."""
    prompt = translate_to_tactile_foley(
        "emergency wedge clamping onto elevator guide rails",
        proof_on_screen="steel brake engagement",
        domain="mechanical",
    )
    assert "metallic clunk" in prompt or "latch snap" in prompt or "steel click" in prompt


def test_translate_pressure_pneumatic():
    """Pneumatic decompression or burst must produce explosive hiss or burst pop."""
    prompt = translate_to_tactile_foley(
        "pressurized chamber valve release blowout",
        proof_on_screen="rapid pneumatic decompression",
        domain="mechanical",
    )
    assert "pneumatic hiss" in prompt or "burst pop" in prompt or "pressure release" in prompt


def test_translate_bone_fracture():
    """Bone fracture and impact must produce sharp bone snap crack."""
    prompt = translate_to_tactile_foley(
        "dense cortical bone fracture under sudden compression",
        proof_on_screen="microscopic fissure crack",
        domain="anatomical",
    )
    assert "bone snap crack" in prompt or "structural snap" in prompt


def test_translate_gastric_acid():
    """Acid secretion and digestion must produce bubbling acidic fizz."""
    prompt = translate_to_tactile_foley(
        "hydrochloric acid secretion dissolving food particles",
        proof_on_screen="peptic enzyme bubbling",
        domain="anatomical",
    )
    assert "bubbling acidic fizz" in prompt or "enzymatic simmer" in prompt


def test_translate_electrical_spark():
    """Electrical current and arc must produce sharp electric arc crackle."""
    prompt = translate_to_tactile_foley(
        "high-voltage static discharge arc across wire",
        proof_on_screen="spark snap",
        domain="mechanical",
    )
    assert "electric arc crackle" in prompt or "spark snap" in prompt


def test_translate_wind_aerodynamic():
    """Atmospheric airflow and turbine must produce turbulent air suction whoosh."""
    prompt = translate_to_tactile_foley(
        "rapid airflow rushing past turbine intake vortex",
        proof_on_screen="aerodynamic pressure streamlines",
        domain="mechanical",
    )
    assert "air suction whoosh" in prompt or "vortex rush" in prompt


def test_translate_fallback_clean_desc():
    """Unknown generic events must be sanitized and formatted cleanly."""
    prompt = translate_to_tactile_foley(
        "camera push-in on an unknown spinning object at t=1.5s",
        proof_on_screen="",
        domain="incident",
    )
    assert "tactile" in prompt.lower()
    assert "foley" in prompt.lower()
    assert "camera" not in prompt
    assert "t=1.5s" not in prompt


def test_get_tactile_sfx_tags():
    """Derived tags must include foley, diegetic, and category tags."""
    tags = get_tactile_sfx_tags("crisp ice cracking snap, brittle crystallization crunch", domain="anatomical")
    assert "foley" in tags
    assert "diegetic" in tags
    assert "anatomical" in tags
    assert any(t in tags for t in ("ice", "frost", "snap", "crack", "crunch"))
    # Check deduplication
    assert len(tags) == len(set(tags))


def test_sanitize_foley_text():
    """Sanitizer must strip cinematography jargon and academic phrases."""
    raw = "camera push-in at t=2.0s macro view of freezing point depression on ice"
    cleaned = sanitize_foley_text(raw)
    assert "camera" not in cleaned
    assert "macro" not in cleaned
    assert "freezing point depression" not in cleaned
    assert "ice" in cleaned


def test_tactile_foley_stop_words_exclusion():
    """Stop words must not be included in semantic tags or fallback descriptions."""
    tags = get_tactile_sfx_tags("the connected component transfers visible energy to the other part", domain="mechanical")
    assert "the" not in tags
    assert "and" not in tags
    assert "visible" not in tags
    assert "state" not in tags
    assert "transfers" not in tags
    assert "foley" in tags
    assert "diegetic" in tags


def test_translate_glass_and_slosh_categories():
    """Glass shatter and liquid slosh must map to concrete tactile Foley."""
    glass_prompt = translate_to_tactile_foley("windshield glass shattering under impact", domain="incident")
    assert "glass shatter" in glass_prompt or "crystalline crash" in glass_prompt

    slosh_prompt = translate_to_tactile_foley("viscous stomach acid liquid slosh", domain="anatomical")
    assert "squelch" in slosh_prompt or "viscous liquid" in slosh_prompt or "acidic fizz" in slosh_prompt


def test_translate_hydraulic_hiss():
    """Hydraulic fluid and pinhole leak must map to high-pressure hydraulic hiss."""
    prompt = translate_to_tactile_foley(
        "hydraulic fluid under intense pressure spraying through pinhole leak",
        domain="mechanical",
    )
    assert "hydraulic fluid hiss" in prompt or "fluid jet spray" in prompt or "pinhole release" in prompt


def test_translate_rotary_drill_cavitation():
    """Rotary drilling and ultrasonic cavitation must map to rotary burr buzz."""
    prompt = translate_to_tactile_foley(
        "high-speed drilling with dental drill burr contact",
        domain="mechanical",
    )
    assert "drill buzz" in prompt or "rotary burr" in prompt or "cavitation hiss" in prompt


def test_translate_cartilage_strain_cavitation():
    """Joint cavitation and cartilage friction must map to cavitation pop / tendon strain."""
    prompt = translate_to_tactile_foley(
        "synovial joint pop and cartilage friction crepitus under tendon strain",
        domain="anatomical",
    )
    assert "joint cavitation pop" in prompt or "tendon strain" in prompt or "cartilage friction" in prompt


def test_translate_glass_crack_fissure():
    """Hairline glass crack and fissure must map to delicate stress ticking / crack ping."""
    prompt = translate_to_tactile_foley(
        "hairline crack and glass stress fissure propagating across surface",
        domain="mechanical",
    )
    assert "glass crack" in prompt or "micro-fracture snap" in prompt or "stress ticking" in prompt


def test_translate_micro_static_electricity():
    """Electrostatic charge and static crackle must map to crisp electrostatic snap."""
    prompt = translate_to_tactile_foley(
        "electrostatic charge buildup causing piezoelectric snap and static crackle",
        domain="mechanical",
    )
    assert "electrostatic snap" in prompt or "micro-static crackle" in prompt or "dielectric ionization" in prompt


def test_translate_rubber_friction_squeal():
    """Rubber friction and gasket drag must map to rubber squeal / gasket drag."""
    prompt = translate_to_tactile_foley(
        "vulcanized rubber friction scrub and gasket drag under torque",
        domain="mechanical",
    )
    assert "rubber squeal" in prompt or "gasket drag" in prompt or "friction scrub" in prompt


def test_expanded_academic_abstractions_sanitized():
    """Expanded scientific terms must be stripped by sanitize_foley_text."""
    raw = "piezoelectric effect and viscoelastic deformation causing shear stress failure"
    cleaned = sanitize_foley_text(raw)
    assert "piezoelectric effect" not in cleaned
    assert "viscoelastic deformation" not in cleaned
    assert "shear stress failure" not in cleaned


def test_get_tactile_sfx_tags_no_substring_false_positives():
    """Tags must not match substrings such as 'ice' in 'device'."""
    tags = get_tactile_sfx_tags("device casing inspection", domain="mechanical")
    assert "ice" not in tags
    assert "frost" not in tags
    assert "device" in tags
    assert "casing" in tags


def test_get_tactile_sfx_tags_deep_keyword_matching():
    """Tags must match keywords situated beyond the first 6 entries in category list."""
    tags = get_tactile_sfx_tags("acoustic rubber seal friction", domain="mechanical")
    assert "rubber" in tags
    assert "squeal" in tags
    assert "seal" in tags


def test_medical_and_physics_abstractions_sanitized():
    """Medical and physics jargon must be stripped from raw Foley input."""
    raw = "vasoconstriction and action potential causing photoelastic stress and intracellular fluid surge"
    cleaned = sanitize_foley_text(raw)
    assert "vasoconstriction" not in cleaned
    assert "action potential" not in cleaned
    assert "photoelastic stress" not in cleaned
    assert "intracellular fluid" not in cleaned


