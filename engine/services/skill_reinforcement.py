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
    "survival": "micro-survival-director",
    "fema": "micro-survival-director",
    "void": "micro-survival-director",
    "planetary": "planetary-catastrophe-director",
    "cosmic": "planetary-catastrophe-director",
    "deepsea": "deepsea-survival-director",
    "hadal": "deepsea-survival-director",
    "ocean": "deepsea-survival-director",
    "urban": "urban-infiltration-director",
    "blackout": "urban-infiltration-director",
    "scada": "urban-infiltration-director",
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

        # Semantic & lexical deduplication check (primary pass — exact and near-exact)
        clean_rule = rule.strip().rstrip(".")
        normalized_rule_words = set(re.findall(r"\w+", clean_rule.lower()))
        for line in lines:
            line_clean = line.strip().lstrip("-* ").rstrip(".")
            if not line_clean:
                continue
            # Exact match
            if clean_rule.lower() == line_clean.lower():
                return {
                    "skill_slug": skill_slug,
                    "applied": False,
                    "reason": "Rule already exists identically in skill guidelines (Deduplicated).",
                    "rule": rule,
                }

        # Additional deduplication: normalise scene ids (s030 == 30) for cross-format matching
        def _norm_scene(text: str) -> str:
            import re as _re
            # Strip leading zeros and 's' prefix: "s030" -> "30", "s009" -> "9"
            return _re.sub(r'\bs0*(\d+)\b', lambda m: str(int(m.group(1))), text.lower())

        norm_rule = _norm_scene(clean_rule)
        norm_rule_words = set(re.findall(r"\w+", norm_rule))

        for line in lines:
            line_clean = line.strip().lstrip("-* ").rstrip(".")
            if not line_clean:
                continue
            norm_line = _norm_scene(line_clean)
            norm_line_words = set(re.findall(r"\w+", norm_line))
            if len(norm_rule_words) >= 5 and len(norm_line_words) >= 5:
                overlap = len(norm_rule_words & norm_line_words) / min(len(norm_rule_words), len(norm_line_words))
                if overlap > 0.80:  # tightened from 0.85 to catch cross-format duplicates
                    return {
                        "skill_slug": skill_slug,
                        "applied": False,
                        "reason": f"Semantically redundant (normalised) with existing rule: '{line_clean[:60]}' (Deduplicated).",
                        "rule": rule,
                    }

        # Hard cap: reject if skill already has >= 20 learned invariant entries.
        # Rules beyond this threshold indicate a structural skill problem (wrong root cause),
        # not a genuine new invariant. Human review is required.
        existing_invariant_count = sum(
            1 for l in lines if l.strip().startswith("- **[Scene")
        )
        if existing_invariant_count >= 20:
            logger.warning(
                "Skill '%s' already has %d learned invariants (>= 20 cap). "
                "Root-cause skill redesign required before adding more rules.",
                skill_slug, existing_invariant_count,
            )
            return {
                "skill_slug": skill_slug,
                "applied": False,
                "reason": (
                    f"Skill '{skill_slug}' has {existing_invariant_count} learned invariants "
                    f"(hard cap = 20). This indicates a structural skill problem. "
                    "Redesign the skill's core directives instead of appending more patches."
                ),
                "rule": rule,
            }

        header = "## Universal Physics & Causality Invariants"
        # Fall back to legacy header if new one not present
        legacy_header = "## Learned Production Invariants (Adversarial Feedback)"
        active_header = header if header in content else (legacy_header if legacy_header in content else header)
        bullet = f"- **[Scene {scene_id or 'General'}]**: {clean_rule}."

        if active_header in content:
            # Append under existing header
            parts = content.split(active_header, 1)
            prefix = parts[0] + active_header + "\n"
            suffix = parts[1]

            # Enforce 150 line cap on learned section: keep last 9 + new one
            if len(lines) >= 150:
                suffix_lines = [l for l in suffix.splitlines() if l.strip()]
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
            new_content = content.rstrip() + f"\n\n{active_header}\n{bullet}\n"

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
        logger.info("Reinforced skill '%s' with learned rule: %s", skill_slug, clean_rule)

        return {
            "skill_slug": skill_slug,
            "applied": True,
            "rule": bullet,
            "file": str(skill_file),
            "line_count": new_lines_count,
        }
