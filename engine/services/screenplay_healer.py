"""Screenplay Healer (Autonomous Closed-Loop Full-Screenplay Context-Aware Healer).

Takes a screenplay and an audit Scorecard from ScreenplayReviewer.
If the score is below the Grade A+ threshold (< 90/100) or contains critical defects:
1. Full-Screenplay Context-Aware Healing: Reads all 38 scenes in compact format to maintain
   unbroken chronological arc and continuity while rewriting flagged defective scenes via Grok LLM.
2. Lightweight Deterministic Polishing: Cleans syntax, premature CTAs, and POV prefixes.
3. Optional skill reinforcement: persists learned rules only with explicit opt-in.
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
    build_compact_scenes_payload,
    extract_json_payload,
)
from engine.services.skill_reinforcement import SkillReinforcementService

logger = logging.getLogger(__name__)


@dataclass
class RoundRecord:
    """Record of a single adversarial debate and auto-heal round."""

    iteration: int
    score_before: int
    grade_before: str
    grok_score_before: int | None
    gemini_score_before: int | None
    defects_before: list[str] = field(default_factory=list)
    ai_critique_before: str | None = None
    repaired_scene_ids: list[str | int] = field(default_factory=list)
    repair_actions: list[str] = field(default_factory=list)
    reinforcement_actions: list[str] = field(default_factory=list)
    score_after: int = 0
    grade_after: str = "Grade F"
    grok_score_after: int | None = None
    gemini_score_after: int | None = None
    defects_after: list[str] = field(default_factory=list)
    ai_critique_after: str | None = None


@dataclass
class HealResult:
    """Outcome of an autonomous healing session."""

    repaired_scenes: list[dict[str, Any]]
    final_scorecard: Scorecard
    iterations: int
    repair_log: list[str] = field(default_factory=list)
    reinforcement_records: list[dict[str, Any]] = field(default_factory=list)
    round_records: list[RoundRecord] = field(default_factory=list)


class ScreenplayHealer:
    """Autonomously heals defective scenes with full-screenplay context to meet Grade A+."""

    def __init__(
        self,
        reviewer: ScreenplayReviewer | None = None,
        xai_api_key: str | None = None,
        target_score: int = 90,
        grok_model: str | None = None,
        allow_skill_writes: bool = False,
    ) -> None:
        self.xai_api_key = xai_api_key if xai_api_key is not None else os.getenv("XAI_API_KEY")
        self.grok_model = grok_model or os.getenv("XAI_MODEL") or "grok-4.20-0309-non-reasoning"
        self.reviewer = reviewer or ScreenplayReviewer(xai_api_key=self.xai_api_key, grok_model=self.grok_model)
        self.target_score = target_score
        self.reinforcement_service = SkillReinforcementService(allow_writes=allow_skill_writes)

    def _extract_target_scene_ids(self, scorecard: Scorecard, total_scenes: int) -> list[int]:
        """Extract explicit 1-based scene numbers from structured defects and text defects."""
        scene_ids: set[int] = set()
        for sd in scorecard.structured_defects:
            sid = sd.get("scene_id")
            if sid is not None:
                try:
                    num = int(re.sub(r"\D", "", str(sid)))
                    if 1 <= num <= total_scenes:
                        scene_ids.add(num)
                except ValueError:
                    pass

        for d in scorecard.defects:
            for match in re.finditer(r"\bscene[s]?\s*(\d+)", d, re.IGNORECASE):
                try:
                    num = int(match.group(1))
                    if 1 <= num <= total_scenes:
                        scene_ids.add(num)
                except ValueError:
                    pass

        sorted_ids = sorted(list(scene_ids))
        # Prioritize top 8 defective scenes per round to prevent LLM output token exhaustion
        return sorted_ids[:8]

    def heal(
        self,
        scenes: list[dict[str, Any]],
        title: str = "",
        genre: str = "catastrophe",
        max_iterations: int = 5,
        consult_ai: bool = False,
        initial_scorecard: Scorecard | None = None,
    ) -> HealResult:
        """Run closed-loop review, full-context healing, and skill reinforcement."""
        current_scenes = copy.deepcopy(scenes)
        repair_log: list[str] = []
        reinforcement_records: list[dict[str, Any]] = []
        round_records: list[RoundRecord] = []
        iteration = 0

        if initial_scorecard is not None:
            scorecard = initial_scorecard
        else:
            scorecard = self.reviewer.review(current_scenes, title=title, genre=genre, consult_ai=consult_ai)

        repair_log.append(
            f"Initial Audit: {scorecard.total_score}/100 ({scorecard.grade}) with {len(scorecard.defects)} defect(s)."
        )

        while (not scorecard.passed or scorecard.total_score < self.target_score) and iteration < max_iterations:
            if (getattr(self.reviewer, "screenplay_mode", "strict-checklist") == "holistic"
                    and not scorecard.structured_defects and scorecard.defects
                    and all(d.startswith(("Grok judge unavailable or invalid:",
                                          "Gemini judge unavailable or invalid:",
                                          "Holistic review is incomplete without both judges",
                                          "World-law context unavailable:",
                                          "No director skill matches", "No structured world rules"))
                            for d in scorecard.defects)):
                repair_log.append("Review infrastructure or rule context is unavailable; screenplay was not rewritten.")
                break
            iteration += 1
            round_pre_scenes = copy.deepcopy(current_scenes)
            round_pre_scorecard = copy.deepcopy(scorecard)
            round_actions: list[str] = []
            round_reinf_actions: list[str] = []
            round_repaired_ids: list[str | int] = []

            repair_log.append(f"--- Healing Round {iteration} (Current Score: {scorecard.total_score}/100) ---")

            # 1. Reinforce skills from structured defects flagged by judges
            if scorecard.structured_defects:
                reinf_applied = self.reinforcement_service.reinforce_from_defects(scorecard.structured_defects)
                for r in reinf_applied:
                    if r.get("applied"):
                        msg = f"Skill Reinforcement: Added learned rule to {r.get('skill_slug')} ({r.get('line_count')} lines)."
                        repair_log.append(msg)
                        round_reinf_actions.append(msg)
                        reinforcement_records.append(r)

            # 2. Perform Full-Screenplay Context-Aware LLM Healing if API key present
            llm_healed = False
            if self.xai_api_key and scorecard.defects:
                try:
                    healed_scenes, llm_actions, rep_ids = self._heal_with_full_context_grok(
                        current_scenes, scorecard, title=title, genre=genre
                    )
                    if healed_scenes:
                        current_scenes = healed_scenes
                        repair_log.extend(llm_actions)
                        round_actions.extend(llm_actions)
                        round_repaired_ids.extend(rep_ids)
                        llm_healed = True
                except Exception as exc:
                    logger.warning("Full-context Grok healing round failed: %s", exc)

            # 3. Deterministic Safety Polish (CTA isolation, 2nd-person, Veo safety)
            if getattr(self.reviewer, "screenplay_mode", "strict-checklist") == "holistic":
                det_actions = []
            else:
                current_scenes, det_actions = self._apply_deterministic_polishing(current_scenes, scorecard.defects)
            repair_log.extend(det_actions)
            round_actions.extend(det_actions)

            # 4. Re-evaluate
            post_scorecard = self.reviewer.review(current_scenes, title=title, genre=genre, consult_ai=consult_ai)
            if getattr(self.reviewer, "screenplay_mode", "strict-checklist") == "holistic":
                previous_critical = {(str(d.get("scene_id")), d.get("rule_id")) for d in scorecard.structured_defects if d.get("severity") == "critical"}
                current_critical = {(str(d.get("scene_id")), d.get("rule_id")) for d in post_scorecard.structured_defects if d.get("severity") == "critical"}
                if current_critical - previous_critical or (len(current_scenes) != len(round_pre_scenes)):
                    current_scenes = round_pre_scenes
                    post_scorecard = round_pre_scorecard
                    repair_log.append("Rejected repair introducing a critical defect or changing scene count.")
            repair_log.append(f"Round {iteration} Evaluation: {post_scorecard.total_score}/100 ({post_scorecard.grade}).")

            # 5. Record complete round progression
            round_rec = RoundRecord(
                iteration=iteration,
                score_before=round_pre_scorecard.total_score,
                grade_before=round_pre_scorecard.grade,
                grok_score_before=round_pre_scorecard.grok_score,
                gemini_score_before=round_pre_scorecard.gemini_score,
                defects_before=round_pre_scorecard.defects,
                ai_critique_before=round_pre_scorecard.ai_critique,
                repaired_scene_ids=round_repaired_ids,
                repair_actions=round_actions,
                reinforcement_actions=round_reinf_actions,
                score_after=post_scorecard.total_score,
                grade_after=post_scorecard.grade,
                grok_score_after=post_scorecard.grok_score,
                gemini_score_after=post_scorecard.gemini_score,
                defects_after=post_scorecard.defects,
                ai_critique_after=post_scorecard.ai_critique,
            )
            round_records.append(round_rec)
            scorecard = post_scorecard

            if scorecard.passed and scorecard.total_score >= self.target_score:
                repair_log.append(f"[OK] Target achieved: Screenplay certified {scorecard.grade} ({scorecard.total_score}/100)!")
                break

        return HealResult(
            repaired_scenes=current_scenes,
            final_scorecard=scorecard,
            iterations=iteration,
            repair_log=repair_log,
            reinforcement_records=reinforcement_records,
            round_records=round_records,
        )

    def _heal_with_full_context_grok(
        self,
        scenes: list[dict[str, Any]],
        scorecard: Scorecard,
        title: str,
        genre: str,
    ) -> tuple[list[dict[str, Any]], list[str], list[str | int]]:
        """Rewrite defective scenes while providing all scenes as context to maintain continuity."""
        compact_all = build_compact_scenes_payload(scenes)
        model_name = self.grok_model or os.getenv("XAI_MODEL") or "grok-4.20-0309-non-reasoning"
        try:
            from tools.models import _CHAT_ALIAS_MAP, resolve_chat_model
            if model_name.strip().lower() in _CHAT_ALIAS_MAP:
                model_name = resolve_chat_model(model_name)
        except Exception:
            if model_name in ("grok-4.20-non-reasoning", "grok-4.20"):
                model_name = "grok-4.20-0309-non-reasoning"
        target_scene_ids = self._extract_target_scene_ids(scorecard, len(scenes))
        if not target_scene_ids:
            if getattr(self.reviewer, "screenplay_mode", "strict-checklist") == "holistic":
                raise ValueError("Holistic repair requires an identified target scene")
            target_scene_ids = [len(scenes)]  # Default to final scene if none parsed

        from engine.services.skill_loader import get_skill_loader
        skill_prompt = get_skill_loader().build_unified_system_prompt(
            title=title, genre=genre,
            duration=max(1,int(sum(float(scene.get("duration",0)) for scene in scenes))),
            aspect=getattr(self.reviewer, "aspect", "16:9"),
        )
        if getattr(self.reviewer, "short_test", False):
            for slug in ("catastrophe-director", "viral-retention-director"):
                instructions = get_skill_loader().load_skill_instructions(slug, max_chars=0)
                test_rule = next((line for line in instructions.splitlines() if line.startswith("For an explicitly marked short integration test only,")), "")
                if not test_rule:
                    raise ValueError(f"Short-test skill contract is missing: {slug}")
                skill_prompt += "\nTEST-ONLY CONTRACT (authoritative for this run):\n" + test_rule
        prompt = json.dumps({
            "title": title, "genre": genre,
            "defects": scorecard.defects,
            "scenes": compact_all,
            "required_scene_ids": target_scene_ids,
            "response_schema": {"repaired_scenes": [{"scene_id": "existing scene identifier",
                "narration": "string", "visual_prompt": "string", "motion_prompt": "string",
                "micro_math": "string", "is_data_broll": "boolean", "template_name": "string", "data_payload": "object"}]},
        },ensure_ascii=False)

        system_instruction = (
            "You are the Lead Screenplay Repair Specialist for Grok Imagine Cinematic Studio.\n"
            "Your task is to repair ONLY the scenes flagged with defects, ensuring unbroken chronological arc and continuity.\n"
            "You MUST respond ONLY with a raw JSON object containing the repaired scenes under the key 'repaired_scenes'.\n"
            "Do NOT output markdown titles, introductory prose, or conversational filler. Output pure JSON only.\n\n"
            + skill_prompt
        )
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": system_instruction,
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        req = urllib.request.Request(
            f"{((os.getenv('XAI_API_BASE') or '').strip().rstrip('/') or 'https://api.x.ai/v1')}/chat/completions",
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
            return scenes, [], []

        merged = copy.deepcopy(scenes)
        actions = []
        repaired_ids = []

        def _norm_id(raw_id: Any) -> str:
            s = str(raw_id).strip().lower()
            digits = re.findall(r"\d+", s)
            if digits:
                return f"scene_{int(digits[0]):02d}"
            return s

        scene_map = {}
        for idx, sc in enumerate(merged):
            sid = sc.get("scene_id") or sc.get("id") or f"scene_{idx+1:02d}"
            scene_map[_norm_id(sid)] = idx
            scene_map[str(sid)] = idx
            scene_map[str(idx + 1)] = idx

        for rep in repaired_list:
            sid = rep.get("scene_id") or rep.get("id")
            norm_target = _norm_id(sid)
            if getattr(self.reviewer, "screenplay_mode", "strict-checklist") == "holistic":
                allowed_indices = {scene_map.get(_norm_id(target), scene_map.get(str(target))) for target in target_scene_ids}
                if scene_map.get(norm_target, scene_map.get(str(sid))) not in allowed_indices:
                    raise ValueError("Healer returned an untargeted scene")
            if norm_target in scene_map or str(sid) in scene_map:
                idx = scene_map.get(norm_target, scene_map.get(str(sid)))
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
                for key in ("motion_prompt", "is_data_broll", "template_name", "data_payload"):
                    if key in rep:
                        orig[key] = rep[key]
                scene_num = orig.get("scene_id", idx + 1)
                repaired_ids.append(scene_num)
                actions.append(f"Grok Context-Healer: Successfully repaired Scene {scene_num} with full continuity.")

        return merged, actions, repaired_ids

    def _apply_deterministic_polishing(
        self,
        scenes: list[dict[str, Any]],
        defects: list[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Report needed creative repairs without substituting engine-authored prose."""
        from engine.services.screenplay_linter import lint_scenes
        return lint_scenes(scenes)
