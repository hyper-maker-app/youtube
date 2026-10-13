"""Unit tests for services/thumbnail_engine.py (Thumbnail & Click-Hook Engine)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from services.thumbnail_engine import (
    CTRHookLibrary,
    SafeZoneBounds,
    ThumbnailPromptCompiler,
    ThumbnailSpec,
)


def test_thumbnail_spec_16_9_format():
    compiler = ThumbnailPromptCompiler()
    spec = compiler.compile(topic="The Lost Labyrinth of Hawara", format="16:9")

    assert spec.format == "16:9"
    assert spec.era == "egyptian"
    assert "gold" in spec.color_palette_lock.lower()
    assert spec.contrast_lut in ("warm_golden", "drama_high_contrast")
    assert len(spec.candidates) == 3
    assert all("16:9" in p for p in spec.candidates)
    assert all(ThumbnailPromptCompiler.ZERO_TEXT_SHIELD in p for p in spec.candidates)
    assert spec.safe_zone.format == "16:9"
    assert spec.safe_zone.text_x_pct < 0.20  # Left aligned
    assert spec.safe_zone.text_w_pct > 0.40


def test_thumbnail_spec_9_16_format():
    compiler = ThumbnailPromptCompiler()
    spec = compiler.compile(topic="Gallipoli 1915 Nusret Minefield", format="9:16")

    assert spec.format == "9:16"
    assert spec.era == "world_war_i"
    assert "steel" in spec.color_palette_lock.lower() or "turquoise" in spec.color_palette_lock.lower()
    assert len(spec.candidates) == 3
    assert all("9:16" in p for p in spec.candidates)
    assert spec.safe_zone.format == "9:16"
    # In Shorts, text must avoid right ~20% buttons and bottom ~25% UI
    assert spec.safe_zone.text_w_pct <= 0.80
    assert spec.safe_zone.text_y_pct <= 0.25  # top third


def test_curiosity_hook_max_6_words():
    compiler = ThumbnailPromptCompiler()
    for era in ("world_war_i", "neolithic", "egyptian", "greco_roman", "ottoman", "modern_disaster", "default"):
        hook = CTRHookLibrary.get_hook(era, "Sample Test Topic")
        words = hook.strip().split()
        assert 1 <= len(words) <= 6, f"Hook '{hook}' for era {era} exceeded 6 words"


def test_safe_zone_pixel_conversion():
    sz = SafeZoneBounds(
        format="16:9",
        text_x_pct=0.10,
        text_y_pct=0.15,
        text_w_pct=0.50,
        text_h_pct=0.60,
    )
    box = sz.to_pixel_box(width=1920, height=1080)
    assert box["x"] == 192
    assert box["y"] == 162
    assert box["w"] == 960
    assert box["h"] == 648


def test_compile_for_both_formats():
    compiler = ThumbnailPromptCompiler()
    specs = compiler.compile_for_both_formats(topic="Gobekli Tepe Secrets", era="neolithic")

    assert "9:16" in specs
    assert "16:9" in specs
    assert specs["9:16"].format == "9:16"
    assert specs["16:9"].format == "16:9"
    assert specs["9:16"].era == "neolithic"
    assert specs["16:9"].era == "neolithic"


def test_dry_run_fixture_syntax():
    fix_16_9 = ThumbnailPromptCompiler.dry_run_fixture("16:9")
    fix_9_16 = ThumbnailPromptCompiler.dry_run_fixture("9:16")

    assert "1920x1080" in fix_16_9
    assert "1080x1920" in fix_9_16
    assert "color=" in fix_16_9
    assert "color=" in fix_9_16


def test_custom_focal_subject_and_hook():
    compiler = ThumbnailPromptCompiler()
    spec = compiler.compile(
        topic="Pompeii Volcanic Blast",
        curiosity_hook="How They Died",
        focal_subject="Petrified Roman Soldier",
        format="16:9",
    )
    assert spec.curiosity_hook_text == "How They Died"
    assert spec.focal_subject == "Petrified Roman Soldier"
    assert all("Petrified Roman Soldier" in c for c in spec.candidates)


def test_thumbnail_spec_frozen_immutability():
    compiler = ThumbnailPromptCompiler()
    spec = compiler.compile(topic="Chernobyl Reactor 4", format="16:9")
    with pytest.raises(Exception):
        spec.topic = "Changed Topic"  # type: ignore


def test_ast_cleanliness_no_network_imports():
    """Verify services/thumbnail_engine.py contains zero network or transport imports."""
    source_path = Path(__file__).resolve().parent.parent / "services" / "thumbnail_engine.py"
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
