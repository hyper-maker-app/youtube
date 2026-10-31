"""Screenplay Healer (Autonomous Closed-Loop Screenplay Auto-Healing Engine).

Takes a screenplay and an audit Scorecard from ScreenplayReviewer. If the score
is below the Grade A+ threshold (< 90/100), the Healer autonomously repairs
violating scenes (locally and/or via Grok LLM) until the screenplay achieves
score >= 90/100.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from engine.services.screenplay_reviewer import Scorecard, ScreenplayReviewer

logger = logging.getLogger(__name__)

_CTA_SUB_REGEX = re.compile(
    r"\s*(?:You must )?subscribe (?:to the channel and turn on notifications now )?(?:if you want to survive the next planetary simulation[.]*|to survive[.]*|for the next episode[.]*|to join the expedition[.]*|to the channel[.]*)?",
    re.IGNORECASE,
)


@dataclass
class HealResult:
    """Outcome of an autonomous healing session."""

    repaired_scenes: list[dict[str, Any]]
    final_scorecard: Scorecard
    iterations: int
    repair_log: list[str] = field(default_factory=list)


class ScreenplayHealer:
    """Autonomously heals defective scenes to meet the Grade A+ (>=90) threshold."""

    def __init__(
        self,
        reviewer: ScreenplayReviewer | None = None,
        xai_api_key: str | None = None,
        target_score: int = 90,
    ) -> None:
        self.reviewer = reviewer or ScreenplayReviewer(xai_api_key=xai_api_key)
        self.xai_api_key = xai_api_key
        self.target_score = target_score

    def heal(
        self,
        scenes: list[dict[str, Any]],
        title: str = "",
        genre: str = "catastrophe",
        max_iterations: int = 10,
    ) -> HealResult:
        """Run closed-loop review and auto-healing until score >= target_score."""
        current_scenes = copy.deepcopy(scenes)
        repair_log: list[str] = []
        iteration = 0

        scorecard = self.reviewer.review(current_scenes, title=title, genre=genre)
        repair_log.append(f"Initial Audit: {scorecard.total_score}/100 ({scorecard.grade}) with {len(scorecard.defects)} defect(s).")

        while scorecard.total_score < self.target_score and iteration < max_iterations:
            iteration += 1
            repair_log.append(f"--- Healing Round {iteration} (Current Score: {scorecard.total_score}/100) ---")

            # Perform programmatic and targeted fixes
            current_scenes, round_actions = self._apply_targeted_repairs(current_scenes, scorecard.defects)
            repair_log.extend(round_actions)

            # Re-evaluate
            scorecard = self.reviewer.review(current_scenes, title=title, genre=genre)
            repair_log.append(f"Round {iteration} Evaluation: {scorecard.total_score}/100 ({scorecard.grade}).")

            if scorecard.passed:
                repair_log.append(f"[OK] Target achieved: Screenplay certified {scorecard.grade} ({scorecard.total_score}/100)!")
                break

        return HealResult(
            repaired_scenes=current_scenes,
            final_scorecard=scorecard,
            iterations=iteration,
            repair_log=repair_log,
        )

    def _apply_targeted_repairs(
        self,
        scenes: list[dict[str, Any]],
        defects: list[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Apply targeted deterministic repairs to defective scenes."""
        repaired = copy.deepcopy(scenes)
        actions: list[str] = []
        total = len(repaired)

        for i, sc in enumerate(repaired):
            narration = sc.get("narration", "")
            prompt = sc.get("visual_prompt", "")
            micro_math = sc.get("micro_math", "")

            # 1. Fix CTA Isolation
            if i < total - 1:
                # Remove any CTA from non-final scenes
                if re.search(r"\b(subscribe|channel|notification|next episode|follow along)\b", narration, re.I):
                    cleaned_narration = re.sub(
                        r"(?:You must )?subscribe (?:to the channel and turn on notifications now )?(?:if you want to survive the next planetary simulation|to join our expedition into what remains of mankind|for the next simulation)?[.!]?",
                        "",
                        narration,
                        flags=re.I,
                    ).strip()
                    # Clean any trailing punctuation or whitespace
                    cleaned_narration = re.sub(r"\s+", " ", cleaned_narration).strip()
                    sc["narration"] = cleaned_narration
                    actions.append(f"Scene {i+1}: Stripped premature CTA from narration.")
            else:
                # Scene 38: Ensure single clean CTA in the final sentence
                if not re.search(r"\bsubscribe\b", narration, re.I):
                    # Append valid single CTA to final sentence
                    sc["narration"] = narration.rstrip(".! ") + ". You must subscribe to the channel now if you want to survive the next planetary simulation."
                    actions.append(f"Scene {total}: Added single canonical survival CTA to final sentence.")
                else:
                    # Clean multiple repeated CTAs in final scene
                    sentences = [st.strip() for st in re.split(r"[.!?]+", narration) if st.strip()]
                    non_cta_sentences = [st for st in sentences if not re.search(r"\b(subscribe|notification)\b", st, re.I)]
                    clean_final = ". ".join(non_cta_sentences) + ". You must subscribe to the channel now if you want to survive the next planetary simulation."
                    sc["narration"] = clean_final
                    actions.append(f"Scene {total}: Consolidated repeated CTAs into single final sentence.")

            # 2. Fix Veo Negative Guardrails in visual prompt
            cleaned_prompt = prompt
            # Mirror face fix
            if re.search(r"\b(?:mirror\s+(?:reflection|reflecting|face)|face\s+in\s+(?:the\s+)?(?:cracked\s+)?mirror|rearview\s+mirror\s+face)\b", cleaned_prompt, re.I):
                cleaned_prompt = re.sub(
                    r"\b(?:a\s+cracked\s+mirror\s+reflecting\s+your\s+terrified\s+face|mirror\s+reflection\s+of\s+your\s+face|face\s+in\s+the\s+cracked\s+mirror)\b",
                    "a frosted bunker blast door with silhouette backlighting, steam billowing against heavy steel hinges",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(
                    r"\bmirror\s+(?:reflection|face)\b",
                    "silhouetted viewpoint through reinforced quartz glass",
                    cleaned_prompt,
                    flags=re.I,
                )
                sc["visual_prompt"] = cleaned_prompt
                actions.append(f"Scene {i+1}: Repaired visual prompt: Replaced mirror facial reflection with atmospheric silhouette/viewport.")

            # Readable digital UI / digits fix
            if re.search(r"\b(?:(?:smart)?phone\s+screen|digital\s+(?:readout|display|clock|thermometer)|readable\s+(?:digits|numbers)|screen\s+reads)\b", cleaned_prompt, re.I):
                cleaned_prompt = re.sub(
                    r"(?:close-up\s+on\s+a\s+)?(?:smart)?phone\s+screen\s+[^\.,;]+(?:\d+[:\.]\d+\s*(?:am|pm)?|\d+)?",
                    "an analog brass pressure needle vibrating violently against frozen industrial pipes, frost crystals spreading across the gauge glass",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(
                    r"\b(?:smart)?phone\s+screen\b",
                    "analog brass pressure gauge",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(
                    r"\bdigital\s+(?:readout|display|clock|thermometer)\b",
                    "analog dial with mechanical needle",
                    cleaned_prompt,
                    flags=re.I,
                )
                sc["visual_prompt"] = cleaned_prompt
                actions.append(f"Scene {i+1}: Repaired visual prompt: Replaced readable digital UI with tactile analog gauge.")

            # Baked-in typography fix
            if re.search(r"\b(?:text\s+(?:overlay|reading|graphic)|subtitles\s+reading|sign\s+that\s+reads|words\s+reading|logo\s+on\s+screen)\b", cleaned_prompt, re.I):
                cleaned_prompt = re.sub(
                    r"(?:with\s+)?(?:text\s+overlay|subtitles|sign|words|logo)\s+(?:reading|showing)?\s*[\"'][^\"']+[\"']?",
                    "with stark atmospheric lighting across derelict metal plating",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(
                    r"\btext\s+overlay\b",
                    "ambient cinematic lighting",
                    cleaned_prompt,
                    flags=re.I,
                )
                sc["visual_prompt"] = cleaned_prompt
                actions.append(f"Scene {i+1}: Repaired visual prompt: Removed baked-in typography/text graphic.")

            # 3. Fix Thermodynamics
            if re.search(r"\bnitrogen\s+(?:snow|ice|slush|rain|frost)\b", sc.get("narration", "") + " " + sc.get("micro_math", ""), re.I):
                temp_match = re.search(r"-(?:[1-9]\d?|1[0-7]\d)\s*(?:°|deg|degrees)?\s*C\b", sc.get("narration", ""), re.I)
                if temp_match:
                    # Fix temperature to realistic nitrogen liquefaction threshold (-196°C) or change to carbon dioxide dry ice frost
                    sc["narration"] = re.sub(
                        r"nitrogen\s+snow",
                        "dense carbon dioxide dry ice frost",
                        sc["narration"],
                        flags=re.I,
                    )
                    actions.append(f"Scene {i+1}: Corrected thermodynamic phase error: Changed nitrogen snow to carbon dioxide dry ice frost at {temp_match.group(0)}.")

            # 4. Fix 2nd-Person Invariant
            narr = sc.get("narration", "").strip()
            if not narr.startswith(("You ", "Your ")):
                lower_narr = narr.lower()
                if lower_narr.startswith("outside,"):
                    sc["narration"] = f"You step outside as {narr[8:].strip()}"
                elif lower_narr.startswith("inside "):
                    sc["narration"] = f"You wait inside {narr[7:].strip()}"
                elif lower_narr.startswith(("day ", "week ", "month ", "year ")):
                    sc["narration"] = f"You endure {narr}"
                elif lower_narr.startswith("at minus "):
                    sc["narration"] = f"You shiver as {narr[0].lower() + narr[1:]}"
                else:
                    first_char_lower = narr[0].lower() + narr[1:] if len(narr) > 1 else narr
                    sc["narration"] = f"You watch as {first_char_lower}"
                actions.append(f"Scene {i+1}: Enforced 2nd-person invariant.")

            # 5. Fix Causality (Scene 1 & 2 photon delay)
            if i == 0 and "sun" in narr.lower() and ("disappear" in narr.lower() or "vanish" in narr.lower()):
                if not any(k in narr.lower() for k in ["8 minute", "8.3", "500 second", "delay", "speed of light", "last photon"]):
                    sc["narration"] = (
                        "You stand beneath a warm blue sky, completely unaware that eight minutes and twenty seconds ago, the Sun ceased to exist. "
                        "The final wave of photons is about to pass before total, eternal darkness claims the Earth."
                    )
                    actions.append("Scene 1: Repaired causality: Grounded Sun disappearance with 8.3-minute speed-of-light photon delay.")

        return repaired, actions
