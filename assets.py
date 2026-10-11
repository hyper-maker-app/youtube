"""Asset library: reusable character sheets, props and environments.

Stores asset metadata in assets/catalog.json and image files in assets/sheets/.
The BeatEngine reads the catalog when building the system prompt so the LLM can
reference existing assets instead of inventing new subjects every time.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import config


@dataclass
class AssetSheet:
    id: str                         # "young_man_01", "heart_organ"
    type: str                       # "character" | "prop" | "environment"
    description: str                # Verbatim physical description for LLM reuse
    tags: list[str] = field(default_factory=list)
    image_path: str = ""            # Relative to ASSETS_DIR, e.g. "sheets/young_man_01.png"
    aspect_ratio: str = ""          # "2:3", "1:1", "9:16"
    damage_states: list[str] = field(default_factory=list)
    created_at: str = ""
    usage_count: int = 0
    last_used: str = ""

    def __post_init__(self):
        if not self.aspect_ratio:
            self.aspect_ratio = config.SHEET_RATIOS.get(self.type, config.ASPECT_RATIO_STRING)
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def abs_image_path(self) -> Path:
        return config.ASSETS_DIR / self.image_path

    @property
    def has_image(self) -> bool:
        return bool(self.image_path) and self.abs_image_path.exists()


class AssetLibrary:
    """CRUD manager for the persistent asset catalog."""

    def __init__(self, catalog_path: Path | None = None):
        self.catalog_path = catalog_path or config.ASSET_CATALOG
        self._assets: dict[str, AssetSheet] = {}
        self._load()

    def _ensure_dirs(self) -> None:
        config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        config.ASSET_SHEETS_DIR.mkdir(parents=True, exist_ok=True)
        config.ASSET_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if self.catalog_path.exists():
            try:
                raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
                for entry in raw.get("assets", []):
                    sheet = AssetSheet(**entry)
                    self._assets[sheet.id] = sheet
            except (json.JSONDecodeError, TypeError):
                self._assets = {}

    def _save(self) -> None:
        self._ensure_dirs()
        data = {"assets": [asdict(s) for s in self._assets.values()]}
        self.catalog_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- CRUD -----------------------------------------------------------------

    def list_assets(
        self, type_filter: str | None = None, tags: list[str] | None = None
    ) -> list[AssetSheet]:
        result = list(self._assets.values())
        if type_filter:
            result = [a for a in result if a.type == type_filter]
        if tags:
            tag_set = {t.lower() for t in tags}
            result = [a for a in result if tag_set & {t.lower() for t in a.tags}]
        return result

    def get_asset(self, asset_id: str) -> AssetSheet | None:
        return self._assets.get(asset_id)

    def register_asset(self, sheet: AssetSheet) -> None:
        self._assets[sheet.id] = sheet
        self._save()

    def remove_asset(self, asset_id: str) -> bool:
        if asset_id in self._assets:
            del self._assets[asset_id]
            self._save()
            return True
        return False

    def increment_usage(self, asset_id: str) -> None:
        if asset_id in self._assets:
            self._assets[asset_id].usage_count += 1
            self._assets[asset_id].last_used = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save()

    # -- LLM helpers ----------------------------------------------------------

    def suggest_assets(self, topic: str | None = None) -> str:
        """Build a concise catalog summary for the LLM system prompt.

        Lists every registered asset with its id, type, description and tags so
        the model can reference existing sheets instead of defining new subjects.
        """
        assets = self.list_assets()
        if not assets:
            return "Asset library is empty. Define new subjects as needed."

        lines = ["Available assets in the library (reuse when appropriate):"]
        for a in assets:
            status = "✓ has image" if a.has_image else "⚠ no image yet"
            lines.append(
                f"  - {a.id} ({a.type}, {a.aspect_ratio}): {a.description} "
                f"[tags: {', '.join(a.tags)}] [{status}] [used {a.usage_count}x]"
            )
        return "\n".join(lines)

    def generate_sheet_prompt(self, asset: AssetSheet) -> str:
        """Create a Google Flow-ready prompt to generate this asset's reference sheet."""
        style = config.SHEET_STYLE_SUFFIX.get(asset.type, config.ZACK_STYLE)
        ratio = config.SHEET_RATIOS.get(asset.type, config.ASPECT_RATIO_STRING)

        prompt = f"{asset.description}. {style}"
        prompt += (
            "\n\nNo text, no caption, no watermark, no logo, no UI elements. "
            f"Aspect ratio: {ratio}."
        )

        # Save the prompt to disk for reference
        self._ensure_dirs()
        prompt_path = config.ASSET_PROMPTS_DIR / f"{asset.id}.txt"
        prompt_path.write_text(prompt + "\n", encoding="utf-8")

        return prompt

    def auto_register_from_shots(self, shots: list) -> list[AssetSheet]:
        """Extract new subjects from script shots and register them as assets.

        Only registers subjects that are NOT already in the catalog. Returns the
        list of newly registered sheets (the user will need to generate images
        for these in Google Flow).
        """
        new_sheets: list[AssetSheet] = []
        seen: set[str] = set()

        for shot in shots:
            sid = shot.subject_id if hasattr(shot, "subject_id") else shot.get("subject_id", "")
            if not sid or sid in self._assets or sid in seen:
                continue
            seen.add(sid)

            desc = (
                shot.subject_description
                if hasattr(shot, "subject_description")
                else shot.get("subject_description", "")
            )
            # Infer type from scale or description
            asset_type = self._infer_type(sid, desc)

            sheet = AssetSheet(
                id=sid,
                type=asset_type,
                description=desc,
                tags=self._infer_tags(sid, desc),
            )
            self.register_asset(sheet)
            self.generate_sheet_prompt(sheet)
            new_sheets.append(sheet)

        return new_sheets

    def _infer_type(self, sid: str, desc: str) -> str:
        desc_lower = (sid + " " + desc).lower()
        person_keywords = ["man", "woman", "boy", "girl", "child", "person", "human",
                           "character", "adam", "kadın", "çocuk", "insan"]
        env_keywords = ["room", "forest", "city", "sky", "space", "ocean", "field",
                        "oda", "orman", "şehir", "gökyüzü", "uzay", "okyanus"]
        if any(k in desc_lower for k in person_keywords):
            return "character"
        if any(k in desc_lower for k in env_keywords):
            return "environment"
        return "prop"

    def _infer_tags(self, sid: str, desc: str) -> list[str]:
        tags = []
        combined = (sid + " " + desc).lower()
        tag_keywords = {
            "human": ["man", "woman", "boy", "girl", "person", "human", "character"],
            "anatomy": ["heart", "brain", "cell", "organ", "muscle", "bone", "blood"],
            "space": ["sun", "moon", "earth", "star", "planet", "galaxy", "orbit"],
            "nature": ["tree", "ocean", "mountain", "river", "forest", "animal"],
            "object": ["phone", "car", "machine", "tool", "device", "building"],
        }
        for tag, keywords in tag_keywords.items():
            if any(k in combined for k in keywords):
                tags.append(tag)
        return tags or ["general"]
