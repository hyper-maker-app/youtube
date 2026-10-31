"""Dynamic Skill Loader & Directive Assembler.

Scans, parses, and injects live operational directives from .grok/skills/ into the
screenplay generation and production pipeline, ensuring that all 71 repository skills
act as an active, living cognitive layer.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _ROOT / ".grok" / "skills"


class SkillLoader:
    """Diskteki .grok/skills/ klasörünü dinamik tarayan ve üretim hattına bağlayan motor."""

    def __init__(self, skills_dir: Path | str | None = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else _SKILLS_DIR
        self._cache: dict[str, dict[str, str]] = {}
        self._index_all_skills()

    def _index_all_skills(self) -> None:
        """Scan skills directory and cache metadata."""
        if not self.skills_dir.is_dir():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                name = skill_dir.name
                desc = self._extract_frontmatter_field(content, "description")
                instructions = self._extract_body(content)
                self._cache[name] = {
                    "name": name,
                    "description": desc,
                    "instructions": instructions,
                    "path": str(skill_md),
                }
            except Exception as exc:
                logger.debug("Failed indexing skill %s: %s", skill_dir.name, exc)

    @staticmethod
    def _extract_frontmatter_field(content: str, field: str) -> str:
        """Extract a single field from YAML frontmatter."""
        pattern = rf"^{field}:\s*[\"']?([^\r\n\"']+)[\"']?"
        match = re.search(pattern, content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_body(content: str) -> str:
        """Strip YAML frontmatter and return operational markdown instructions."""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content.strip()

    def get_skill(self, slug: str) -> dict[str, str] | None:
        """Return indexed skill details by slug."""
        return self._cache.get(slug)

    def list_skills(self) -> list[dict[str, str]]:
        """List all indexed skills."""
        return list(self._cache.values())

    def load_skill_instructions(self, slug: str, max_chars: int = 3500) -> str:
        """Load, clean, and format skill instructions for prompt injection."""
        skill = self._cache.get(slug)
        if not skill:
            return ""
        instr = skill.get("instructions", "")

        lines = []
        skip_section = False
        skip_block = False

        for line in instr.splitlines():
            stripped = line.strip()

            # Skip code blocks like yaml/toml
            if stripped.startswith("```"):
                skip_block = not skip_block
                continue
            if skip_block:
                continue

            # Skip internal agent routing sections
            if stripped.startswith("## Model Layer") or stripped.startswith("## When to Activate"):
                skip_section = True
                continue
            elif stripped.startswith("## ") and skip_section:
                skip_section = False

            if skip_section:
                continue

            # Skip boilerplate metadata
            if stripped.startswith((
                "---",
                "name:",
                "description:",
                "> [!NOTE]",
                "License:",
                "Version legend",
                "Canonical Source:",
                "**Registry:**",
                "**Stack default:**",
                "**Role Card:**",
                "**Legacy fork:**",
                "**Handoff language",
                "Begin: **",
            )):
                continue

            # Skip table header/rows if it's model layer
            if stripped.startswith("|") and ("Preferred model" in stripped or "Task type" in stripped or "grok-4" in stripped):
                continue

            lines.append(line)

        cleaned = "\n".join(lines).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned[:max_chars].strip() if max_chars else cleaned.strip()

    def assemble_production_directives(self, genre: str = "catastrophe") -> dict[str, str]:
        """Synthesize directives across 6 key production departments."""
        genre_clean = genre.lower().strip()
        director_slug = f"{genre_clean}-director"
        if director_slug not in self._cache:
            director_slug = "catastrophe-director" if "catastrophe" in self._cache else "studio-director"

        return {
            "director": self.load_skill_instructions(director_slug, max_chars=8500),
            "retention": self.load_skill_instructions("viral-retention-director", max_chars=4000),
            "cinematography": self.load_skill_instructions("director-of-photography", max_chars=3500),
            "foley": self.load_skill_instructions("foley-sound-design-specialist", max_chars=3000),
            "vfx": self.load_skill_instructions("vfx-sfx-supervisor", max_chars=3000),
            "continuity": self.load_skill_instructions("continuity-consistency-guardian", max_chars=3000),
        }

    def build_unified_system_prompt(
        self,
        title: str,
        genre: str,
        duration: int,
        aspect: str = "16:9",
    ) -> str:
        """Assemble live disk skills into a single authoritative production directive.

        Pure Engine Invariant: No creative, directorial, or negative prompt text
        is hardcoded in this Python engine. All knowledge and constraints are loaded
        directly from .grok/skills/*.md.
        """
        directives = self.assemble_production_directives(genre)
        target_scene_count = max(5, round(duration / 7.89))

        sections = [
            f"You are the Multi-Agent Autonomous Studio Director for the high-end production '{title}'.",
            f"Target Duration: {duration} seconds | Genre: {genre.capitalize()} | Aspect Ratio: {aspect}.",
            f"Scene Target: Exactly {target_scene_count} tightly connected scenes (dynamic block durations from [4.0, 6.0, 8.0, 10.0] seconds).",
            "",
            "OPERATIONAL DIRECTIVES (LOADED LIVE FROM DISK SKILLS):",
            "Follow all instructions, negative guardrails, narrative scales, and standards loaded from .grok/skills/:",
            "",
            "=== [1. DIRECTORIAL & NARRATIVE ARCHITECTURE] ===",
            directives["director"],
            "",
            "=== [2. VIRAL RETENTION & ASPECT-AWARE SMART ENDINGS (.grok/skills/viral-retention-director)] ===",
            directives.get("retention", ""),
            "",
            "=== [3. CINEMATOGRAPHY & LIGHTING STANDARDS (.grok/skills/director-of-photography)] ===",
            directives["cinematography"],
            "",
            "=== [4. SIMULATION & VFX FIDELITY (.grok/skills/vfx-sfx-supervisor)] ===",
            directives["vfx"],
            "",
            "=== [5. DUAL-STAGE SFX & FOLEY ACCENTS (.grok/skills/foley-sound-design-specialist)] ===",
            directives["foley"],
            "",
            "=== [6. BOUNDARY QA & VISUAL CONTINUITY (.grok/skills/continuity-consistency-guardian)] ===",
            directives["continuity"],
        ]
        return "\n".join(sections)


_DEFAULT_LOADER: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    """Return singleton SkillLoader instance."""
    global _DEFAULT_LOADER
    if _DEFAULT_LOADER is None:
        _DEFAULT_LOADER = SkillLoader()
    return _DEFAULT_LOADER


def load_genre_skills(genre: str) -> dict[str, str]:
    """Helper to get genre-tailored production directives."""
    return get_skill_loader().assemble_production_directives(genre)
