"""Capture the skill directives actually selected by the production loader.

This is provenance, not a physics parser or a certification decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import math
import re

from .skill_loader import SkillLoader


@dataclass(frozen=True)
class SkillDirective:
    role: str
    slug: str
    source: str
    sha256: str
    instructions: str


@dataclass(frozen=True)
class WorldRuleSet:
    slug: str
    source: str
    sha256: str
    version: str
    rules: tuple[dict, ...]


def load_world_rule_sets(directives: tuple[SkillDirective, ...]) -> tuple[WorldRuleSet, ...]:
    """Load explicitly referenced and validated rules for the selected skills."""
    result = []
    seen = set()
    for directive in directives:
        if "`references/review_rules.json`" not in directive.instructions:
            continue
        path = Path(directive.source).parent / "references" / "review_rules.json"
        raw = path.read_bytes()
        doc = json.loads(raw)
        if not isinstance(doc.get("version"), str) or not isinstance(doc.get("rules"), list) or not doc["rules"]:
            raise ValueError(f"Invalid rule set: {path}")
        rules = []
        for rule in doc["rules"]:
            if not isinstance(rule, dict) or not all(isinstance(rule.get(k), str) and rule[k] for k in ("id", "category", "scope", "description")):
                raise ValueError(f"Invalid rule: {path}")
            if rule["id"] in seen or rule["scope"] != "scene":
                raise ValueError(f"Duplicate or invalid rule: {rule['id']}")
            seen.add(rule["id"])
            if rule.get("kind") == "semantic":
                if rule["category"] != "world_law" or not isinstance(rule.get("source_url"), str) or not rule["source_url"].startswith("https://"):
                    raise ValueError(f"Invalid semantic rule: {rule['id']}")
                rules.append(dict(rule))
                continue
            if rule.get("kind", "numeric") != "numeric" or not isinstance(rule.get("quantity_pattern"), str) or not rule["quantity_pattern"]:
                raise ValueError(f"Invalid numeric rule: {rule['id']}")
            patterns = rule.get("all_patterns")
            if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) and p for p in patterns):
                raise ValueError(f"Invalid patterns: {rule['id']}")
            for pattern in [*patterns, rule["quantity_pattern"]]:
                re.compile(pattern)
            limit, deduction = rule.get("violation_if_greater_than"), rule.get("deduction")
            if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or isinstance(deduction, bool) or not isinstance(deduction, int) or deduction < 0:
                raise ValueError(f"Invalid bounds: {rule['id']}")
            rules.append(dict(rule))
        result.append(WorldRuleSet(directive.slug, str(path), sha256(raw).hexdigest(), doc["version"], tuple(rules)))
    return tuple(result)


def capture_world_laws(loader: SkillLoader, genre: str) -> tuple[SkillDirective, ...]:
    """Snapshot selected skill bodies without inferring numerical rules from prose."""
    directives = loader.assemble_production_directives(genre)
    selected = {}
    for skill in loader.list_skills():
        selected[skill["name"]] = loader.load_skill_instructions(skill["name"], max_chars=0)
    result = []
    for role, text in directives.items():
        if not text:
            raise ValueError(f"Missing required {role} skill directives")
        matches = [slug for slug, full in selected.items() if full.startswith(text)]
        if len(matches) != 1:
            raise ValueError(f"Cannot uniquely identify {role} skill directives")
        slug = matches[0]
        skill = loader.get_skill(slug)
        assert skill is not None
        path = Path(skill["path"])
        current_body = loader._extract_body(path.read_text(encoding="utf-8"))
        if current_body != skill["instructions"]:
            raise ValueError(f"Skill {slug} changed since the loader was indexed; reload it")
        result.append(SkillDirective(role, slug, str(path), sha256(path.read_bytes()).hexdigest(), selected[slug]))
    return tuple(result)
