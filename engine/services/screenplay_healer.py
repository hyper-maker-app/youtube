"""Screenplay Healer (Autonomous Closed-Loop Full-Screenplay Context-Aware Healer).

Takes a screenplay and an audit Scorecard from ScreenplayReviewer.
If the score is below the Grade A+ threshold (< 90/100) or contains critical defects:
1. Full-Screenplay Context-Aware Healing: Reads all 38 scenes in compact format to maintain
   unbroken chronological arc and continuity while rewriting flagged defective scenes via Grok LLM.
2. Lightweight Deterministic Polishing: Cleans syntax, premature CTAs, and POV prefixes.
3. Closed-Loop Skill Reinforcement: Automatically persists learned rules into matching
   .grok/skills/<slug>/SKILL.md department guidelines under the <500-line cap.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any
import urllib.request

from engine.services.screenplay_reviewer import (
    Scorecard,
    ScreenplayReviewer,
    _CTA_PATTERN,
    build_compact_scenes_payload,
    extract_json_payload,
)
from engine.services.skill_reinforcement import SkillReinforcementService

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
    reinforcement_records: list[dict[str, Any]] = field(default_factory=list)


class ScreenplayHealer:
    """Autonomously heals defective scenes with full-screenplay context to meet Grade A+."""

    def __init__(
        self,
        reviewer: ScreenplayReviewer | None = None,
        xai_api_key: str | None = None,
        target_score: int = 90,
    ) -> None:
        self.xai_api_key = xai_api_key or os.getenv("XAI_API_KEY")
        self.reviewer = reviewer or ScreenplayReviewer(xai_api_key=self.xai_api_key)
        self.target_score = target_score
        self.reinforcement_service = SkillReinforcementService()

    def heal(
        self,
        scenes: list[dict[str, Any]],
        title: str = "",
        genre: str = "catastrophe",
        max_iterations: int = 5,
        consult_ai: bool = False,
    ) -> HealResult:
        """Run closed-loop review, full-context healing, and skill reinforcement."""
        current_scenes = copy.deepcopy(scenes)
        repair_log: list[str] = []
        reinforcement_records: list[dict[str, Any]] = []
        iteration = 0

        scorecard = self.reviewer.review(current_scenes, title=title, genre=genre, consult_ai=consult_ai)
        repair_log.append(
            f"Initial Audit: {scorecard.total_score}/100 ({scorecard.grade}) with {len(scorecard.defects)} defect(s)."
        )

        while (not scorecard.passed or scorecard.total_score < self.target_score) and iteration < max_iterations:
            iteration += 1
            repair_log.append(f"--- Healing Round {iteration} (Current Score: {scorecard.total_score}/100) ---")

            # 1. Reinforce skills from structured defects flagged by judges
            if scorecard.structured_defects:
                reinf_applied = self.reinforcement_service.reinforce_from_defects(scorecard.structured_defects)
                for r in reinf_applied:
                    if r.get("applied"):
                        msg = f"Skill Reinforcement: Added learned rule to {r.get('skill_slug')} ({r.get('line_count')} lines)."
                        repair_log.append(msg)
                        reinforcement_records.append(r)

            # 2. Perform Full-Screenplay Context-Aware LLM Healing if API key present
            llm_healed = False
            if self.xai_api_key and scorecard.defects:
                try:
                    healed_scenes, llm_actions = self._heal_with_full_context_grok(
                        current_scenes, scorecard, title=title, genre=genre
                    )
                    if healed_scenes:
                        current_scenes = healed_scenes
                        repair_log.extend(llm_actions)
                        llm_healed = True
                except Exception as exc:
                    logger.warning("Full-context Grok healing round failed: %s", exc)

            # 3. Deterministic Safety Polish (CTA isolation, 2nd-person, Veo safety)
            current_scenes, det_actions = self._apply_deterministic_polishing(current_scenes, scorecard.defects)
            repair_log.extend(det_actions)

            # 4. Re-evaluate
            scorecard = self.reviewer.review(current_scenes, title=title, genre=genre, consult_ai=consult_ai)
            repair_log.append(f"Round {iteration} Evaluation: {scorecard.total_score}/100 ({scorecard.grade}).")

            if scorecard.passed and scorecard.total_score >= self.target_score:
                repair_log.append(f"[OK] Target achieved: Screenplay certified {scorecard.grade} ({scorecard.total_score}/100)!")
                break

        return HealResult(
            repaired_scenes=current_scenes,
            final_scorecard=scorecard,
            iterations=iteration,
            repair_log=repair_log,
            reinforcement_records=reinforcement_records,
        )

    def _heal_with_full_context_grok(
        self,
        scenes: list[dict[str, Any]],
        scorecard: Scorecard,
        title: str,
        genre: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Rewrite defective scenes while providing all 38 scenes as context to maintain continuity."""
        compact_all = build_compact_scenes_payload(scenes)
        model_name = os.getenv("XAI_CHAT_MODEL") or os.getenv("XAI_MODEL") or "grok-4.20-0309-non-reasoning"

        prompt = (
            "You are the Lead Screenplay Director and Continuity Guardian for Grok Imagine Cinematic Studio.\n"
            "Below is the COMPLETE screenplay (all scenes) for reference, followed by the adversarial review defects.\n\n"
            f"Film Title: {title}\n"
            f"Genre: {genre}\n"
            f"Defects Identified by Dual-Judge Review:\n"
            + "\n".join(f"- {d}" for d in scorecard.defects)
            + "\n\n"
            f"Complete Screenplay Context (All {len(scenes)} Scenes):\n"
            f"{json.dumps(compact_all, indent=2, ensure_ascii=False)}\n\n"
            "TASK:\n"
            "Rewrite ONLY the defective scenes to fully eliminate every flagged defect.\n"
            "Crucial Continuity Rules:\n"
            "1. You MUST read the full screenplay context so that repaired scenes perfectly bridge previous and subsequent scenes.\n"
            "2. Maintain strict 2nd-person singular perspective ('You watch...', 'You tighten...').\n"
            "3. Maintain Veo safety (zero mirror reflections, zero readable UI screens, zero baked typography).\n"
            "4. Confine subscribe CTA strictly to the final sentence of the final scene.\n\n"
            "Respond ONLY with valid JSON in this exact structure:\n"
            "{\n"
            '  "repaired_scenes": [\n'
            "    {\n"
            '      "scene_id": 12,\n'
            '      "narration": "Updated narration starting with You...",\n'
            '      "visual_prompt": "Updated visual prompt...",\n'
            '      "camera": {"angle": "low-angle", "movement": "tracking"},\n'
            '      "micro_math": "Tangible micro-survival detail",\n'
            '      "sfx": "Layered foley directive"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a master cinematic screenwriter. Heal the screenplay with full contextual awareness.",
                },
                {"role": "user", "content": prompt},
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

        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"]
            parsed = extract_json_payload(raw_text)

        repaired_list = parsed.get("repaired_scenes", [])
        if not repaired_list:
            return scenes, []

        merged = copy.deepcopy(scenes)
        actions = []

        scene_map = {sc.get("scene_id") or sc.get("id"): idx for idx, sc in enumerate(merged)}

        for rep in repaired_list:
            sid = rep.get("scene_id") or rep.get("id")
            if sid in scene_map:
                idx = scene_map[sid]
                orig = merged[idx]
                if rep.get("narration"):
                    orig["narration"] = rep["narration"]
                if rep.get("visual_prompt"):
                    orig["visual_prompt"] = rep["visual_prompt"]
                if rep.get("camera"):
                    orig["camera"] = rep["camera"]
                if rep.get("micro_math"):
                    orig["micro_math"] = rep["micro_math"]
                if rep.get("sfx"):
                    orig["sfx"] = rep["sfx"]
                actions.append(f"Grok Context-Healer: Successfully repaired Scene {sid} with full continuity.")

        return merged, actions

    def _apply_deterministic_polishing(
        self,
        scenes: list[dict[str, Any]],
        defects: list[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Apply deterministic syntactic and prompt polishing."""
        repaired = copy.deepcopy(scenes)
        actions: list[str] = []
        total = len(repaired)

        for i, sc in enumerate(repaired):
            narration = sc.get("narration", "")
            prompt = sc.get("visual_prompt", "")

            # 1. Fix CTA Isolation
            if i < total - 1:
                if _CTA_PATTERN.search(narration):
                    sentences = [st.strip() for st in re.split(r"(?<=[.!?])\s+", narration) if st.strip()]
                    non_cta = [st for st in sentences if not _CTA_PATTERN.search(st)]
                    if non_cta:
                        cleaned = " ".join(non_cta)
                    else:
                        cleaned = "You observe the shifting horizon in tense silence."
                    # Remove any dangling inline fragments
                    cleaned = re.sub(r"[,\-\s]*(?:please\s+)?(?:subscribe|subscribing|follow along|turn on notifications|comment below)[^.!?]*", "", cleaned, flags=re.I)
                    cleaned = re.sub(r"[,\-\s]*to the channel[^.!?]*", "", cleaned, flags=re.I)
                    cleaned = re.sub(r"\s+", " ", cleaned).strip()
                    sc["narration"] = cleaned
                    actions.append(f"Scene {i+1}: Stripped premature CTA from narration.")
            else:
                sentences = [st.strip() for st in re.split(r"(?<=[.!?])\s+", narration) if st.strip()]
                non_cta = [st for st in sentences if not _CTA_PATTERN.search(st)]
                clean_final = " ".join(non_cta).strip()
                if clean_final and not clean_final.endswith((".", "!", "?")):
                    clean_final += "."
                canonical_cta = "You must subscribe to the channel now if you want to survive the next planetary simulation."
                if clean_final:
                    clean_final = f"{clean_final} {canonical_cta}"
                else:
                    clean_final = canonical_cta
                sc["narration"] = clean_final.strip()
                actions.append(f"Scene {total}: Enforced single canonical survival CTA in final sentence.")

            # 2. Fix Veo Negative Guardrails in visual prompt
            cleaned_prompt = prompt
            if re.search(r"\b(?:mirror\s+(?:reflection|reflecting|face)|face\s+in\s+(?:the\s+)?(?:cracked\s+)?mirror|rearview\s+mirror\s+face)\b", cleaned_prompt, re.I):
                cleaned_prompt = re.sub(
                    r"\b(?:a\s+cracked\s+mirror\s+reflecting\s+your\s+terrified\s+face|mirror\s+reflection\s+of\s+your\s+face|face\s+in\s+the\s+cracked\s+mirror)\b",
                    "a frosted bunker blast door with silhouette backlighting, steam billowing against heavy steel hinges",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(r"\bmirror\s+(?:reflection|face)\b", "silhouetted viewpoint through reinforced quartz glass", cleaned_prompt, flags=re.I)
                sc["visual_prompt"] = cleaned_prompt
                actions.append(f"Scene {i+1}: Replaced mirror reflection with atmospheric silhouette/viewport.")

            if re.search(r"\b(?:(?:smart)?phone\s+screen|digital\s+(?:readout|display|clock|thermometer)|readable\s+(?:digits|numbers)|screen\s+reads)\b", cleaned_prompt, re.I):
                cleaned_prompt = re.sub(
                    r"(?:close-up\s+on\s+a\s+)?(?:smart)?phone\s+screen\s+[^\.,;]+(?:\d+[:\.]\d+\s*(?:am|pm)?|\d+)?",
                    "an analog brass pressure needle vibrating violently against frozen industrial pipes, frost crystals spreading across the gauge glass",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(r"\b(?:smart)?phone\s+screen\b", "analog brass pressure gauge", cleaned_prompt, flags=re.I)
                cleaned_prompt = re.sub(r"\bdigital\s+(?:readout|display|clock|thermometer)\b", "analog dial with mechanical needle", cleaned_prompt, flags=re.I)
                cleaned_prompt = re.sub(r"\b(?:no\s+|zero\s+|without\s+)?readable\s+(?:numbers|digits)\b", "analog mechanical dials", cleaned_prompt, flags=re.I)
                sc["visual_prompt"] = cleaned_prompt
                actions.append(f"Scene {i+1}: Replaced readable digital UI with tactile analog gauge.")

            if re.search(r"\b(?:text\s+(?:overlay|reading|graphic)|subtitles\s+reading|sign\s+that\s+reads|words\s+reading|logo\s+on\s+screen)\b", cleaned_prompt, re.I):
                cleaned_prompt = re.sub(
                    r"(?:with\s+)?(?:text\s+overlay|subtitles|sign|words|logo)\s+(?:reading|showing)?\s*[\"'][^\"']+[\"']?",
                    "with stark atmospheric lighting across derelict metal plating",
                    cleaned_prompt,
                    flags=re.I,
                )
                cleaned_prompt = re.sub(r"\btext\s+overlay\b", "ambient cinematic lighting", cleaned_prompt, flags=re.I)
                sc["visual_prompt"] = cleaned_prompt
                actions.append(f"Scene {i+1}: Removed baked-in typography/text graphic.")

            # 3. Fix 2nd-Person Invariant
            narr = sc.get("narration", "").strip()
            if not narr.startswith(("You ", "Your ")):
                lower_narr = narr.lower()
                if lower_narr.startswith("outside,"):
                    sc["narration"] = f"You step outside as {narr[8:].strip()}"
                elif lower_narr.startswith("outside "):
                    sc["narration"] = f"You look as {narr[0].lower() + narr[1:]}"
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

            # 4. Universal physical/temperature fixes
            if re.search(r"\b(?:nitrogen\b[^\.\,\;]*\b(?:liquef\w*|rain|snow|ice|slush|frost)|liquid\s+nitrogen)\b", sc.get("narration", "") + " " + sc.get("micro_math", ""), re.I):
                temp_match = re.search(r"-(?:[1-9]\d?|1[0-8]\d|19[0-5])\s*(?:°|deg|degrees)?\s*C\b", sc.get("narration", ""), re.I) or re.search(r"\bminus\s+(?:1[0-8]\d|19[0-5]|[1-9]\d?)\s+(?:°|deg|degrees)?\s*(?:C|celsius)\b", sc.get("narration", ""), re.I)
                if temp_match:
                    if re.search(r"\b(?:snow|ice|slush|frost)\b", sc.get("narration", ""), re.I):
                        sc["narration"] = re.sub(r"nitrogen\s+(?:snow|ice|slush|frost)", "dense carbon dioxide dry ice frost", sc["narration"], flags=re.I)
                        actions.append(f"Scene {i+1}: Corrected nitrogen snow to carbon dioxide dry ice frost at {temp_match.group(0)}.")
                    else:
                        sc["narration"] = re.sub(r"-(?:[1-9]\d?|1[0-8]\d|19[0-5])\s*(?:°|deg|degrees)?\s*C\b", "-196°C", sc["narration"], flags=re.I)
                        actions.append(f"Scene {i+1}: Corrected nitrogen liquefaction temperature to physical threshold -196°C.")

        return repaired, actions
