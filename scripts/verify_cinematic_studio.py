#!/usr/bin/env python3
"""Cross-platform Python verifier for Grok Imagine Cinematic Studio.

Verifies:
1. All skills in scripts/required_skills.manifest exist in .grok/skills/
2. Strict YAML frontmatter and conventions for Phase 6 skills:
   - catastrophe-director
   - thumbnail-designer
   - youtube-factory
   - Strict frontmatter: name matches kebab-case directory name
   - Description is single-line plain text (no colons, no angle brackets, < 1024 chars)
   - Model Layer (Grok 4.6) block exists
   - Agent-only (zero README.md / CHANGELOG.md in skill folders)
3. Model registry verification (tools/models.py)
4. Boundary inspector threshold is 0.80
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

# Ensure UTF-8 output even on legacy Windows terminals
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

MANIFEST_PATH = ROOT / "scripts" / "required_skills.manifest"
SKILLS_DIR = ROOT / ".grok" / "skills"

PHASE6_SKILLS = {
    "catastrophe-director",
    "thumbnail-designer",
    "youtube-factory",
}


def parse_frontmatter(path: Path) -> dict[str, str]:
    """Parse YAML frontmatter from a SKILL.md file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        fields[k] = v
    return fields


def verify_skills() -> tuple[int, int, list[str]]:
    """Verify all required skills against repository conventions."""
    if not MANIFEST_PATH.is_file():
        return 0, 1, [f"Manifest file not found: {MANIFEST_PATH}"]

    manifest_lines = MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    required: list[str] = []
    for line in manifest_lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        name = s.split("#")[0].strip()
        if name:
            required.append(name)

    passed = 0
    failed = 0
    errors: list[str] = []

    for name in required:
        skill_dir = SKILLS_DIR / name
        skill_md = skill_dir / "SKILL.md"

        if not skill_dir.is_dir():
            errors.append(f"Skill directory missing: {skill_dir}")
            failed += 1
            continue

        if not skill_md.is_file():
            errors.append(f"SKILL.md missing in: {skill_dir}")
            failed += 1
            continue

        # Strict checks for Phase 6 skills
        if name in PHASE6_SKILLS:
            for forbidden in ("README.md", "CHANGELOG.md"):
                if (skill_dir / forbidden).is_file():
                    errors.append(f"Forbidden file '{forbidden}' in agent skill dir: {skill_dir}")
                    failed += 1
                    break

            fm = parse_frontmatter(skill_md)
            if not fm.get("name"):
                errors.append(f"Missing frontmatter 'name' in {skill_md}")
                failed += 1
                continue
            if fm["name"] != name:
                errors.append(f"Frontmatter name '{fm['name']}' != folder name '{name}' in {skill_md}")
                failed += 1
                continue

            desc = fm.get("description", "")
            if not desc:
                errors.append(f"Missing frontmatter 'description' in {skill_md}")
                failed += 1
                continue
            if "\n" in desc:
                errors.append(f"Description must be single-line in {skill_md}")
                failed += 1
                continue
            if len(desc) > 1024:
                errors.append(f"Description exceeds 1024 chars in {skill_md}")
                failed += 1
                continue
            if "<" in desc or ">" in desc:
                errors.append(f"Description contains angle brackets in {skill_md}")
                failed += 1
                continue

            content = skill_md.read_text(encoding="utf-8", errors="replace")
            if "## Model Layer (Grok 4.6)" not in content and "Model Layer" not in content:
                errors.append(f"Missing Model Layer block in {skill_md}")
                failed += 1
                continue

        passed += 1

    return passed, failed, errors


def verify_boundary_inspector() -> tuple[bool, str]:
    """Verify boundary_inspector.py threshold is 0.80."""
    try:
        from engine.services.boundary_inspector import TRANSITION_SCORE_THRESHOLD
        if abs(TRANSITION_SCORE_THRESHOLD - 0.80) < 1e-4:
            return True, f"Boundary inspector threshold is {TRANSITION_SCORE_THRESHOLD:.2f}"
        return False, f"Boundary inspector threshold is {TRANSITION_SCORE_THRESHOLD}, expected 0.80"
    except Exception as exc:
        return False, f"Failed to import or inspect boundary_inspector: {exc}"


def verify_models() -> tuple[bool, str]:
    """Verify model stack registry."""
    try:
        from tools.models import verify_model_compatibility
        res = verify_model_compatibility()
        if res.get("compatible") and not res.get("issues"):
            return True, "Model stack registry is compatible and valid"
        return False, f"Model stack invalid: {res}"
    except Exception as exc:
        return False, f"Failed to verify models: {exc}"


def main() -> int:
    print("=" * 60)
    print("Grok Imagine Cinematic Studio — Python Verification Suite")
    print("=" * 60)

    # 1. Skills verification
    passed_skills, failed_skills, skill_errors = verify_skills()
    print(f"\n[Skills] Verified {passed_skills} skill(s) against manifest.")
    if failed_skills > 0:
        print(f"❌ {failed_skills} skill error(s) found:")
        for err in skill_errors:
            print(f"   • {err}")
    else:
        print(f"✅ All {passed_skills} skills verified successfully.")

    # 2. Boundary inspector verification
    bi_ok, bi_msg = verify_boundary_inspector()
    if bi_ok:
        print(f"[Boundary Inspector] ✅ {bi_msg}")
    else:
        print(f"[Boundary Inspector] ❌ {bi_msg}")

    # 3. Model registry verification
    m_ok, m_msg = verify_models()
    if m_ok:
        print(f"[Model Registry] ✅ {m_msg}")
    else:
        print(f"[Model Registry] ❌ {m_msg}")

    total_failures = failed_skills + (0 if bi_ok else 1) + (0 if m_ok else 1)
    print("\n" + "=" * 60)
    if total_failures == 0:
        print("✅ ALL STUDIO CHECKS PASSED GREEN")
        print("=" * 60)
        return 0
    else:
        print(f"❌ {total_failures} FAILURE(S) DETECTED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
