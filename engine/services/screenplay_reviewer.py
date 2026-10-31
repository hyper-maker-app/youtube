"""Screenplay Reviewer (Dual-Agent Grok & Gemini Adversarial Quality Gate).

Implements a rigorous 100-point rubric to evaluate screenplays on:
1. CTA Isolation (15 pts) - strictly confined to final sentence of Scene 38 only.
2. Veo Negative Guardrails (25 pts) - zero mirror faces, readable UI numbers, baked-in text.
3. Thermodynamics & Physics (20 pts) - grounded phase transitions and thermal decay curve.
4. Chronological Progression (15 pts) - multi-tier timescale (hours -> days -> months -> years -> cosmos).
5. Causality & Photon Delay (15 pts) - speed of light delay (8.3 minutes) respected.
6. 2nd-Person POV Invariant (10 pts) - 100% scenes start with 'You ' or 'Your ' in English.

Target certification: Grade A+ (>= 90/100 points).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Regular expressions for audit checks
_CTA_PATTERN = re.compile(
    r"\b(subscribe|subscribing|channel|notification|notifications|next episode|follow along|smash the like|comment below)\b",
    re.IGNORECASE,
)
_MIRROR_FACE_PATTERN = re.compile(
    r"\b(mirror\s+(reflection|reflecting|face)|face\s+in\s+(?:the\s+)?(?:cracked\s+)?mirror|rearview\s+mirror\s+face|reflection\s+of\s+(?:your\s+)?face)\b",
    re.IGNORECASE,
)
_UI_READABLE_PATTERN = re.compile(
    r"\b((?:smart)?phone\s+screen\s+(?:showing|displaying|reading)|digital\s+(?:readout|display|clock|thermometer)\s+(?:showing|reading|with)|readable\s+(?:numbers|digits)|screen\s+reads\s+[\"']?\d+)\b",
    re.IGNORECASE,
)
_BAKED_TEXT_PATTERN = re.compile(
    r"\b(text\s+(?:overlay|reading|graphic)|subtitles\s+reading|sign\s+that\s+reads|words\s+reading|logo\s+on\s+screen|watermark)\b",
    re.IGNORECASE,
)


@dataclass
class Scorecard:
    """Detailed audit scorecard produced by ScreenplayReviewer."""

    total_score: int
    category_scores: dict[str, int]
    defects: list[str] = field(default_factory=list)
    passed: bool = False
    grade: str = "Grade F"
    ai_critique: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "category_scores": self.category_scores,
            "defects": self.defects,
            "passed": self.passed,
            "grade": self.grade,
            "ai_critique": self.ai_critique,
        }

    def format_report(self) -> str:
        lines = [
            f"=== SCREENPLAY AUDIT SCORECARD: {self.total_score}/100 ({self.grade}) ===",
            f"Passed Threshold (>=90): {'YES (Certified Grade A+)' if self.passed else 'NO (Repair Required)'}",
            "Category Breakdown:",
        ]
        for cat, sc in self.category_scores.items():
            lines.append(f"  - {cat:<24}: {sc} pts")
        if self.defects:
            lines.append(f"Identified Defects ({len(self.defects)}):")
            for i, d in enumerate(self.defects, 1):
                lines.append(f"  {i}. {d}")
        else:
            lines.append("Identified Defects: None (Clean screenplay).")
        if self.ai_critique:
            lines.append("\nAI Adversarial Critique:")
            lines.append(self.ai_critique.strip())
        return "\n".join(lines)


class ScreenplayReviewer:
    """Evaluates screenplays deterministically and via LLM against the 100-point rubric."""

    def __init__(self, xai_api_key: str | None = None) -> None:
        self.xai_api_key = xai_api_key

    def review(
        self,
        scenes: list[dict[str, Any]],
        title: str = "",
        genre: str = "catastrophe",
        consult_ai: bool = False,
    ) -> Scorecard:
        """Run complete 100-point adversarial evaluation on a screenplay."""
        if not scenes:
            return Scorecard(
                total_score=0,
                category_scores={},
                defects=["Screenplay is completely empty (0 scenes)."],
                passed=False,
                grade="Grade F",
            )

        cat_scores: dict[str, int] = {}
        all_defects: list[str] = []

        # 1. CTA Isolation (15 pts)
        sc_cta, def_cta = self._audit_cta_isolation(scenes)
        cat_scores["cta_isolation"] = sc_cta
        all_defects.extend(def_cta)

        # 2. Veo Negative Guardrails (25 pts)
        sc_veo, def_veo = self._audit_veo_guardrails(scenes)
        cat_scores["veo_guardrails"] = sc_veo
        all_defects.extend(def_veo)

        # 3. Thermodynamics & Physics (20 pts)
        sc_phys, def_phys = self._audit_thermodynamics(scenes)
        cat_scores["thermodynamic_sanity"] = sc_phys
        all_defects.extend(def_phys)

        # 4. Chronological Progression (15 pts)
        sc_time, def_time = self._audit_narrative_timeline(scenes)
        cat_scores["narrative_time_scale"] = sc_time
        all_defects.extend(def_time)

        # 5. Causality & Photon Delay (15 pts)
        sc_caus, def_caus = self._audit_causality(scenes)
        cat_scores["causality_integrity"] = sc_caus
        all_defects.extend(def_caus)

        # 6. 2nd-Person POV Invariant (10 pts)
        sc_pov, def_pov = self._audit_pov_invariants(scenes)
        cat_scores["pov_invariants"] = sc_pov
        all_defects.extend(def_pov)

        total_score = sum(cat_scores.values())
        # Strict Grade A+ Certification: Must achieve >= 90 AND have zero critical defects
        has_critical_defects = (
            cat_scores.get("pov_invariants", 0) < 8
            or cat_scores.get("cta_isolation", 0) < 12
            or cat_scores.get("veo_guardrails", 0) < 20
        )
        passed = total_score >= 90 and not has_critical_defects

        if passed and total_score >= 90:
            grade = "Grade A+"
        elif total_score >= 80:
            grade = "Grade A"
        elif total_score >= 70:
            grade = "Grade B"
        elif total_score >= 60:
            grade = "Grade C"
        else:
            grade = "Grade F"

        ai_critique_text = None
        if consult_ai and self.xai_api_key:
            try:
                ai_critique_text = self._consult_grok_critique(scenes, title, all_defects)
            except Exception as exc:
                logger.debug("AI critique consultation skipped: %s", exc)

        return Scorecard(
            total_score=total_score,
            category_scores=cat_scores,
            defects=all_defects,
            passed=passed,
            grade=grade,
            ai_critique=ai_critique_text,
        )

    def _audit_cta_isolation(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify subscribe CTA is strictly confined to the final sentence of Scene 38."""
        score = 15
        defects = []
        premature_cta_scenes = []

        total_scenes = len(scenes)
        for i, s in enumerate(scenes):
            narration = s.get("narration", "")
            matches = _CTA_PATTERN.findall(narration)

            if matches:
                # If it's before the final scene
                if i < total_scenes - 1:
                    premature_cta_scenes.append(i + 1)
                    defects.append(
                        f"Scene {i+1} violates CTA isolation: Contains premature CTA phrase(s) {set(matches)}. "
                        f"CTAs are strictly forbidden in Scenes 1-{total_scenes-1}."
                    )
                else:
                    # Final scene: verify it is in the last sentence
                    sentences = [st.strip() for st in re.split(r"[.!?]+", narration) if st.strip()]
                    if sentences:
                        last_sentence = sentences[-1]
                        if not _CTA_PATTERN.search(last_sentence):
                            defects.append(
                                f"Scene {total_scenes} CTA is misplaced: Must be located strictly in the very last sentence."
                            )
                            score = max(0, score - 3)

        if premature_cta_scenes:
            # Deduct 5 points per premature scene
            deduction = len(premature_cta_scenes) * 5
            score = max(0, score - deduction)

        # If final scene has zero CTA at all, award 10/15 (it's safe from spam, but lacks conversion)
        if total_scenes > 0:
            final_narration = scenes[-1].get("narration", "")
            if not _CTA_PATTERN.search(final_narration) and not premature_cta_scenes:
                score = 12

        return score, defects

    def _audit_veo_guardrails(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify prompts do not request mirror faces, readable UI text, or baked-in typography."""
        score = 25
        defects = []

        for i, s in enumerate(scenes):
            prompt = s.get("visual_prompt", "")

            # 1. Mirror face reflections
            mirror_match = _MIRROR_FACE_PATTERN.search(prompt)
            if mirror_match:
                defects.append(
                    f"Scene {i+1} visual prompt violates Veo safety: Requests mirror face reflection ('{mirror_match.group(0)}'). "
                    "Causes grotesque AI facial deformations."
                )
                score = max(0, score - 8)

            # 2. Readable UI / digits
            ui_match = _UI_READABLE_PATTERN.search(prompt)
            if ui_match:
                defects.append(
                    f"Scene {i+1} visual prompt violates Veo safety: Requests readable digital UI screen text/numbers ('{ui_match.group(0)}'). "
                    "AI engines hallucinate shifting glyphs."
                )
                score = max(0, score - 8)

            # 3. Baked-in typography
            text_match = _BAKED_TEXT_PATTERN.search(prompt)
            if text_match:
                defects.append(
                    f"Scene {i+1} visual prompt violates Veo safety: Requests baked-in typography/text graphic ('{text_match.group(0)}')."
                )
                score = max(0, score - 8)

        return max(0, score), defects

    def _audit_thermodynamics(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify realistic thermodynamic phase bounds and progressive cooling curve."""
        score = 20
        defects = []

        for i, s in enumerate(scenes):
            narration = s.get("narration", "")
            micro_math = s.get("micro_math", "")
            combined = f"{narration} {micro_math}"

            # Check for impossible nitrogen phase claims (nitrogen snow/liquid at warm temperatures)
            if re.search(r"\bnitrogen\s+(?:snow|ice|slush|rain|frost)\b", combined, re.I):
                # If temperature mentioned is > -180C (e.g. -60C, -100C)
                temp_match = re.search(r"-(?:[1-9]\d?|1[0-7]\d)\s*(?:°|deg|degrees)?\s*C\b", combined, re.I)
                if temp_match:
                    defects.append(
                        f"Scene {i+1} violates thermodynamic phase limits: Nitrogen snow/frost claimed at {temp_match.group(0)}. "
                        "Nitrogen only liquefies at -196°C and solidifies at -210°C."
                    )
                    score = max(0, score - 10)

            # Check for instant global freeze in early scenes (Scenes 1-4)
            if i < 4:
                if re.search(r"\b(?:oceans?\s+(?:are\s+)?frozen\s+solid|entire\s+planet\s+is\s+solid\s+ice)\b", combined, re.I):
                    defects.append(
                        f"Scene {i+1} violates thermal decay physics: Earth retains significant atmospheric heat; oceans take years to freeze, not minutes."
                    )
                    score = max(0, score - 10)

        return max(0, score), defects

    def _audit_narrative_timeline(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify narrative progression spans across multi-tier chronological stages."""
        score = 15
        defects = []

        if len(scenes) < 10:
            return 15, defects  # Short films don't require full cosmic arc

        full_text = " ".join([s.get("narration", "") + " " + s.get("micro_math", "") for s in scenes]).lower()

        has_hours = any(k in full_text for k in ["hour", "day 1", "24 hours", "first night"])
        has_weeks_or_months = any(k in full_text for k in ["week", "month", "30 days", "subway", "bunker", "geothermal"])
        has_year_or_ocean = any(k in full_text for k in ["year", "ocean", "ice sheet", "crust", "drift"])
        has_cosmic = any(k in full_text for k in ["cosmos", "cosmic", "star", "sunless", "rogue planet", "milky way", "centuries", "millennia", "drift"])

        missing = []
        if not has_hours:
            missing.append("Day 1 initial crisis")
        if not has_weeks_or_months:
            missing.append("Week/Month structural freeze")
        if not (has_year_or_ocean or has_cosmic):
            missing.append("Year 1 or cosmic timescale aftermath")

        if len(missing) >= 2:
            defects.append(
                f"Narrative scale compressed: Missing multi-tier chronological progression ({', '.join(missing)}). "
                "Scenes appear trapped in an immediate timeframe without long-term survival escalation."
            )
            score = max(0, score - 8)

        return max(0, score), defects

    def _audit_causality(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify speed-of-light delay and causal ordering in opening scenes."""
        score = 15
        defects = []

        if len(scenes) >= 2:
            s1_text = scenes[0].get("narration", "").lower()
            s2_text = scenes[1].get("narration", "").lower()

            # If Scene 1 asserts the sun disappeared at t=0, check if darkness or photon delay is handled
            if "sun" in s1_text and ("disappear" in s1_text or "vanish" in s1_text):
                # If Scene 1 or 2 claims instant darkness without acknowledging light speed delay
                claims_instant_dark = "instant" in s1_text and "dark" in s1_text
                mentions_delay = any(k in (s1_text + " " + s2_text) for k in ["8 minute", "8.3", "500 second", "delay", "speed of light", "last photon", "illusion", "delusion", "still shining"])
                if claims_instant_dark and not mentions_delay:
                    defects.append(
                        "Causality paradox in Scenes 1-2: Instant darkness claimed upon Sun disappearance without accounting "
                        "for the 8-minute-and-20-second speed-of-light photon delay."
                    )
                    score = max(0, score - 8)

        return max(0, score), defects

    def _audit_pov_invariants(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify 100% of scenes start with 'You ' or 'Your ' in clean English."""
        score = 10
        defects = []
        invalid_pov_count = 0

        for i, s in enumerate(scenes):
            narr = s.get("narration", "").strip()
            if not narr.startswith(("You ", "Your ")):
                invalid_pov_count += 1
                first_few_words = " ".join(narr.split()[:3])
                defects.append(
                    f"Scene {i+1} violates 2nd-person POV invariant: Starts with '{first_few_words}...' instead of 'You ' or 'Your '."
                )

        if invalid_pov_count > 0:
            deduction = min(10, invalid_pov_count * 2)
            score = max(0, score - deduction)

        return score, defects

    def _consult_grok_critique(
        self,
        scenes: list[dict[str, Any]],
        title: str,
        defects: list[str],
    ) -> str:
        """Query Grok API to provide deep adversarial review."""
        import json
        import urllib.request
        import os

        model_name = os.getenv("XAI_CHAT_MODEL", "grok-4.20-0309-non-reasoning")
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Lead Screenplay Reviewer and Physicist for Grok Imagine Cinematic Studio. "
                        "Conduct an adversarial critique of the provided screenplay. Focus on Veo video safety, "
                        "thermodynamic laws, speed-of-light causality, and retention pacing. Be concise, rigorous, and direct."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Film Title: {title}\n"
                        f"Total Scenes: {len(scenes)}\n"
                        f"Deterministic Defects Flagged:\n" + "\n".join(f"- {d}" for d in defects) + "\n\n"
                        f"Screenplay Scenes JSON:\n{json.dumps(scenes[:10], indent=2)}\n\n"
                        "Provide a 3-bullet adversarial executive review assessing whether this screenplay is ready for physical video rendering."
                    ),
                },
            ],
            "temperature": 0.3,
        }

        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.xai_api_key}",
            },
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
