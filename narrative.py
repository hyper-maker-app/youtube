"""Event-driven storyboard contracts for short-form documentary runs.

The timeline decides *how many* native clips a provider produces.  This module decides
whether those clips form a story before the pipeline spends credits on images or motion.
It intentionally contains no provider-specific prompt text, so Flow and Fal receive the
same causal scene plan.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable


NARRATIVE_TEMPLATES = ("mechanism_reveal", "mystery_escalation")
CAPTION_SAFE_ZONES = (
    "top", "upper_left", "upper_center", "upper_right", "left", "right",
)
PROOF_OVERLAY_TYPES = ("arrow", "trajectory_line", "outline", "measurement", "force_line")
LIGHTHOUSE_ANCHOR_VIEWS = (
    "exterior", "lantern_room", "tower_interior", "lighthouse_attached_mechanism",
)

# These are presentation instructions, not physical proof. A relay, filament, lens,
# cable, or changing sunlight can prove an event; a dashboard cannot.
PROHIBITED_PRESENTATION_TERMS = (
    "hud", "ui", "gauge", "meter", "charge bar", "percentage", "percent",
    "indicator", "chart", "dashboard", "readable label", "readable labels",
    "visible text", "on-screen text", "caption", "captions", "subtitle",
    "subtitles", "watermark",
)


def has_prohibited_presentation(value: object) -> str | None:
    """Return the prohibited presentation token requested by authored prose, if any."""
    text = str(value or "").casefold()
    for term in PROHIBITED_PRESENTATION_TERMS:
        # ``ui`` must mean the standalone presentation term, never the middle of
        # a legitimate physical word such as ``circuit``.
        pattern = r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)"
        if re.search(pattern, text):
            return term
    return None


@dataclass
class StoryBeat:
    """The information and state transition carried by one spoken beat."""

    index: int
    role: str
    question_in: str
    answer_out: str
    cause: str
    visible_event: str
    state_before: str
    state_after: str
    new_information: str
    open_loop: str
    payoff_link: str

    @classmethod
    def from_dict(cls, raw: dict, index: int = 1) -> "StoryBeat":
        return cls(
            index=int(raw.get("index") or index),
            role=str(raw.get("role") or "bridge"),
            question_in=str(raw.get("question_in") or "").strip(),
            answer_out=str(raw.get("answer_out") or "").strip(),
            cause=str(raw.get("cause") or "").strip(),
            visible_event=str(raw.get("visible_event") or "").strip(),
            state_before=str(raw.get("state_before") or "").strip(),
            state_after=str(raw.get("state_after") or "").strip(),
            new_information=str(raw.get("new_information") or "").strip(),
            open_loop=str(raw.get("open_loop") or "").strip(),
            payoff_link=str(raw.get("payoff_link") or "").strip(),
        )


@dataclass
class SceneCard:
    """One continuous provider-native shot, expressed as a causal visual event."""

    scene_id: str
    purpose: str
    entry_state: str
    exit_state: str
    dominant_event: str
    proof_on_screen: str
    causal_parent_scene_id: str
    next_question: str
    asset_states: dict[str, str] = field(default_factory=dict)
    caption_safe_zone: str = "upper_center"
    semantic_expected_result: str = ""
    # Overlay is forbidden unless this explicit, persisted proof specification exists.
    # Allowed fields are validated by the Vertex adapter, not inferred from prose.
    proof_overlay: dict[str, str] = field(default_factory=dict)
    # Empty retains persisted V1/V2 SceneCards. Lighthouse V3 requires this field.
    anchor_view: str = ""

    @classmethod
    def from_dict(cls, raw: dict, scene_id: str) -> "SceneCard":
        asset_states = raw.get("asset_states") or {}
        if not isinstance(asset_states, dict):
            asset_states = {}
        return cls(
            scene_id=str(raw.get("scene_id") or scene_id),
            purpose=str(raw.get("purpose") or "").strip(),
            entry_state=str(raw.get("entry_state") or "").strip(),
            exit_state=str(raw.get("exit_state") or "").strip(),
            dominant_event=str(raw.get("dominant_event") or "").strip(),
            proof_on_screen=str(raw.get("proof_on_screen") or "").strip(),
            causal_parent_scene_id=str(raw.get("causal_parent_scene_id") or "").strip(),
            next_question=str(raw.get("next_question") or "").strip(),
            asset_states={str(k): str(v) for k, v in asset_states.items() if str(k).strip() and str(v).strip()},
            caption_safe_zone=str(raw.get("caption_safe_zone") or "upper_center").strip(),
            semantic_expected_result=str(raw.get("semantic_expected_result") or raw.get("exit_state") or "").strip(),
            anchor_view=str(raw.get("anchor_view") or "").strip(),
            proof_overlay={
                str(k): str(v).strip() for k, v in (raw.get("proof_overlay") or {}).items()
                if str(k).strip() and str(v).strip()
            } if isinstance(raw.get("proof_overlay"), dict) else {},
        )


@dataclass
class NarrativePlan:
    """Persisted, provider-neutral retention plan for a new run."""

    template: str
    viewer_question: str
    hook_image: str
    stake: str
    turn_or_constraint: str
    reversal: str
    final_payoff: str
    beats: list[StoryBeat] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "viewer_question": self.viewer_question,
            "hook_image": self.hook_image,
            "stake": self.stake,
            "turn_or_constraint": self.turn_or_constraint,
            "reversal": self.reversal,
            "final_payoff": self.final_payoff,
            "beats": [asdict(beat) for beat in self.beats],
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> "NarrativePlan | None":
        if not isinstance(raw, dict):
            return None
        beats_raw = raw.get("beats") or raw.get("story_beats") or []
        if not isinstance(beats_raw, list):
            beats_raw = []
        return cls(
            template=str(raw.get("template") or "").strip(),
            viewer_question=str(raw.get("viewer_question") or "").strip(),
            hook_image=str(raw.get("hook_image") or "").strip(),
            stake=str(raw.get("stake") or "").strip(),
            turn_or_constraint=str(raw.get("turn_or_constraint") or raw.get("false_assumption") or "").strip(),
            reversal=str(raw.get("reversal") or "").strip(),
            final_payoff=str(raw.get("final_payoff") or "").strip(),
            beats=[StoryBeat.from_dict(item, i + 1) for i, item in enumerate(beats_raw) if isinstance(item, dict)],
        )


class NarrativeQualityGate:
    """Deterministic pre-credit audit of a causal scene plan.

    The gate distinguishes an actionable failure from a subjective visual preference.  It
    is intentionally strict about information flow: a pretty close-up that does not change
    the world is filler, regardless of the render model used later.
    """

    _FICTION_PREAMBLES = (
        "imagine this fictional", "this fictional story", "this is a fictional",
        "hayal edin", "bu kurgusal",
    )

    def audit(
        self,
        plan: NarrativePlan | None,
        cards: Iterable[SceneCard],
        narration: str = "",
        content_type: str = "factual",
    ) -> dict:
        cards = list(cards)
        failures: list[str] = []
        review: list[str] = []
        if plan is None:
            failures.append("Missing NarrativePlan; new runs must choose a supported story template.")
        else:
            if plan.template not in NARRATIVE_TEMPLATES:
                failures.append("Narrative template must be mechanism_reveal or mystery_escalation.")
            missing_plan_fields = [
                name for name, value in (
                    ("viewer_question", plan.viewer_question), ("hook_image", plan.hook_image),
                    ("stake", plan.stake), ("turn_or_constraint", plan.turn_or_constraint),
                    ("reversal", plan.reversal), ("final_payoff", plan.final_payoff),
                ) if not value
            ]
            if missing_plan_fields:
                failures.append("NarrativePlan is missing: " + ", ".join(missing_plan_fields) + ".")
            if len(plan.beats) != 5:
                failures.append(f"NarrativePlan needs exactly 5 StoryBeats, got {len(plan.beats)}.")
            for beat in plan.beats:
                missing = [
                    name for name, value in (
                        ("question_in", beat.question_in), ("answer_out", beat.answer_out),
                        ("cause", beat.cause), ("visible_event", beat.visible_event),
                        ("state_before", beat.state_before), ("state_after", beat.state_after),
                        ("new_information", beat.new_information), ("open_loop", beat.open_loop),
                        ("payoff_link", beat.payoff_link),
                    ) if not value
                ]
                if missing:
                    failures.append(f"StoryBeat {beat.index} is missing: {', '.join(missing)}.")
                if beat.state_before and beat.state_before.casefold() == beat.state_after.casefold():
                    failures.append(f"StoryBeat {beat.index} has no state change.")

        if not cards:
            failures.append("Storyboard has no SceneCards.")
        first = cards[0] if cards else None
        if first and not (first.dominant_event and first.proof_on_screen and first.entry_state and first.exit_state):
            failures.append("Opening 0-3 seconds lack a visible event, risk, or physical paradox.")
        if content_type == "fiction" and narration:
            opening = narration.strip().casefold()[:120]
            if any(phrase in opening for phrase in self._FICTION_PREAMBLES):
                failures.append("Fiction disclaimer consumes the opening hook; put the conflict on screen first.")

        previous: SceneCard | None = None
        seen_transitions: set[tuple[str, str]] = set()
        for index, card in enumerate(cards):
            for field, value in {
                "purpose": card.purpose,
                "dominant_event": card.dominant_event,
                "proof_on_screen": card.proof_on_screen,
                "entry_state": card.entry_state,
                "exit_state": card.exit_state,
                "next_question": card.next_question,
            }.items():
                if forbidden := has_prohibited_presentation(value):
                    failures.append(
                        f"SceneCard {card.scene_id} {field} requests prohibited {forbidden}; use physical proof instead."
                    )
            missing = [
                name for name, value in (
                    ("purpose", card.purpose), ("entry_state", card.entry_state),
                    ("exit_state", card.exit_state), ("dominant_event", card.dominant_event),
                    ("proof_on_screen", card.proof_on_screen), ("next_question", card.next_question),
                ) if not value
            ]
            if missing:
                failures.append(f"SceneCard {card.scene_id} is missing: {', '.join(missing)}.")
            if not card.asset_states:
                failures.append(f"SceneCard {card.scene_id} has no canonical asset_states to preserve identity.")
            if card.entry_state and card.entry_state.casefold() == card.exit_state.casefold():
                failures.append(f"SceneCard {card.scene_id} repeats its entry state instead of changing it.")
            transition = (card.entry_state.casefold(), card.exit_state.casefold())
            if transition in seen_transitions and all(transition):
                failures.append(f"SceneCard {card.scene_id} repeats an earlier visual state transition (filler).")
            seen_transitions.add(transition)
            if card.caption_safe_zone not in CAPTION_SAFE_ZONES:
                failures.append(f"SceneCard {card.scene_id} must reserve a non-caption safe zone for proof.")
            if card.proof_overlay:
                overlay = card.proof_overlay
                for field, value in overlay.items():
                    if forbidden := has_prohibited_presentation(value):
                        failures.append(
                            f"SceneCard {card.scene_id} proof_overlay {field} requests prohibited {forbidden}; HUD/text overlays are never allowed."
                        )
                missing_overlay = [key for key in ("type", "purpose", "placement") if not overlay.get(key)]
                if missing_overlay:
                    failures.append(f"SceneCard {card.scene_id} proof_overlay is missing: {', '.join(missing_overlay)}.")
                elif overlay.get("type") not in PROOF_OVERLAY_TYPES:
                    failures.append(f"SceneCard {card.scene_id} has an unsupported proof_overlay type.")
                elif overlay.get("placement") not in CAPTION_SAFE_ZONES:
                    failures.append(f"SceneCard {card.scene_id} proof_overlay placement overlaps or is outside the caption-safe contract.")
                elif overlay.get("placement") == card.caption_safe_zone:
                    failures.append(f"SceneCard {card.scene_id} proof_overlay placement collides with its caption-safe zone.")
            if index and previous:
                if not card.causal_parent_scene_id:
                    failures.append(f"SceneCard {card.scene_id} has no causal parent scene.")
                elif card.causal_parent_scene_id != previous.scene_id:
                    failures.append(
                        f"SceneCard {card.scene_id} must causally follow {previous.scene_id}, not {card.causal_parent_scene_id}."
                    )
                if previous.exit_state and card.entry_state and previous.exit_state.casefold() != card.entry_state.casefold():
                    failures.append(
                        f"SceneCard {card.scene_id} entry state does not continue the prior exit state; use a causal cut or shared state."
                    )
            previous = card

        if plan and cards:
            last = cards[-1]
            payoff_text = " ".join((plan.final_payoff, last.exit_state, last.semantic_expected_result)).casefold()
            question_terms = [term.casefold() for term in plan.viewer_question.split() if len(term) > 3]
            if not plan.final_payoff:
                failures.append("Final payoff is missing; the opening question is not closed.")
            elif question_terms and not any(term in payoff_text for term in question_terms):
                review.append("Final payoff is present but its textual link to the viewer question is weak; review the callback.")
            if not last.next_question:
                failures.append("Final SceneCard has no payoff/callback statement.")

        return {
            "schema_version": 1,
            "accepted": not failures,
            "blockers": failures,
            "review": review,
            "template": plan.template if plan else None,
            "scene_count": len(cards),
            "checks": {
                "visible_opening_hook": not any("Opening 0-3" in item for item in failures),
                "causal_chain": not any("causal" in item.lower() or "continue" in item.lower() for item in failures),
                "state_change": not any("state change" in item.lower() or "repeats" in item.lower() for item in failures),
                "payoff": not any("payoff" in item.lower() or "opening question" in item.lower() for item in failures),
            },
        }

    def audit_legacy_script(self, script: object, quality_report: dict | None = None) -> dict:
        """Read-only diagnostic for an old script with no saved SceneCards.

        It never mutates or upgrades the legacy run.  This lets a fixture explain why it
        would not pass the current production gate while preserving its original prompts,
        timing, and manual blocks for inspection.
        """
        narration = str(getattr(script, "narration", "") or "")
        shots = list(getattr(script, "shots", []) or [])
        report = self.audit(None, [], narration, str(getattr(script, "content_type", "fiction")))
        blockers = list(report["blockers"])
        opening = narration.casefold()[:140]
        if any(phrase in opening for phrase in self._FICTION_PREAMBLES):
            blockers.append("Opening spends the hook on a fiction disclaimer instead of a visible stake.")
        prompt_text = " ".join(
            " ".join((
                str(getattr(shot, "start_image_prompt", "")),
                str(getattr(shot, "end_image_prompt", "")),
                str(getattr(shot, "motion_prompt", "")),
            ))
            for shot in shots
        ).casefold()
        power_sources = [term for term in ("solar", "battery", "clockwork", "falling weight") if term in (narration + " " + prompt_text).casefold()]
        if "solar" in power_sources and ("clockwork" in power_sources or "falling weight" in power_sources):
            blockers.append("Multiple unconnected power chains are introduced; select one causal energy path.")
        if quality_report:
            quality_text = " ".join(
                " ".join(str(reason) for reason in (block.get("visual_quality") or {}).get("reasons", []))
                for block in quality_report.get("blocks", []) if isinstance(block, dict)
            ).casefold()
            if any(term in quality_text for term in ("industrial metal crushing", "debris", "domain mismatch")):
                blockers.append("Generated footage drifts away from the planned lighthouse event; semantic continuity would block release.")
        report.update({
            "accepted": False,
            "blockers": list(dict.fromkeys(blockers)),
            "legacy_fixture": True,
            "checks": {**report["checks"], "legacy_prompt_preserved": True},
        })
        return report
