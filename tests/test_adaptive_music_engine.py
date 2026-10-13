"""Unit tests for services/adaptive_music_engine.py (Engine 4: Adaptive Music & Braam)."""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest
from services.adaptive_music_engine import (
    BRAAM_HP_HZ,
    VO_PROTECTION_DIP_DB,
    AdaptiveMusicEngine,
    AdaptiveMusicPlan,
    BraamEvent,
    DramaticTensionMap,
)


def test_dramatic_tension_map_from_beats():
    beats = [
        {"phase": "arrival_hook", "name": "Hook"},
        {"phase": "context_immersion", "name": "Context"},
        {"phase": "rising_investigation", "name": "Investigate 1"},
        {"phase": "rising_investigation", "name": "Investigate 2"},
        {"phase": "turning_point", "name": "Revelation"},
        {"phase": "legacy_verdict", "name": "Verdict"},
    ]
    durations = [8.0, 6.0, 8.0, 6.0, 8.0, 8.0]
    t_map = DramaticTensionMap.from_beats(beats, durations)

    assert len(t_map.blocks) == 6
    assert t_map.total_duration == 44.0
    # Phase mappings
    assert t_map.blocks[0].tension_level == 1  # Hook -> RISING
    assert t_map.blocks[1].tension_level == 0  # Context -> CALM
    assert t_map.blocks[4].tension_level == 3  # Turning Point -> BRAAM
    assert t_map.blocks[4].braam_type == "sub_drop"
    assert t_map.blocks[5].tension_level == 4  # Legacy -> RESOLUTION


def test_adaptive_music_plan_filtergraph():
    beats = [
        {"phase": "arrival_hook"},
        {"phase": "turning_point"},
    ]
    t_map = DramaticTensionMap.from_beats(beats, [4.0, 4.0])
    plan = AdaptiveMusicPlan(t_map)
    graph = plan.build_filtergraph()

    # Verify key architectural invariants:
    assert "sine=frequency=40" in graph  # Sub-bass foundation
    assert "sine=frequency=42" in graph  # Braam low component
    assert f"highpass=f={BRAAM_HP_HZ}" in graph  # Sub-bass safety filter
    assert f"g={VO_PROTECTION_DIP_DB}" in graph  # VO protection pocket dip
    assert "stereotools=" in graph  # Stereo side-diffusion
    assert "volume=0.19" in graph  # Broadcast staging volume (-14.4 dBFS)


def test_adaptive_music_plan_without_braam():
    beats = [
        {"phase": "context_immersion"},
        {"phase": "rising_investigation"},
    ]
    t_map = DramaticTensionMap.from_beats(beats, [4.0, 4.0])
    plan = AdaptiveMusicPlan(t_map)
    graph = plan.build_filtergraph()

    assert "volume=0.19" in graph
    assert "sine=frequency=40" in graph


def test_write_script_file():
    beats = [{"phase": "turning_point"}]
    t_map = DramaticTensionMap.from_beats(beats, [4.0])
    plan = AdaptiveMusicPlan(t_map)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        out_path = Path(tf.name)

    try:
        written = plan.write_script_file(out_path)
        assert written.is_file()
        content = written.read_text(encoding="utf-8")
        assert "volume=0.19" in content
    finally:
        if out_path.exists():
            out_path.unlink()


def test_adaptive_music_engine_generates_wav():
    beats = [
        {"phase": "arrival_hook"},
        {"phase": "turning_point"},
    ]
    t_map = DramaticTensionMap.from_beats(beats, [2.0, 2.0])
    engine = AdaptiveMusicEngine()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        out_wav = Path(tf.name)

    try:
        res = engine.generate(t_map, duration=4.0, out_path=out_wav)
        assert res.is_file()
        assert res.stat().st_size > 1000  # Non-empty 48kHz WAV
    finally:
        if out_wav.exists():
            out_wav.unlink()


def test_ast_cleanliness_services_layer():
    """Verify services/adaptive_music_engine.py contains zero network or provider imports."""
    source_path = Path(__file__).resolve().parent.parent / "services" / "adaptive_music_engine.py"
    tree = ast.parse(source_path.read_text("utf-8"), filename=str(source_path))

    forbidden_modules = {"httpx", "requests", "urllib", "aiohttp", "websockets", "google"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                assert mod not in forbidden_modules, f"Forbidden import: {mod}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                assert mod not in forbidden_modules, f"Forbidden from-import: {mod}"
