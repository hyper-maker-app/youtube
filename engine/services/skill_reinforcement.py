"""Skill Reinforcement Engine (Dynamic Closed-Loop Adversarial Feedback & File Health Guard).

Takes structured defects and rules learned from Grok and Gemini LLM judges,
validates and maps them to active .grok/skills/<skill>/SKILL.md files, and safely
reinforces the skill guidelines while enforcing:
1. AGENTS.md Constitution Invariant: Keep SKILL.md concise (< 500 lines).
2. Semantic & Lexical Deduplication: Prevent redundant/repeated directives.
3. SkillResolver Fallback: Robust slug resolution across 64 project skills.
4. Hot-Reload: Instantly invalidates and refreshes SkillLoader memory cache.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

from engine.services.skill_loader import get_skill_loader

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _ROOT / ".grok" / "skills"

_CATEGORY_FALLBACK_MAP = {
    "camera": "director-of-photography",
    "lens": "director-of-photography",
    "lighting": "director-of-photography",
    "cinematography": "director-of-photography",
    "physics": "catastrophe-director",
    "thermodynamics": "catastrophe-director",
    "science": "catastrophe-director",
    "catastrophe": "catastrophe-director",
    "atmosphere": "catastrophe-director",
    "sound": "foley-sound-design-specialist",
    "sfx": "foley-sound-design-specialist",
    "foley": "foley-sound-design-specialist",
    "music": "sonic-architect-native-audio-virtuoso",
    "prompt": "imagine-prompt-master",
    "veo": "imagine-prompt-master",
    "visual_safety": "imagine-prompt-master",
    "retention": "viral-retention-director",
    "pacing": "narrative-arc-pacing-strategist",
    "pov": "viral-retention-director",
    "cta": "viral-retention-director",
    "acting": "performance-emotion-director",
    "emotion": "performance-emotion-director",
    "continuity": "continuity-consistency-guardian",
    "color": "post-production-color-grading-supervisor",
}


class SkillResolver:
    """Validates and resolves skill slugs against project .grok/skills/ repository."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or _SKILLS_DIR

    def resolve(self, candidate_slug: str | None, category: str = "", issue_text: str = "") -> str:
        """Resolve a candidate skill slug to a guaranteed existing skill directory."""
        if candidate_slug:
            clean_slug = candidate_slug.strip().lower()
            if (self.skills_dir / clean_slug / "SKILL.md").is_file():
                return clean_slug

        # Fallback by category
        cat_lower = category.lower().strip()
        for key, target in _CATEGORY_FALLBACK_MAP.items():
            if key in cat_lower:
                if (self.skills_dir / target / "SKILL.md").is_file():
                    return target

        # Fallback by keywords in issue text
        text_lower = issue_text.lower()
        for key, target in _CATEGORY_FALLBACK_MAP.items():
            if key in text_lower:
                if (self.skills_dir / target / "SKILL.md").is_file():
                    return target

        # Ultimate fallback
        if (self.skills_dir / "catastrophe-director" / "SKILL.md").is_file():
            return "catastrophe-director"
        return "studio-director"


class SkillReinforcementService:
    """Applies learned rules to .grok/skills/<slug>/SKILL.md under strict health bounds."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or _SKILLS_DIR
        self.resolver = SkillResolver(self.skills_dir)

    def reinforce_from_defects(
        self,
        defects: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Process structured defects and reinforce matching skill files.

        Returns a list of applied reinforcement records with diff/status details.
        """
        results: list[dict[str, Any]] = []

        for defect in defects:
            rule = defect.get("rule_to_learn", "").strip()
            if not rule:
                continue

            raw_skill = defect.get("responsible_skill")
            category = defect.get("category", "")
            issue = defect.get("issue", "")
            skill_slug = self.resolver.resolve(raw_skill, category=category, issue_text=issue)

            record = self.apply_learned_rule(
                skill_slug=skill_slug,
                rule=rule,
                scene_id=defect.get("scene_id"),
                category=category,
            )
            results.append(record)

        # Hot-reload memory cache if any rule was applied
        if any(r.get("applied") for r in results):
            get_skill_loader(force_reload=True)

        return results

    def apply_learned_rule(
        self,
        skill_slug: str,
        rule: str,
        scene_id: int | None = None,
        category: str = "",
    ) -> dict[str, Any]:
        """Apply a single learned invariant to SKILL.md under the <500 lines limit."""
        skill_file = self.skills_dir / skill_slug / "SKILL.md"
        if not skill_file.is_file():
            return {
                "skill_slug": skill_slug,
                "applied": False,
                "reason": f"SKILL.md not found at {skill_file}",
                "rule": rule,
            }

        content = skill_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Semantic & lexical deduplication check
        clean_rule = rule.strip().rstrip(".")
        normalized_rule_words = set(re.findall(r"\w+", clean_rule.lower()))
        for line in lines:
            line_clean = line.strip().lstrip("-* ").rstrip(".")
            if not line_clean:
                continue
            # Exact or highly overlapping match
            if clean_rule.lower() == line_clean.lower():
                return {
                    "skill_slug": skill_slug,
                    "applied": False,
                    "reason": "Rule already exists identically in skill guidelines (Deduplicated).",
                    "rule": rule,
                }
            line_words = set(re.findall(r"\w+", line_clean.lower()))
            if len(normalized_rule_words) >= 5 and len(line_words) >= 5:
                overlap = len(normalized_rule_words & line_words) / min(len(normalized_rule_words), len(line_words))
                if overlap > 0.85:
                    return {
                        "skill_slug": skill_slug,
                        "applied": False,
                        "reason": f"Semantically redundant with existing rule: '{line_clean[:60]}...' (Deduplicated).",
                        "rule": rule,
                    }

        header = "## Learned Production Invariants (Adversarial Feedback)"
        bullet = f"- **[Scene {scene_id or 'General'}]**: {clean_rule}."

        if header in content:
            # Append under existing header
            parts = content.split(header)
            prefix = parts[0] + header + "\n"
            suffix = parts[1]

            # Enforce 450 line cap consolidation if file is growing too large
            if len(lines) >= 450:
                # Consolidate older invariant lines
                suffix_lines = [l for l in suffix.splitlines() if l.strip()]
                # Keep top 10 most recent invariants + new one
                kept_invariants = [l for l in suffix_lines if l.strip().startswith("-")][-9:]
                new_suffix = "\n" + "\n".join(kept_invariants) + f"\n{bullet}\n"
                new_content = prefix + new_suffix
            else:
                new_content = prefix + f"\n{bullet}" + suffix
        else:
            # Check 500 lines limit before adding new section
            if len(lines) >= 480:
                logger.warning("Skill %s is at %d lines; cannot add new header without breaching 500-line cap.", skill_slug, len(lines))
                return {
                    "skill_slug": skill_slug,
                    "applied": False,
                    "reason": f"File at {len(lines)} lines would exceed 500-line AGENTS.md limit.",
                    "rule": rule,
                }
            new_content = content.rstrip() + f"\n\n{header}\n{bullet}\n"

        # Hard guard: Verify line count <= 500
        new_lines_count = len(new_content.splitlines())
        if new_lines_count > 500:
            logger.warning("Skill %s reinforcement rejected: Resulting length %d exceeds 500-line cap.", skill_slug, new_lines_count)
            return {
                "skill_slug": skill_slug,
                "applied": False,
                "reason": f"Resulting line count ({new_lines_count}) violates AGENTS.md 500-line limit.",
                "rule": rule,
            }

        skill_file.write_text(new_content, encoding="utf-8")
        logger.info("Reinforced skill '%s' with learned rule: %s", skill_slug, clean_rule[:60])

        return {
            "skill_slug": skill_slug,
            "applied": True,
            "rule": bullet,
            "file": str(skill_file),
            "line_count": new_lines_count,
        }
