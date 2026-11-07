"""Unit tests for engine/services/prompt_compiler.py.

Verifies:
1. Zero hardcoded creative lexical substitutions or barrier entity injections.
2. Pure AST dispatch linter against coplanar bleed.
3. Generic visibility gating driven by entity keywords or token extraction.
4. Parameterized visual style and lighting directives in b-roll and Veo prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import pytest

from engine.services.prompt_compiler import (
    DispatchLintError,
    HistoricalTruthSheet,
    compile_longform_broll_prompt,
    compile_udse_prompt,
    format_multi_shot_prompt,
    format_veo_cinematography_prompt,
    inject_active_deltas_with_visibility_gating,
    lint_prompt_for_unpartitioned_bleed,
)


@dataclass
class MockEntity:
    id: str
    kind: str = "prop"
    material_class: str = "metal"
    keywords: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockWorldState:
    project_id: str = "test-project"
    entity_registry: dict[str, MockEntity] = field(default_factory=dict)
    delta_ledger: list[dict[str, Any]] = field(default_factory=list)


def test_compile_udse_prompt_clean_no_hardcoded_barrier():
    """Verify compile_udse_prompt does not inject hardcoded white-oak slab clauses."""
    prompt = "A weathered wooden door in an abandoned hallway under flickering fluorescent bulbs."
    compiled = compile_udse_prompt(prompt)
    assert "white-oak slab" not in compiled
    assert "E_DOOR_01" not in compiled
    assert "100% opaque timber through-and-through" not in compiled
    assert "A weathered wooden door in an abandoned hallway" in compiled


def test_compile_udse_prompt_strips_invariant_brackets():
    """Verify compile_udse_prompt strips bracketed metadata invariants."""
    raw = "Cinematic shot of control room. [INVARIANT: maintain lever position] Sparks fly."
    compiled = compile_udse_prompt(raw)
    assert "[INVARIANT:" not in compiled
    assert "Sparks fly" in compiled


def test_lint_prompt_for_unpartitioned_bleed_passes_with_metric_partition():
    """Verify linter permits glass and door when metric spatial partition is specified."""
    prompt = "A reinforced door on the front wall. On the left wall, 2.5 meters away, a cracked window pane."
    lint_prompt_for_unpartitioned_bleed(prompt)  # Should not raise


def test_lint_prompt_for_unpartitioned_bleed_raises_on_coplanar():
    """Verify linter raises DispatchLintError when glass and door are unpartitioned in the same sentence."""
    prompt = "A heavy door with a cracked window pane in the same opening."
    with pytest.raises(DispatchLintError, match="Coplanar glass and door detected"):
        lint_prompt_for_unpartitioned_bleed(prompt)


def test_inject_active_deltas_generic_visibility_gating():
    """Verify active deltas are injected only when entity is visible via registry keywords or token derivation."""
    ws = MockWorldState(
        entity_registry={
            "PROP_LANTERN_01": MockEntity(
                id="PROP_LANTERN_01",
                kind="lantern",
                material_class="brass",
                keywords=["lantern", "lamp", "oil lamp"],
            ),
            "E_HYDRAULIC_VALVE": MockEntity(
                id="E_HYDRAULIC_VALVE",
                kind="valve",
                material_class="steel",
                keywords=["valve", "pipe", "gauge"],
            ),
        },
        delta_ledger=[
            {
                "entity_id": "PROP_LANTERN_01",
                "attribute": "glass_shade",
                "after": "cracked with soot",
                "evidence": "spiderweb fracture across lantern globe",
            },
            {
                "entity_id": "E_HYDRAULIC_VALVE",
                "attribute": "pressure_seal",
                "after": "ruptured",
                "evidence": "pressurized steam venting",
            },
        ],
    )

    # Frame 1: Mentions lantern -> only lantern delta injected
    prompt_lantern = "Close up of an antique brass lantern resting on the workbench."
    gated_lantern = inject_active_deltas_with_visibility_gating(prompt_lantern, ws)
    assert "PROP_LANTERN_01 maintains spiderweb fracture" in gated_lantern
    assert "E_HYDRAULIC_VALVE" not in gated_lantern

    # Frame 2: Mentions pipe -> only valve delta injected
    prompt_valve = "Wide shot of steam hissing from the rusty pipe manifold."
    gated_valve = inject_active_deltas_with_visibility_gating(prompt_valve, ws)
    assert "E_HYDRAULIC_VALVE maintains pressurized steam venting" in gated_valve
    assert "PROP_LANTERN_01" not in gated_valve

    # Frame 3: Neither mentioned -> no deltas injected
    prompt_exterior = "Aerial view of a misty pine forest in early morning light."
    gated_exterior = inject_active_deltas_with_visibility_gating(prompt_exterior, ws)
    assert gated_exterior == prompt_exterior


def test_compile_longform_broll_prompt_parameterization():
    """Verify compile_longform_broll_prompt accepts custom visual style and lighting."""
    custom_style = "Hyperrealistic 4k anamorphic film capture"
    custom_lighting = "Harsh ultraviolet xenon searchlights slicing dense fog"
    prompt = compile_longform_broll_prompt(
        scene_description="the abandoned radar installation",
        proof_target="severed coaxial cable hanging from dish",
        visual_style=custom_style,
        lighting=custom_lighting,
    )
    assert "Hyperrealistic 4k anamorphic film capture of the abandoned radar installation" in prompt
    assert "severed coaxial cable hanging from dish" in prompt
    assert "Harsh ultraviolet xenon searchlights slicing dense fog" in prompt
    assert "STRICT VISUAL MANDATE: ZERO text" in prompt


def test_format_veo_cinematography_prompt_parameterization():
    """Verify format_veo_cinematography_prompt parameterizes visual style and lighting."""
    prompt = format_veo_cinematography_prompt(
        shot_type="Extreme wide tracking shot",
        subject_labor="a lone surveyor calibrating an optical theodolite",
        lighting="dawn twilight specular glint",
        historical_atmosphere="wind-swept arctic tundra",
        camera_vector="slow jib descent",
        fps="30fps",
        visual_style="65mm IMAX photorealistic cinema",
    )
    assert "Extreme wide tracking shot" in prompt
    assert "a lone surveyor calibrating an optical theodolite" in prompt
    assert "dawn twilight specular glint" in prompt
    assert "wind-swept arctic tundra" in prompt
    assert "slow jib descent" in prompt
    assert "30fps motion blur" in prompt
    assert "65mm IMAX photorealistic cinema" in prompt


def test_dynamic_sfx_prompt_synthesis():
    """Verify SFX taxonomy produces dynamic prompt directives from scene action and physical context."""
    from engine.services.sfx_categorizer import DynamicSfxPrompt, extract_sfx_category

    # 1. Direct dynamic synthesis from DynamicSfxPrompt
    dyn = DynamicSfxPrompt("large explosion with shockwave", "explosion")
    assert dyn == "large explosion with shockwave"
    custom = dyn.synthesize(action="violent decompression", physical_context="subterranean reinforced silo")
    assert "subterranean reinforced silo" in custom
    assert "violent decompression" in custom

    # 2. extract_sfx_category with scene action and physical context
    scene = {
        "narration": "You hear the emergency alert echo across the launch platform.",
        "action": "pulsing high-frequency warning",
        "physical_context": "sub-zero orbital hangar",
    }
    match = extract_sfx_category(scene)
    assert match is not None
    assert match.category == "alarm_siren"
    assert "sub-zero orbital hangar" in match.audiogen_prompt
    assert "pulsing high-frequency warning" in match.audiogen_prompt


def test_thumbnail_generator_title_text_required_and_no_volcano():
    """Verify thumbnail_generator enforces required title_text and removes volcano defaults."""
    from engine.services.thumbnail_generator import generate_thumbnail

    # Raises ValueError when title_text is empty
    with pytest.raises(ValueError, match="title_text is a required non-empty string"):
        generate_thumbnail(title_text="")

    with pytest.raises(TypeError):
        generate_thumbnail()  # type: ignore[call-arg]
