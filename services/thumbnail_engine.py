"""Thumbnail & Click-Hook Engine for 16:9 Longform and 9:16 Shorts.

Compiles high-CTR thumbnail specifications adhering to format-specific
YouTube UI safe zones, color grading LUT profiles, era palettes, and
typographic curiosity hooks.

Strictly AST-clean: Zero network calls, zero provider imports (ADR-065).
Text is NEVER rendered into AI image prompts; text overlays are specified
strictly for post-generation FFmpeg / ASS compositing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from services.character import detect_era


@dataclass(frozen=True)
class SafeZoneBounds:
    """Format-specific YouTube UI safe coordinates to prevent overlay clashes.

    - 9:16 Shorts: Avoids right edge (~20% Like/Share buttons) and bottom (~25% avatar/title).
    - 16:9 Longform: Avoids bottom-right corner (~120x40px duration timestamp).
    """

    format: str  # "9:16" | "16:9"
    text_x_pct: float  # Left margin percent (0.0 - 1.0)
    text_y_pct: float  # Top margin percent (0.0 - 1.0)
    text_w_pct: float  # Text box width percent
    text_h_pct: float  # Text box height percent

    def to_pixel_box(self, width: int, height: int) -> dict[str, int]:
        """Convert relative percentages to absolute pixel bounds."""
        return {
            "x": int(self.text_x_pct * width),
            "y": int(self.text_y_pct * height),
            "w": int(self.text_w_pct * width),
            "h": int(self.text_h_pct * height),
        }


@dataclass(frozen=True)
class ThumbnailSpec:
    """Immutable, validated specification for an autonomous thumbnail generation run."""

    topic: str
    era: str
    format: str  # "9:16" | "16:9"
    curiosity_hook_text: str  # Max 6 words, high-CTR hook
    focal_subject: str
    color_palette_lock: str
    contrast_lut: str  # e.g. "drama_high_contrast", "warm_golden", "cold_blue_steel"
    candidates: tuple[str, ...]  # 3 distinct candidate prompts (zero model text)
    ass_overlay_spec: dict[str, Any]  # Post-production overlay metadata
    safe_zone: SafeZoneBounds
    zero_text_shield: str


class CTRHookLibrary:
    """Curated curiosity hooks organized by historical/thematic era."""

    HOOKS_BY_ERA: dict[str, list[str]] = {
        "world_war_i": [
            "What Really Sank It?",
            "The Forgotten War Secret",
            "Hidden Under The Water",
            "How One Shell Changed All",
            "The Miracle At Erenköy",
        ],
        "neolithic": [
            "Before History Began",
            "Buried On Purpose?",
            "12,000 Years Untouched",
            "Who Actually Built This?",
            "Older Than Stonehenge",
        ],
        "egyptian": [
            "Lost Beneath The Sand",
            "The Chamber Nobody Found",
            "Forbidden Pharaonic Tomb",
            "Why Was It Sealed?",
            "The Labyrinth Was Real",
        ],
        "greco_roman": [
            "Frozen In Volcanic Ash",
            "The Secret Roman Chamber",
            "Uncovered After 2000 Years",
            "They Never Escaped",
            "Hidden Under The Villa",
        ],
        "ottoman": [
            "Secret Beneath The Palace",
            "The Cistern Nobody Knew",
            "Architect's Lost Chamber",
            "Hidden Below Istanbul",
            "The Forgotten Subterranean Maze",
        ],
        "modern_disaster": [
            "What Happened Inside?",
            "Seconds Before Meltdown",
            "The Alarm They Ignored",
            "Trapped In The Deep",
            "The True Cause Revealed",
        ],
        "modern_space": [
            "Lost In Deep Orbit",
            "The Signal From Space",
            "What They Found Outside",
            "400,000 Kilometers Away",
            "The Astronaut's Warning",
        ],
        "default": [
            "The Forbidden Discovery",
            "What Was Hidden Here?",
            "Archaeologists Stunned",
            "The Secret Never Told",
            "Nobody Was Supposed To See",
        ],
    }

    @classmethod
    def get_hook(cls, era: str, topic: str) -> str:
        """Select or generate a curiosity hook guaranteed to be <= 6 words."""
        era_lower = str(era or "default").casefold()
        candidates = cls.HOOKS_BY_ERA.get(era_lower) or cls.HOOKS_BY_ERA["default"]
        # Deterministic choice based on topic hash
        idx = abs(hash(topic)) % len(candidates)
        hook = candidates[idx]
        words = hook.strip().split()
        if len(words) > 6:
            hook = " ".join(words[:6])
        return hook


class ThumbnailPromptCompiler:
    """Compiles format-aware, AST-clean thumbnail image generation prompts."""

    ZERO_TEXT_SHIELD: str = (
        "STRICT VISUAL MANDATE: ZERO text, ZERO typography, ZERO date stamps, "
        "ZERO year numbers written on image, ZERO name plaques, ZERO title banners, "
        "ZERO caption boxes, ZERO subtitles, ZERO HUD overlay, ZERO fake watermarks."
    )

    _COLOR_PALETTES: dict[str, str] = {
        "world_war_i": "deep ocean turquoise, burnt gunmetal steel, oxidized copper, muted olive khaki",
        "neolithic": "ancient ochre, raw limestone beige, deep subterranean shadow, warm golden dust motes",
        "egyptian": "radiant desert gold, deep lapis lazuli shadow, weathered sandstone amber, rich linen white",
        "greco_roman": "pompeian volcanic red, terracotta earthenware, cool marble grey, deep obsidian black",
        "ottoman": "imperial crimson, burnished brass, küfeki stone ivory, deep subterranean aqueduct blue",
        "modern_disaster": "industrial neon amber, cold concrete charcoal, toxic steel green, dark emergency shadow",
        "modern_space": "lunar titanium silver, deep vacuum void black, gold kapton reflection, crisp Earth blue",
        "default": "high-contrast cinematic chiaroscuro, intense focal amber, deep shadow obsidian",
    }

    _CONTRAST_LUTS: dict[str, str] = {
        "world_war_i": "cold_blue_steel",
        "neolithic": "warm_golden",
        "egyptian": "warm_golden",
        "greco_roman": "drama_high_contrast",
        "ottoman": "drama_high_contrast",
        "modern_disaster": "cold_blue_steel",
        "modern_space": "drama_high_contrast",
        "default": "drama_high_contrast",
    }

    def _build_safe_zone(self, format: str) -> SafeZoneBounds:
        fmt = str(format or "16:9").strip()
        if fmt == "9:16":
            return SafeZoneBounds(
                format="9:16",
                text_x_pct=0.10,
                text_y_pct=0.12,
                text_w_pct=0.75,
                text_h_pct=0.35,
            )
        return SafeZoneBounds(
            format="16:9",
            text_x_pct=0.06,
            text_y_pct=0.15,
            text_w_pct=0.55,
            text_h_pct=0.65,
        )

    def _select_color_palette(self, era: str) -> str:
        return self._COLOR_PALETTES.get(str(era).casefold()) or self._COLOR_PALETTES["default"]

    def _select_contrast_lut(self, era: str) -> str:
        return self._CONTRAST_LUTS.get(str(era).casefold()) or self._CONTRAST_LUTS["default"]

    def _build_ass_overlay(self, hook_text: str, safe_zone: SafeZoneBounds) -> dict[str, Any]:
        """Construct ASS / FFmpeg drawtext compositing metadata."""
        is_short = safe_zone.format == "9:16"
        return {
            "text": hook_text,
            "fontname": "Montserrat ExtraBold, Arial Black, sans-serif",
            "fontsize": 64 if is_short else 76,
            "primary_color": "&H00FFFFFF",  # Pure white
            "outline_color": "&H00000000",  # Pure black outline
            "outline_width": 5,
            "shadow_offset": 4,
            "alignment": 8 if is_short else 5,  # Top-center for Shorts, Middle-left for Longform
            "margin_l": int(safe_zone.text_x_pct * (1080 if is_short else 1920)),
            "margin_t": int(safe_zone.text_y_pct * (1920 if is_short else 1080)),
        }

    def compile(
        self,
        topic: str,
        era: str | None = None,
        format: str = "16:9",
        curiosity_hook: str | None = None,
        focal_subject: str | None = None,
    ) -> ThumbnailSpec:
        """Compile an authoritative ThumbnailSpec for a topic and format."""
        resolved_era = era or detect_era(topic)
        safe_zone = self._build_safe_zone(format)
        hook = curiosity_hook or CTRHookLibrary.get_hook(resolved_era, topic)
        palette = self._select_color_palette(resolved_era)
        lut = self._select_contrast_lut(resolved_era)

        subject = focal_subject or re.sub(r"[^\w\s-]", "", topic).strip() or "historical anomaly"
        aspect_ratio_tag = "16:9 widescreen cinematic frame" if safe_zone.format == "16:9" else "9:16 vertical fullscreen frame"

        # Construct 3 distinct high-CTR visual prompts
        # Candidate 1: Epic discovery / wide reveal angle
        p1 = (
            f"Epic cinematic high-CTR documentary thumbnail of {subject}, {aspect_ratio_tag}. "
            f"Focal hero discovery with dramatic volumetric rim lighting, intense depth of field, "
            f"hyper-detailed textures in {palette}. Powerful visual curiosity, dynamic diagonal composition. "
            f"{self.ZERO_TEXT_SHIELD}"
        )

        # Candidate 2: Extreme close-up / tactile relic or mechanism
        p2 = (
            f"Extreme cinematic macro close-up documentary thumbnail showing key forensic evidence of {subject}, {aspect_ratio_tag}. "
            f"Chiaroscuro lighting, razor-sharp tactile focal point, glowing ambient shadows in {palette}. "
            f"Intense mystery, cinematic 35mm film grain, 8k resolution. "
            f"{self.ZERO_TEXT_SHIELD}"
        )

        # Candidate 3: Atmospheric low-angle / human scale perspective
        p3 = (
            f"Low-angle atmospheric documentary thumbnail capturing monumental scale of {subject}, {aspect_ratio_tag}. "
            f"Strong volumetric light rays cutting through ancient dust, rich contrast {lut} profile in {palette}. "
            f"Shock and awe visual hook, award-winning cinematography. "
            f"{self.ZERO_TEXT_SHIELD}"
        )

        ass_spec = self._build_ass_overlay(hook, safe_zone)

        return ThumbnailSpec(
            topic=topic,
            era=resolved_era,
            format=safe_zone.format,
            curiosity_hook_text=hook,
            focal_subject=subject,
            color_palette_lock=palette,
            contrast_lut=lut,
            candidates=(p1, p2, p3),
            ass_overlay_spec=ass_spec,
            safe_zone=safe_zone,
            zero_text_shield=self.ZERO_TEXT_SHIELD,
        )

    def compile_for_both_formats(
        self, topic: str, era: str | None = None
    ) -> dict[str, ThumbnailSpec]:
        """Compile both 9:16 (Shorts) and 16:9 (Longform) thumbnail specs."""
        return {
            "9:16": self.compile(topic, era=era, format="9:16"),
            "16:9": self.compile(topic, era=era, format="16:9"),
        }

    @staticmethod
    def dry_run_fixture(format: str = "16:9") -> str:
        """Return an FFmpeg lavfi filter string for zero-cost dry-run fixture generation."""
        dims = "1080x1920" if format == "9:16" else "1920x1080"
        return f"color=c=0x0a1128:s={dims}:d=1"
