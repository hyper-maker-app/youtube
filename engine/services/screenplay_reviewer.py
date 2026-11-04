"""Screenplay Reviewer (Dual-Agent Grok & Gemini Adversarial Quality Gate).

Implements universal 7-layer cinematic evaluation:
1. CTA Isolation (15 pts) - strictly confined to final sentence of Scene 38 only.
2. Veo Negative Guardrails (25 pts) - zero mirror faces, readable UI numbers, baked-in text.
3. Thermodynamics & Physics (20 pts) - realistic phase transitions & atmospheric thermodynamics.
4. Chronological Progression (15 pts) - multi-tier timescale (hours -> days -> months -> years -> cosmos).
5. Causality & Photon Delay (15 pts) - speed of light & causal integrity.
6. 2nd-Person POV Invariant (10 pts) - 100% scenes start with 'You ' or 'Your ' in English.

When consult_ai=True:
- Grok (xAI API) & Gemini (gemini_webapi Chrome CDP port 9223) inspect ALL 38 scenes in compact JSON.
- Pessimistic Scoring Gate: Final Score = min(Grok, Gemini).
- Fail-Closed User Gate: Never silently fall back to DeepMind without explicit user approval.
- Structured Defects: Directly tags responsible_skill and rule_to_learn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any
import urllib.request

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


class GeminiWebAPIUnavailableError(RuntimeError):
    """Raised when gemini_webapi connection fails and user has not authorized fallback."""
    pass


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    """RobustJsonExtractor: Extracts and parses JSON from raw LLM responses with chatter, markdown fences, or unescaped LaTeX/backslashes."""
    if not raw_text or not raw_text.strip():
        return {}

    cleaned = raw_text.strip()
    # Check for markdown code fences (even if unclosed)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", cleaned, re.IGNORECASE)
    candidate = fence_match.group(1).strip() if fence_match else cleaned

    # Locate outermost curly braces
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = candidate[start:end + 1]
    elif start != -1 and end <= start:
        candidate = candidate[start:] + "\n}"

    # 1. First attempt: direct parse with strict=False (allows literal newlines inside strings)
    try:
        return json.loads(candidate, strict=False)
    except Exception as exc:
        logger.debug("First-pass JSON extraction failed (%s), attempting syntax repair...", exc)

    # 2. Second attempt: sanitize invalid backslash escapes (e.g. LaTeX \circ, \text, \mu or Windows paths)
    # Valid JSON escapes are: \" \\ \/ \b \f \n \r \t \uXXXX
    repaired = re.sub(r'\\(?![/"\\bfnrtu]|u[0-9a-fA-F]{4})', r'\\\\', candidate)
    # Remove trailing commas before closing braces/brackets
    repaired = re.sub(r",\s*([\]}])", r"\1", repaired)

    try:
        return json.loads(repaired, strict=False)
    except Exception as exc2:
        logger.debug("Second-pass escape repair failed (%s), attempting structural repair...", exc2)

    # 3. Third attempt: balance unclosed quotes, brackets, braces
    try:
        quote_count = repaired.count('"') - repaired.count(r'\"')
        if quote_count % 2 != 0:
            repaired += '"'
        open_braces = repaired.count('{') - repaired.count('}')
        if open_braces > 0:
            repaired += '}' * open_braces
        open_brackets = repaired.count('[') - repaired.count(']')
        if open_brackets > 0:
            repaired += ']' * open_brackets
        return json.loads(repaired, strict=False)
    except Exception:
        logger.warning("RobustJsonExtractor could not parse payload: %s", raw_text[:200])
        return {}


def validate_judge_score(value: Any) -> int | float | None:
    """Reject malformed, boolean, non-finite and out-of-range model scores."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and 0 <= value <= 100 else None


def build_compact_scenes_payload(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build compact, token-efficient JSON view of all scenes for dual-judge review."""
    return [
        {
            "scene_id": s.get("id") or s.get("scene_id", idx + 1),
            "duration": s.get("duration", 8.0),
            "narration": s.get("narration", ""),
            "visual_prompt": s.get("visual_prompt", ""),
            "camera": s.get("camera", {}),
            "micro_math": s.get("micro_math", ""),
            "sfx": s.get("sfx", ""),
            "is_data_broll": s.get("is_data_broll", False),
            "template_name": s.get("template_name", ""),
            "data_payload": s.get("data_payload", {}),
        }
        for idx, s in enumerate(scenes)
    ]


@dataclass
class Scorecard:
    """Detailed audit scorecard produced by ScreenplayReviewer."""

    total_score: int
    category_scores: dict[str, int]
    defects: list[str] = field(default_factory=list)
    structured_defects: list[dict[str, Any]] = field(default_factory=list)
    passed: bool = False
    grade: str = "Grade F"
    ai_critique: str | None = None
    grok_score: int | None = None
    gemini_score: int | None = None
    raw_grok_response: str | None = None
    raw_gemini_response: str | None = None
    raw_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "category_scores": self.category_scores,
            "defects": self.defects,
            "structured_defects": self.structured_defects,
            "passed": self.passed,
            "grade": self.grade,
            "ai_critique": self.ai_critique,
            "grok_score": self.grok_score,
            "gemini_score": self.gemini_score,
        }

    def format_report(self) -> str:
        lines = [
            f"=== SCREENPLAY AUDIT SCORECARD: {self.total_score}/100 ({self.grade}) ===",
            f"Passed Threshold (>=90): {'YES (Certified Grade A+)' if self.passed else 'NO (Repair Required)'}",
            "Category Breakdown:",
        ]
        for cat, sc in self.category_scores.items():
            lines.append(f"  - {cat:<24}: {sc} pts")
        if self.grok_score is not None or self.gemini_score is not None:
            lines.append(f"Dual-Judge Scores: Grok = {self.grok_score or 'N/A'}, Gemini = {self.gemini_score or 'N/A'}")
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
    """Evaluates screenplays deterministically and via dual Grok & Gemini LLM judges."""

    def __init__(
        self,
        xai_api_key: str | None = None,
        allow_deepmind_fallback: bool = False,
        gemini_model: str = "gemini-3.1-pro",
        grok_model: str = "grok-4.20-0309-non-reasoning",
    ) -> None:
        self.xai_api_key = xai_api_key
        self.allow_deepmind_fallback = allow_deepmind_fallback
        self.gemini_model = gemini_model
        self.grok_model = grok_model

    def review(
        self,
        scenes: list[dict[str, Any]],
        title: str = "",
        genre: str = "catastrophe",
        consult_ai: bool = False,
    ) -> Scorecard:
        """Run complete adversarial evaluation on a screenplay."""
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
        schema_defects: list[str] = []
        for index, scene in enumerate(scenes, 1):
            if scene.get("simulation_only"):
                schema_defects.append(f"Scene {index}: simulation fixtures cannot receive production certification")
            for key in ("narration", "visual_prompt"):
                if not isinstance(scene.get(key), str) or not scene[key].strip():
                    schema_defects.append(f"Scene {index}: {key} is required and must be non-empty")
            if scene.get("is_data_broll") or "[DATA_BROLL]" in str(scene.get("visual_prompt", "")).upper():
                try:
                    from engine.services.remotion_bridge import validate_broll_payload
                    validate_broll_payload(scene.get("template_name", ""), scene.get("data_payload", {}))
                except (ValueError, TypeError, AttributeError) as exc:
                    schema_defects.append(f"Scene {index}: invalid B-roll contract: {exc}")
        all_defects.extend(schema_defects)

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
        sc_caus, def_caus = self._audit_causality(scenes, title=title)
        cat_scores["causality_integrity"] = sc_caus
        all_defects.extend(def_caus)

        # 6. 2nd-Person POV Invariant (10 pts)
        sc_pov, def_pov = self._audit_pov_invariants(scenes)
        cat_scores["pov_invariants"] = sc_pov
        all_defects.extend(def_pov)

        deterministic_score = sum(cat_scores.values())
        has_critical_defects = (
            bool(schema_defects)
            or cat_scores.get("pov_invariants", 0) < 8
            or cat_scores.get("cta_isolation", 0) < 12
            or cat_scores.get("veo_guardrails", 0) < 20
        )

        grok_score: int | None = None
        gemini_score: int | None = None
        ai_critique_text: str | None = None
        raw_grok: str | None = None
        raw_gemini: str | None = None
        structured_defects: list[dict[str, Any]] = []

        compact_payload = build_compact_scenes_payload(scenes)
        raw_prompt = json.dumps(compact_payload, indent=2, ensure_ascii=False)

        if consult_ai:
            grok_data: dict[str, Any] = {}
            gemini_data: dict[str, Any] = {}

            # Judge 1: Grok xAI
            if self.xai_api_key:
                try:
                    grok_data = self._consult_grok_critique(compact_payload, title, genre, all_defects)
                    grok_score = validate_judge_score(grok_data.get("screenplay_score"))
                    raw_grok = grok_data.get("raw_response")
                    for d in grok_data.get("defects", []):
                        structured_defects.append(d)
                        all_defects.append(f"[Grok] Scene {d.get('scene_id')}: {d.get('issue')}")
                except Exception as exc:
                    grok_score = None
                    logger.warning("Grok judge critique failed: %s", exc)

            # Judge 2: Google Gemini (gemini_webapi via CDP port 9223)
            try:
                gemini_data = self._consult_gemini_critique(compact_payload, title, genre, all_defects)
                gemini_score = validate_judge_score(gemini_data.get("screenplay_score"))
                raw_gemini = gemini_data.get("raw_response")
                for d in gemini_data.get("defects", []):
                    structured_defects.append(d)
                    all_defects.append(f"[Gemini] Scene {d.get('scene_id')}: {d.get('issue')}")
            except GeminiWebAPIUnavailableError:
                raise
            except Exception as exc:
                gemini_score = None
                logger.warning("Gemini judge critique failed: %s", exc)

            # Build dual-judge summary text
            critique_parts = []
            if grok_data.get("critique_text") or grok_data.get("raw_response"):
                c_text = grok_data.get("critique_text") or grok_data.get("raw_response")
                critique_parts.append(f"### [JUDGE 1: xAI Grok ({grok_score or 'N/A'}/100)]\n{c_text}")
            if gemini_data.get("critique_text") or gemini_data.get("raw_response"):
                c_text = gemini_data.get("critique_text") or gemini_data.get("raw_response")
                critique_parts.append(f"### [JUDGE 2: Google Gemini ({gemini_score or 'N/A'}/100)]\n{c_text}")

            if critique_parts:
                ai_critique_text = "\n\n".join(critique_parts)

        # Calculate Final Score (Pessimistic Scoring Gate when AI judges respond)
        if not consult_ai:
            total_score = deterministic_score
            passed = total_score >= 90 and not has_critical_defects
        else:
            # AI judges were consulted
            if grok_score is not None and gemini_score is not None:
                total_score = min(grok_score, gemini_score)
                passed = (
                    total_score >= 90
                    and grok_score >= 90
                    and gemini_score >= 90
                    and deterministic_score >= 90
                    and not has_critical_defects
                )
            elif grok_score is not None and not self.xai_api_key:
                total_score = min(deterministic_score, grok_score)
                passed = total_score >= 90 and grok_score >= 85 and not has_critical_defects
            elif gemini_score is not None and not self.xai_api_key:
                # Only Gemini configured (no xAI API key provided)
                total_score = min(deterministic_score, gemini_score)
                passed = total_score >= 90 and gemini_score >= 85 and not has_critical_defects
            elif grok_score is not None and gemini_score is None:
                total_score = min(deterministic_score, grok_score)
                passed = False
                all_defects.append("[Judge Fail-Closed] Gemini judge did not return a valid score.")
            elif gemini_score is not None and grok_score is None:
                total_score = min(deterministic_score, gemini_score)
                passed = False
                all_defects.append("[Judge Fail-Closed] Grok judge did not return a valid score (timed out or error).")
            else:
                total_score = deterministic_score
                passed = False
                all_defects.append("[Judge Fail-Closed] Neither Grok nor Gemini judge returned a valid score.")

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

        return Scorecard(
            total_score=total_score,
            category_scores=cat_scores,
            defects=all_defects,
            structured_defects=structured_defects,
            passed=passed,
            grade=grade,
            ai_critique=ai_critique_text,
            grok_score=grok_score,
            gemini_score=gemini_score,
            raw_grok_response=raw_grok,
            raw_gemini_response=raw_gemini,
            raw_prompt=raw_prompt,
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
                if i < total_scenes - 1:
                    premature_cta_scenes.append(i + 1)
                    defects.append(
                        f"Scene {i+1} violates CTA isolation: Contains premature CTA phrase(s) {set(matches)}. "
                        f"CTAs are strictly forbidden in Scenes 1-{total_scenes-1}."
                    )
                else:
                    sentences = [st.strip() for st in re.split(r"[.!?]+", narration) if st.strip()]
                    if sentences:
                        last_sentence = sentences[-1]
                        if not _CTA_PATTERN.search(last_sentence):
                            defects.append(
                                f"Scene {total_scenes} CTA is misplaced: Must be located strictly in the very last sentence."
                            )
                            score = max(0, score - 3)

        if premature_cta_scenes:
            deduction = len(premature_cta_scenes) * 5
            score = max(0, score - deduction)

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
            if s.get("is_data_broll") or "[DATA_BROLL]" in prompt.upper():
                continue
            # Only audit the positive prompt (exclude negative prompt after --no)
            pos_prompt = prompt.split("--no")[0] if "--no" in prompt else prompt

            # 1. Mirror face reflections
            mirror_match = _MIRROR_FACE_PATTERN.search(pos_prompt)
            if mirror_match:
                defects.append(
                    f"Scene {i+1} visual prompt violates Veo safety: Requests mirror face reflection ('{mirror_match.group(0)}'). "
                    "Causes grotesque AI facial deformations."
                )
                score = max(0, score - 8)

            # 2. Readable UI / digits
            ui_match = _UI_READABLE_PATTERN.search(pos_prompt)
            if ui_match:
                preceding = pos_prompt[max(0, ui_match.start() - 10):ui_match.start()].lower()
                if not any(k in preceding for k in ["no ", "zero ", "without "]):
                    defects.append(
                        f"Scene {i+1} visual prompt violates Veo safety: Requests readable digital UI screen text/numbers ('{ui_match.group(0)}'). "
                        "AI engines hallucinate shifting glyphs."
                    )
                    score = max(0, score - 8)

            # 3. Baked-in typography
            text_match = _BAKED_TEXT_PATTERN.search(pos_prompt)
            if text_match:
                defects.append(
                    f"Scene {i+1} visual prompt violates Veo safety: Requests baked-in typography/text graphic ('{text_match.group(0)}')."
                )
                score = max(0, score - 8)

        return max(0, score), defects

    def _audit_thermodynamics(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify realistic thermodynamic phase bounds and progressive cooling/heating curve."""
        score = 20
        defects = []

        for i, s in enumerate(scenes):
            narration = s.get("narration", "")
            micro_math = s.get("micro_math", "")
            combined = f"{narration} {micro_math}"

            # Check for impossible nitrogen phase claims
            if re.search(r"\b(?:nitrogen\b[^\.\,\;]*\b(?:liquef\w*|rain|snow|ice|slush|frost)|liquid\s+nitrogen)\b", combined, re.I):
                temp_match = re.search(r"-(?:[1-9]\d?|1[0-8]\d|19[0-5])\s*(?:°|deg|degrees)?\s*C\b", combined, re.I) or re.search(r"\bminus\s+(?:1[0-8]\d|19[0-5]|[1-9]\d?)\s*(?:°|deg|degrees)?\s*(?:C|celsius)\b", combined, re.I)
                if temp_match:
                    defects.append(
                        f"Scene {i+1} violates thermodynamic phase limits: Nitrogen liquefaction/snow claimed at {temp_match.group(0)}. "
                        "Nitrogen only liquefies at -196°C and solidifies at -210°C."
                    )
                    score = max(0, score - 10)

            # Check for impossible oxygen phase claims
            if re.search(r"\b(?:oxygen\b[^\.\,\;]*\b(?:liquef\w*|rain|droplets|frost)|liquid\s+oxygen)\b", combined, re.I):
                temp_match = re.search(r"-(?:[1-9]\d?|1[0-7]\d|18[0-2])\s*(?:°|deg|degrees)?\s*C\b", combined, re.I) or re.search(r"\bminus\s+(?:1[0-7]\d|18[0-2]|[1-9]\d?)\s*(?:°|deg|degrees)?\s*(?:C|celsius)\b", combined, re.I)
                if temp_match:
                    defects.append(
                        f"Scene {i+1} violates thermodynamic phase limits: Liquid oxygen claimed at {temp_match.group(0)}. "
                        "Oxygen only liquefies at -183°C."
                    )
                    score = max(0, score - 10)

        return max(0, score), defects

    def _audit_narrative_timeline(self, scenes: list[dict[str, Any]]) -> tuple[int, list[str]]:
        """Verify narrative progression spans across multi-tier chronological stages."""
        score = 15
        defects = []

        if len(scenes) < 5:
            return 15, defects

        full_text = " ".join([s.get("narration", "") + " " + s.get("micro_math", "") for s in scenes]).lower()
        has_initial = any(k in full_text for k in ["minute", "hour", "day 1", "24 hours", "first night", "initial", "seconds", "moment"])
        has_escalation = any(k in full_text for k in ["week", "month", "days", "aftermath", "deepens", "subway", "bunker", "shelter", "pressure"])
        has_long_term = any(k in full_text for k in ["year", "decade", "ocean", "crust", "ice", "steam", "salt", "cosmos", "drift", "centuries", "millennia", "extinction", "survive"])

        missing = []
        if not has_initial:
            missing.append("initial crisis stage")
        if not has_escalation:
            missing.append("escalation stage")
        if not has_long_term:
            missing.append("long-term / climatic aftermath")

        if len(missing) >= 2:
            defects.append(
                f"Narrative scale compressed: Missing multi-tier progression ({', '.join(missing)})."
            )
            score = max(0, score - 8)

        return max(0, score), defects

    def _audit_causality(self, scenes: list[dict[str, Any]], title: str = "") -> tuple[int, list[str]]:
        """Verify causality and speed-of-light delay where applicable."""
        score = 15
        defects = []

        # Only enforce 8.3-minute photon delay if the film is specifically about the Sun vanishing
        combined_title_s1 = (title + " " + (scenes[0].get("narration", "") if scenes else "")).lower()
        if "sun" in combined_title_s1 and ("disappear" in combined_title_s1 or "vanish" in combined_title_s1):
            s1_text = scenes[0].get("narration", "").lower()
            s2_text = scenes[1].get("narration", "").lower() if len(scenes) > 1 else ""
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
        compact_scenes: list[dict[str, Any]],
        title: str,
        genre: str,
        deterministic_defects: list[str],
    ) -> dict[str, Any]:
        """Query Grok API to provide deep adversarial review across all scenes in compact JSON."""
        model_name = self.grok_model or "grok-4.20-0309-non-reasoning"
        try:
            from tools.models import resolve_chat_model
            model_name = resolve_chat_model(model_name)
        except Exception:
            if model_name in ("grok-4.20-non-reasoning", "grok-4.20"):
                model_name = "grok-4.20-0309-non-reasoning"

        system_prompt = (
            "You are the Lead Adversarial Screenplay Reviewer & Scientific Director for Grok Imagine Cinematic Studio.\n"
            "Review the COMPLETE screenplay presented in compact JSON format.\n"
            "Evaluate:\n"
            "1. Veo generative video safety (avoid facial glitches, readable digital UI numbers, baked-in text overlays).\n"
            "2. Scientific, thermodynamic, and physical causality realism.\n"
            "3. 2nd-person immersion ('You/Your') and viral retention pacing.\n"
            "4. CTA isolation (strictly confined to the final sentence of the last scene).\n\n"
            "You MUST respond ONLY with valid JSON conforming to this schema:\n"
            "{\n"
            '  "screenplay_score": 85,\n'
            '  "grade": "Grade B",\n'
            '  "critique_text": "Executive summary of audit...",\n'
            '  "defects": [\n'
            "    {\n"
            '      "scene_id": 12,\n'
            '      "category": "physics",\n'
            '      "responsible_skill": "catastrophe-director",\n'
            '      "issue": "Specific explanation of defect...",\n'
            '      "fix_instruction": "Actionable command to repair this scene...",\n'
            '      "rule_to_learn": "One-line operational invariant to record in skill guidelines."\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        user_content = (
            f"Film Title: {title}\n"
            f"Genre: {genre}\n"
            f"Total Scenes: {len(compact_scenes)}\n"
            f"Deterministic Defects Detected:\n" + "\n".join(f"- {d}" for d in deterministic_defects) + "\n\n"
            f"Complete Screenplay Compact JSON:\n{json.dumps(compact_scenes, indent=2, ensure_ascii=False)}\n"
        )

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
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

        timeout = int(os.getenv("XAI_JUDGE_TIMEOUT", "180"))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"]
            parsed = extract_json_payload(raw_text)
            parsed["raw_response"] = raw_text
            return parsed

    def _consult_gemini_critique(
        self,
        compact_scenes: list[dict[str, Any]],
        title: str,
        genre: str,
        deterministic_defects: list[str],
    ) -> dict[str, Any]:
        """Query Google Gemini via gemini_webapi (Chrome CDP port 9223) or enforce Fail-Closed gate."""
        prompt = (
            "You are Google DeepMind's Senior Visual Continuity & Screenplay Auditor for Google Flow CDP.\n"
            "Conduct a rigorous adversarial audit on the complete screenplay provided below.\n"
            "Evaluate:\n"
            "1. 2nd-person immersion and viral retention pacing.\n"
            "2. AI Video / Veo rendering safety (avoiding facial deformities, mirror reflections, UI text).\n"
            "3. Physical, thermodynamic, and causal realism.\n\n"
            f"Film Title: {title}\n"
            f"Genre: {genre}\n"
            f"Total Scenes: {len(compact_scenes)}\n"
            f"Pre-flagged Defects: {deterministic_defects}\n\n"
            f"Screenplay Compact JSON:\n{json.dumps(compact_scenes, indent=2, ensure_ascii=False)}\n\n"
            "Respond ONLY with valid JSON using this format:\n"
            "{\n"
            '  "screenplay_score": 88,\n'
            '  "grade": "Grade B",\n'
            '  "critique_text": "3-bullet adversarial executive critique...",\n'
            '  "defects": [\n'
            "    {\n"
            '      "scene_id": 5,\n'
            '      "category": "camera",\n'
            '      "responsible_skill": "director-of-photography",\n'
            '      "issue": "Description of defect",\n'
            '      "fix_instruction": "How to repair the prompt",\n'
            '      "rule_to_learn": "One-line rule to store in skill"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        # 1. Attempt connection via local gemini_webapi (Chrome CDP port 9223)
        try:
            from engine.providers.gemini_webapi import call_gemini_chat
            judge_model = self.gemini_model or "gemini-3.1-pro"

            raw_response = call_gemini_chat(prompt, model=judge_model, timeout=35.0)
            if raw_response and raw_response.strip():
                # Filter out error screens if any slipped through
                error_signatures = [
                    "Sorry, something went wrong",
                    "I'm having a hard time fulfilling your request",
                    "I encountered an error doing what you asked",
                    "I seem to be encountering an error",
                    "An internal error has occurred",
                ]
                if not any(err in raw_response for err in error_signatures):
                    parsed = extract_json_payload(raw_response)
                    if parsed:
                        parsed["raw_response"] = raw_response
                        return parsed
        except Exception as exc:
            logger.warning("gemini_webapi connection failed: %s", exc)

        # 2. Fail-Closed User Gate Check
        if not self.allow_deepmind_fallback:
            raise GeminiWebAPIUnavailableError(
                "gemini_webapi (Chrome CDP port 9223 / cookies.txt) connection failed or timed out. "
                "Fail-Closed Invariant Active: Silent fallback to DeepMind heuristic is strictly forbidden without user approval."
            )

        # 3. DeepMind Heuristic Fallback (Only executed when explicitly authorized)
        logger.info("Executing authorized DeepMind Heuristic Protocol fallback...")
        defects_list = []
        for d in deterministic_defects:
            defects_list.append({
                "scene_id": 1,
                "category": "schema",
                "responsible_skill": "viral-retention-director" if "pov" in d.lower() else "imagine-prompt-master",
                "issue": d,
                "fix_instruction": f"Resolve flagged issue: {d}",
                "rule_to_learn": "Maintain continuous strict adherence to production schema and guardrails.",
            })

        score = max(50, 100 - (len(deterministic_defects) * 8))
        return {
            "screenplay_score": score,
            "grade": "Grade A" if score >= 80 else "Grade B" if score >= 70 else "Grade F",
            "critique_text": f"DeepMind Heuristic Evaluator: Identified {len(deterministic_defects)} defect(s).",
            "defects": defects_list,
            "raw_response": f"[DeepMind Fallback Mode] Screenplay score: {score}/100",
        }
