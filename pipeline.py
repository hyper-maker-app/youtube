"""Five-phase provider-factory pipeline with an audio-locked native-block timeline."""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

logger = logging.getLogger("pipeline")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass

import captions
import config
import editor
import metadata
import release
import research
import run_history
from providers.base import HandoffPending as ProviderHandoffPending
from providers.factory import get_image_provider, get_llm_provider, get_sfx_provider, get_video_provider, get_voice_provider
from services.script_engine import (
    Beat, BeatEngine, Script, Shot, _is_exterior_shot, _required_beat_indices,
    annotate_words, compile_negative_prompt, optimize_for_flow, transition_boundary_kinds, validate_script
)
from services.asset_roster import build_roster, manifest as roster_manifest
from services.mode_profile import ANATOMICAL, INCIDENT, ModeProfile, detect_mode, mode_from_name
from services.sfx import SfxAsset, SfxValidationError, detect_peak_transient, validate_cue_sheet, write_attributions, write_sfx_cue_sheet
from services.sfx_dictionary import get_tactile_sfx_tags, sanitize_foley_text, translate_to_tactile_foley
from timeline import TimelinePlan


class HandoffPending(RuntimeError):
    """Manual video completion is required; ``run`` treats this as a clean stop."""


def atomic_write_json(path: Path, value: object) -> None:
    """Atomically persist BOM-free UTF-8 JSON; an interrupted write never becomes input."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def slugify(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "video")[:48]


@dataclass
class RunContext:
    topic: str
    out_dir: Path
    lang: str = "en"
    mode: ModeProfile = ANATOMICAL
    music: Path | None = None
    no_music: bool = False
    captions: bool = True
    dry_run: bool = False
    resumed: bool = False
    timeline: TimelinePlan | None = None
    llm_provider: str | None = None
    video_provider: str | None = None
    voice_provider: str | None = None
    image_provider: str | None = None
    test_blocks: int | None = None
    production_bundle: dict[str, str] | None = None
    stage: str = "all"
    skip_video: bool = False
    format: str = "short"

    @property
    def state_path(self) -> Path:
        return self.out_dir / "state.json"

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.state_path, state)


def make_run_dir(topic: str, resume: str | None = None) -> Path:
    if resume:
        path = Path(resume)
        if not path.is_absolute():
            path = config.OUT_ROOT / path
        if not path.exists():
            raise SystemExit(f"--resume path not found: {path}")
        return path
    path = config.OUT_ROOT / f"{slugify(topic)}_{time.strftime('%Y%m%d_%H%M%S')}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def provider_timeline(test_blocks: int | None = None, blocks: int | None = None) -> TimelinePlan:
    """Return a provisional screenplay plan or an isolated native-block smoke plan.

    A real new run initially uses a 12-shot provisional outline (48s) to give the
    screenplay model a practical visual outline. Phase 2 measures the generated
    narration and replaces this provisional plan with a persisted 6..13 block
    audio-driven plan *before* any keyframe request. ``--resume`` never reinterprets an
    existing plan.
    """
    if test_blocks is not None:
        if not 1 <= test_blocks <= 8:
            raise ValueError("test_blocks must be between 1 and 8")
        count = test_blocks
        is_smoke = True
    elif blocks is not None:
        count = blocks
        is_smoke = False
    elif (
        getattr(config, "LONGFORM_MODE", False)
        or os.getenv("LONGFORM_MODE", "").casefold() in {"1", "true", "yes"}
        or os.getenv("PRODUCTION_FORMAT", "").casefold() == "longform"
    ):
        count = 28
        is_smoke = False
    else:
        count = getattr(config, "DEFAULT_PRODUCTION_BLOCKS", 12)
        is_smoke = False

    if not is_smoke:
        timeline = TimelinePlan.for_profile("providers_4s", config.BLOCK_DURATION * count)
    else:
        # A smoke test deliberately relaxes the production planner's >=5-block
        # rule without changing it. The persisted plan records that this is a
        # short, non-resumable provider smoke test.
        timeline = TimelinePlan(
            source="providers_smoke_test", motion_model="providers_4s",
            motion_model_name="Provider adapters smoke test (4s)",
            native_clip_duration=4.0, minimum_duration=4.0 * count,
            beat_count=5, block_count=count, shot_durations=(4.0,) * count,
            total_duration=4.0 * count, keyframe_count=count + 1,
            output_resolution="720p",
        )
    if timeline.block_count != count or timeline.total_duration != 4.0 * count:
        raise RuntimeError(f"Provider timeline invariant must be {count} x 4.0s")
    return timeline


def audio_driven_timeline(voice_duration: float) -> TimelinePlan:
    """Freeze the native 4-second block count required by measured narration."""
    if voice_duration <= 0:
        raise ValueError("Audio-driven timeline requires a positive measured voice duration")
    needed_blocks = math.ceil((voice_duration - config.TAIL_HOLD) / config.BLOCK_DURATION)
    block_count = max(config.MIN_BLOCKS, min(config.MAX_BLOCKS, needed_blocks))
    generated_footage = block_count * config.BLOCK_DURATION
    target_duration = config.compute_target_duration(generated_footage, voice_duration)
    # The requested N formula chooses the minimum native plan.  Tail-inside-final
    # accounting can require one additional native block at a boundary; add it only
    # when otherwise the voice would overrun the moving-content-plus-tail budget.
    if target_duration - config.TAIL_HOLD > generated_footage + 0.001 and block_count < config.MAX_BLOCKS:
        block_count += 1
        generated_footage = block_count * config.BLOCK_DURATION
        target_duration = config.compute_target_duration(generated_footage, voice_duration)
    if target_duration - config.TAIL_HOLD > generated_footage + 0.001:
        raise RuntimeError(
            f"Voice duration {voice_duration:.3f}s exceeds the 13-block Shorts contract; "
            "shorten narration before any keyframe or video request."
        )
    timeline = TimelinePlan.for_profile("providers_4s", block_count * config.BLOCK_DURATION)
    return replace(
        timeline,
        source="providers_audio_driven",
        motion_model_name="Provider adapters (4s, audio-driven)",
        minimum_duration=block_count * config.BLOCK_DURATION,
        target_duration=target_duration,
        tail_hold=config.TAIL_HOLD,
        voice_duration=round(voice_duration, 3),
        content_duration=round(target_duration - config.TAIL_HOLD, 3),
    )


def _dry_script(ctx: RunContext) -> Script:
    timeline = ctx.timeline or provider_timeline()
    is_longform = (
        getattr(ctx, "format", "short") == "longform"
        or ctx.mode.name == "explorer"
        or getattr(config, "LONGFORM_MODE", False)
        or getattr(config, "IS_EXPLORER_FORMAT", False)
    )
    if is_longform:
        from services.screenplay import generate_dynamic_screenplay
        return generate_dynamic_screenplay(ctx.topic, timeline, lang=ctx.lang, target_blocks=timeline.block_count if timeline else 28)
    # Keep the local-only fixture inside the same full-run narration contract that
    # production validates, without invoking an LLM to invent real narration.
    beats = [Beat(
        index=i,
        text="A clean scientific mechanism moves through ordered physical steps. Energy transfers across connected parts to produce the causal result.",
        emphasis=["mechanism"],
    ) for i in range(1, 6)]
    shots: list[Shot] = []
    for block in range(1, timeline.block_count + 1):
        start, end = timeline.shot_window(block)
        shots.append(Shot(
            block=block, beat_index=_required_beat_indices(timeline.block_count)[block - 1], t_start=start, t_end=end,
            subject_id="demo_mechanism", subject_description="a readable scientific mechanism",
            start_image_prompt=f"Documentary 3D view of mechanism state {block}",
            end_image_prompt=f"Documentary 3D view of mechanism state {block + 1}",
            motion_prompt="the mechanism visibly advances one causal state",
            target_quadrant=("top_left", "top_right", "center", "bottom_left")[block % 4],
            dominant_event="a connected component transfers visible energy", proof_on_screen="the connected component changes state",
            entry_state=f"state {block}", exit_state=f"state {block + 1}",
            scale="medium", journey_phase=("establish", "descend", "explore", "reveal", "resolve")[min(4, (block - 1) * 5 // timeline.block_count)],
            transition_kind="same_subject", visual_domain="mechanical", continuity_anchor="demo mechanism housing",
            detail_target="connected mechanical energy path", quality_critical=["connected housing", "stable component attachment"], location_id="demo_lab",
        ))
    return Script(ctx.topic, beats, shots, ctx.lang, timeline, mode=ctx.mode.name)


def _retime_shots_to_timeline(script: Script, timeline: TimelinePlan) -> Script:
    """Resize a screenplay's visual coverage without changing its spoken narration.

    Extra blocks are explicit substeps of the final mechanism scene.  This preserves
    the authored causal progression while producing the exact N+1 Match-Cut keyframe
    chain that a provider-native 4-second render needs.  When narration is shorter,
    evenly sampled authored shots retain the hook and final payoff.
    """
    original = list(script.shots)
    if not original:
        raise RuntimeError("Cannot build an audio-driven timeline without screenplay shots")
    terminal_modes = {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"}
    payoff = next((shot for shot in original if shot.presentation_mode in terminal_modes), None)
    has_terminal_payoff = bool(payoff and original[-1].presentation_mode in terminal_modes)
    mechanism_candidates = [s for s in original if s.presentation_mode == "mechanism"]
    if not mechanism_candidates:
        mechanism_candidates = [s for s in original if s.presentation_mode not in terminal_modes]
    last_mech = mechanism_candidates[-1] if mechanism_candidates else (original[-2] if len(original) > 1 else original[0])
    if last_mech.presentation_mode != "mechanism":
        last_mech = replace(
            last_mech,
            presentation_mode="mechanism",
            opening_anchor_id="",
            endpoint_mode="first_last",
            endpoint_reason="",
            payoff_reason="",
        )

    selected: list[Shot] = []
    original_count = len(original)
    split_point = (original_count - 1) if (has_terminal_payoff and timeline.block_count > original_count) else original_count

    for target_index in range(timeline.block_count):
        if target_index < split_point:
            source = original[target_index]
        elif original_count > 1:
            # The final mechanism is deliberately decomposed into visible substeps;
            # use the last mechanism shot rather than the terminal character payoff (ADR-024).
            source = last_mech
        else:
            source = original[0]
        start, end = timeline.shot_window(target_index + 1)
        beat_index = _required_beat_indices(timeline.block_count)[target_index]
        if target_index >= split_point:
            substep = target_index - split_point + 1
            suffix = f"; visible mechanism substep {substep}"
            source = replace(
                source,
                presentation_mode="mechanism",
                opening_anchor_id="",
                endpoint_mode="first_last",
                endpoint_reason="",
                payoff_reason="",
                start_image_prompt=source.start_image_prompt + suffix,
                end_image_prompt=source.end_image_prompt + f"; next visible mechanism substep {substep}",
                motion_prompt=source.motion_prompt + suffix,
                entry_state=source.entry_state + f" (substep {substep})",
                exit_state=source.exit_state + f" (substep {substep + 1})",
                dominant_event=source.dominant_event + f" during mechanism substep {substep}",
                proof_on_screen=source.proof_on_screen + f" during mechanism substep {substep}",
            )
        selected.append(replace(source, block=target_index + 1, beat_index=beat_index, t_start=start, t_end=end))

    # The minimum six-block case deliberately compresses visual coverage rather than
    # keeping a stale eight-shot manifest.  Preserve both the opener and payoff.
    if timeline.block_count < original_count:
        selected = []
        max_src = (original_count - 2) if has_terminal_payoff else (original_count - 1)
        for target_index in range(timeline.block_count):
            if target_index == timeline.block_count - 1 and has_terminal_payoff:
                source = original[-1]
            else:
                source_index = round(target_index * max_src / max(1, timeline.block_count - 1))
                source = original[min(max_src, source_index)]
            start, end = timeline.shot_window(target_index + 1)
            selected.append(replace(
                source, block=target_index + 1,
                beat_index=_required_beat_indices(timeline.block_count)[target_index],
                t_start=start, t_end=end,
            ))
    # Compression can make two formerly non-adjacent authored shots neighbors.
    # Their original `same_subject` label described a different predecessor, so
    # convert only those newly-invalid edges into an explicit Match-Cut rather
    # than asking the image/video providers to preserve a false identity link.
    normalized: list[Shot] = []
    for shot in selected:
        if normalized and shot.transition_kind == "same_subject":
            previous = normalized[-1]
            identity_matches = (
                shot.subject_id == previous.subject_id
                and shot.continuity_anchor == previous.continuity_anchor
                and shot.location_id == previous.location_id
            )
            if not identity_matches:
                transition = "location_change" if shot.location_id != previous.location_id else "subject_change"
                shot = replace(shot, transition_kind=transition)
        normalized.append(shot)
    # The terminal payoff is singular: when duration changes it follows the final
    # native block rather than being copied into decomposed mechanism coverage.
    if payoff:
        normalized = [replace(shot, presentation_mode=("mechanism" if shot.presentation_mode in terminal_modes else shot.presentation_mode), payoff_reason=("" if shot.presentation_mode in terminal_modes else shot.payoff_reason), endpoint_mode=("first_last" if shot.presentation_mode in terminal_modes else shot.endpoint_mode)) for shot in normalized]
        terminal = normalized[-1]
        payoff_endpoint_mode = payoff.endpoint_mode if (payoff.presentation_mode == "return_to_contextual_anchor_payoff" and payoff.endpoint_mode in {"first_only", "first_last"}) else "first_only"
        payoff_endpoint_reason = payoff.endpoint_reason.strip() or payoff.payoff_reason.strip() or f"terminal {payoff.presentation_mode} quality preservation"
        normalized[-1] = replace(
            payoff,
            block=timeline.block_count,
            beat_index=_required_beat_indices(timeline.block_count)[-1],
            t_start=terminal.t_start,
            t_end=terminal.t_end,
            presentation_mode=payoff.presentation_mode,
            endpoint_mode=payoff_endpoint_mode,
            endpoint_reason=payoff_endpoint_reason if payoff_endpoint_mode == "first_only" else payoff.endpoint_reason,
        )
    for i in range(1, len(normalized)):
        prev = normalized[i - 1]
        curr = normalized[i]
        if curr.transition_kind == "scale_transition" and curr.scale == prev.scale and curr.camera_angle == prev.camera_angle:
            if curr.subject_id == prev.subject_id and curr.continuity_anchor == prev.continuity_anchor and curr.location_id == prev.location_id:
                normalized[i] = replace(curr, transition_kind="same_subject")
            elif curr.location_id != prev.location_id:
                normalized[i] = replace(curr, transition_kind="location_change")
            else:
                normalized[i] = replace(curr, transition_kind="subject_change")
        elif curr.transition_kind == "same_subject":
            if curr.subject_id == prev.subject_id and (curr.scale != prev.scale or curr.camera_angle != prev.camera_angle):
                normalized[i] = replace(curr, transition_kind="scale_transition")
            elif curr.location_id != prev.location_id:
                normalized[i] = replace(curr, transition_kind="location_change")
            elif curr.subject_id != prev.subject_id or curr.continuity_anchor != prev.continuity_anchor:
                normalized[i] = replace(curr, transition_kind="subject_change")
    return Script(script.topic, script.beats, normalized, script.lang, timeline, mode=script.mode)


def build_frame_plan(script: Script) -> list[dict[str, Any]]:
    """Create the immutable N+1 keyframe contract, including a non-morph payoff."""
    plan: list[dict[str, Any]] = []
    n = len(script.shots)
    for shot in script.shots:
        terminal = shot.presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"}
        contextual = shot.presentation_mode == "return_to_contextual_anchor_payoff"
        is_pullout_interpolation = contextual and shot.endpoint_mode == "first_last" and (
            shot.transition_kind == "scale_transition"
            or any(kw in f"{shot.motion_prompt} {shot.dominant_event}".casefold() for kw in ("pull", "zoom", "interpolat", "flight"))
        )
        if is_pullout_interpolation:
            start_frame_id = f"kf{shot.block:02d}"
            end_frame_id = f"kf{n + 1:02d}"
            transition_at_in = "continuous_flight"
        elif terminal:
            start_frame_id = f"kf{n + 1:02d}"
            end_frame_id = None
            transition_at_in = "hard_cut"
        else:
            start_frame_id = f"kf{shot.block:02d}"
            next_shot = script.shots[shot.block] if shot.block < n else None
            is_cut = (
                shot.endpoint_mode == "first_only"
                or shot.transition_kind in {"subject_change", "location_change"}
                or (next_shot is not None and next_shot.transition_kind in {"subject_change", "location_change"})
            )
            is_valid_continuous = (
                shot.endpoint_mode == "first_last"
                and shot.transition_kind in {"same_subject", "scale_transition"}
                and not is_cut
            )
            end_frame_id = f"kf{shot.block + 1:02d}" if is_valid_continuous else None
            transition_at_in = "hard_cut"

        plan.append({
            "block": shot.block,
            "start_frame_id": start_frame_id,
            "end_frame_id": end_frame_id,
            "reference_policy": ("contextual_anchor_roster_only" if contextual else "opening_anchor_roster_only") if terminal else "previous_keyframe_plus_roster",
            "transition_at_in": transition_at_in,
            "presentation_mode": shot.presentation_mode,
            "opening_anchor_id": shot.opening_anchor_id if terminal else "",
            "contextual_anchor_id": shot.contextual_anchor_id if contextual else "",
            "contextual_anchor_subject_id": shot.contextual_anchor_subject_id if contextual else "",
            "payoff_reason": shot.payoff_reason if terminal else "",
        })
    return plan


def build_editorial_plan(script: Script) -> dict[str, Any]:
    """Persist calm hard-cut decisions with subtle micro-impact on domain/subject shifts."""
    boundaries = []
    for index in range(1, len(script.shots)):
        prior = script.shots[index - 1]
        current = script.shots[index]
        domain_shift = prior.normalized_domain != current.normalized_domain
        major_transition = current.transition_kind in {"location_change", "subject_change"}
        impact = "subtle" if (domain_shift or major_transition) else "none"
        boundaries.append({
            "boundary": index,
            "time": round(current.t_start, 3),
            "cut_style": "hard",
            "impact_level": impact,
            "physical_accent": "domain_shift" if domain_shift else ("scene_cut" if major_transition else None),
            "sfx_cue_ids": [],
        })
    return {"schema_version": 1, "boundaries": boundaries}


async def resolve_sfx_cues(ctx: RunContext, script: Script) -> list[dict[str, Any]]:
    """Resolve only explicitly authored physical-event cues through the selected source.

    No configured provider and no authored cue means silent-by-design, not a fallback.
    """
    raw = list((script.editorial_plan or {}).get("sfx_cues") or [])
    if not raw:
        return []
    if script.shots and script.shots[-1].presentation_mode == "return_to_contextual_anchor_payoff":
        terminal_block = script.shots[-1].block
        if any(isinstance(cue, dict) and int(cue.get("block") or 0) == terminal_block for cue in raw):
            raise SfxValidationError("Contextual terminal payoff is silent by default; do not author a terminal SFX cue.")
    provider = get_sfx_provider()
    assets: list[SfxAsset] = []
    cues: list[dict[str, Any]] = []
    max_target = float((script.timeline or ctx.timeline or provider_timeline()).target_duration or 60.0)
    for item in raw:
        if not isinstance(item, dict):
            raise SfxValidationError("Every authored SFX cue must be an object.")
        raw_prompt = str(item.get("prompt") or item.get("reason") or "").strip()
        domain = str(item.get("domain") or getattr(ctx.mode, "name", "") or "")
        tactile_prompt = translate_to_tactile_foley(raw_prompt, domain=domain) if raw_prompt else "tactile acoustic foley, crisp ASMR micro-hit"
        tags = [str(t) for t in item.get("tags") or [] if str(t).strip()]
        if not tags and raw_prompt:
            tags = get_tactile_sfx_tags(tactile_prompt, domain=domain)
        query = {
            "asset_id": item.get("asset_id"),
            "prompt": tactile_prompt,
            "tags": tags or ["foley", "diegetic"],
            "duration": float(item.get("duration") or 1.0),
        }
        record = await provider.resolve_asset(query, ctx.out_dir / "sfx_cache")
        asset = SfxAsset.from_dict(record)
        assets.append(asset)
        cue = dict(item)
        cue["asset_id"] = asset.asset_id
        cue["local_path"] = asset.local_path
        c_start = float(cue.get("start", 0.0))
        c_end = float(cue.get("end", c_start + 0.65))
        duration = c_end - c_start
        if duration < 0.55:
            duration = 0.65
            c_end = round(c_start + duration, 3)
        elif duration > 0.75:
            duration = 0.75
            c_end = round(c_start + duration, 3)
        if c_end > max_target:
            c_end = round(max_target, 3)
            c_start = max(0.0, round(c_end - 0.65, 3))
            cue["start"] = c_start
        cue["end"] = c_end
        if "gain_db" not in cue:
            cue["gain_db"] = -10.0
        if "fade_in" not in cue:
            cue["fade_in"] = 0.015
        if "fade_out" not in cue:
            cue["fade_out"] = 0.25
        if "start_trim" not in cue:
            peak_t = detect_peak_transient(Path(asset.local_path))
            cue["start_trim"] = max(0.0, round(peak_t - 0.05, 3))
        if "reason" not in cue or len(str(cue["reason"]).strip()) < 8:
            clean_reason = sanitize_foley_text(tactile_prompt) or tactile_prompt
            cue["reason"] = f"Physical diegetic motion: {clean_reason[:60]}"
        cues.append(cue)
    normalized = validate_cue_sheet(cues, assets)
    write_sfx_cue_sheet(ctx.out_dir, normalized, assets)
    write_attributions(ctx.out_dir, assets)
    return normalized


async def generate_mmaudio_sfx(ctx: RunContext, script: Script, blocks: list[Path]) -> list[dict[str, Any]]:
    """Synthesize synchronized diegetic SFX for key physical/analogy blocks."""
    selected = (getattr(ctx, "sfx_provider", None) or os.getenv("SFX_PROVIDER", "")).casefold()
    if selected not in {"mmaudio", "elevenlabs", "eleven_labs"} or not blocks:
        return []

    provider = get_sfx_provider(selected)
    assets: list[SfxAsset] = []
    cues: list[dict[str, Any]] = []

    candidate_shots: list[Shot] = []
    for shot in script.shots:
        if shot.presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"}:
            continue
        is_analogy = shot.journey_phase == "explore" and shot.normalized_domain == "mechanical"
        has_physical_proof = any(
            kw in f"{shot.proof_on_screen} {shot.dominant_event}".lower()
            for kw in ctx.mode.sfx_trigger_keywords
        )
        is_descent = shot.journey_phase == "descend" or shot.transition_kind == "scale_transition"
        if is_analogy or has_physical_proof or is_descent:
            candidate_shots.append(shot)

    chosen_shots = candidate_shots[:ctx.mode.max_sfx_cues] if candidate_shots else (script.shots[:1] if script.shots else [])

    timeline_target = float((script.timeline or ctx.timeline or provider_timeline()).target_duration or (len(blocks) * 4.0))

    for shot in chosen_shots:
        if shot.block > len(blocks):
            continue
        shot_dur = shot.t_end - shot.t_start
        if shot_dur < 0.4:
            continue
        block_path = blocks[shot.block - 1]
        
        # Calculate precise physical contact time rather than blindly starting at t=0
        impact_offset = getattr(shot, "impact_offset_seconds", 1.8)
        if not (0.2 <= impact_offset <= 3.6):
            impact_offset = 1.8
        
        # Zack D. Films tactile foley uses natural decay envelope (0.55-0.75s) aligned to transient
        cue_start = round(min(shot.t_start + impact_offset, max(shot.t_start, shot.t_end - 0.65)), 3)
        effective_end = round(min(cue_start + 0.65, timeline_target), 3)
        if effective_end <= cue_start:
            effective_end = round(min(cue_start + 0.55, timeline_target), 3)
        if effective_end <= cue_start:
            continue

        # Translate abstract scientific/mechanical descriptions into concrete tactile Foley
        sfx_prompt = translate_to_tactile_foley(
            shot.dominant_event,
            proof_on_screen=shot.proof_on_screen,
            domain=shot.normalized_domain,
            narration_context=getattr(shot, "narration_excerpt", ""),
        )
        prompt_tags = get_tactile_sfx_tags(sfx_prompt, domain=shot.normalized_domain)

        record = await provider.resolve_asset({
            "video_path": str(block_path),
            "prompt": sfx_prompt,
            "duration": 1.0,
            "tags": list(dict.fromkeys([shot.normalized_domain, "foley", "diegetic"] + prompt_tags)),
            "asset_id": f"sfx_b{shot.block:02d}",
        }, ctx.out_dir / "sfx_cache")

        asset = SfxAsset.from_dict(record)
        assets.append(asset)

        peak_t = detect_peak_transient(Path(asset.local_path))
        start_trim = max(0.0, round(peak_t - 0.05, 3))

        clean_reason = sanitize_foley_text(shot.dominant_event) or shot.dominant_event
        cues.append({
            "cue_id": f"cue_mmaudio_{shot.block:02d}",
            "block": shot.block,
            "start": cue_start,
            "end": effective_end,
            "reason": f"Physical diegetic motion: {clean_reason[:60]}",
            "asset_id": asset.asset_id,
            "local_path": asset.local_path,
            "gain_db": -10.0,
            "fade_in": 0.015,
            "fade_out": 0.25,
            "start_trim": start_trim,
        })

    if not cues:
        return []
    normalized = validate_cue_sheet(cues, assets)
    write_sfx_cue_sheet(ctx.out_dir, normalized, assets)
    write_attributions(ctx.out_dir, assets)
    return normalized


def _measured_voice_duration(voice: dict[str, Any]) -> float:
    """Use the media file's duration when available, never a provider estimate."""
    raw_path = voice.get("vo_path")
    if raw_path:
        path = Path(raw_path)
        if path.is_file():
            measured = editor.probe(path).duration
            if measured and measured > 0:
                return float(measured)
    reported = voice.get("duration")
    return float(reported) if isinstance(reported, (int, float)) else 0.0


def _lock_audio_driven_timeline(ctx: RunContext, script: Script, voice: dict[str, Any], state: dict[str, Any]) -> Script:
    """Persist the one permitted new-run timing change before billable keyframes."""
    duration = _measured_voice_duration(voice)
    voice["duration"] = duration
    timeline = script.timeline or ctx.timeline or provider_timeline()
    # A test plan or a genuinely persisted audio-driven/legacy plan is authoritative.
    # ``ctx.resumed`` alone is insufficient: a process can be interrupted after TTS
    # but before this first lock, while its timeline still says ``providers``.
    is_longform = (
        getattr(ctx, "format", "short") == "longform"
        or ctx.mode.name == "explorer"
        or getattr(config, "LONGFORM_MODE", False)
        or getattr(config, "IS_EXPLORER_FORMAT", False)
    )
    if ctx.test_blocks is not None or timeline.source == "providers_audio_driven" or state.get("audio_timeline_locked"):
        return script
    if not is_longform and timeline.source != "providers":
        return script

    if is_longform:
        if script.shots:
            total_current = sum(s.duration for s in script.shots)
            needed_footage = max(total_current, duration + config.TAIL_HOLD) if duration > 0 else total_current
            if total_current > 0 and needed_footage > total_current:
                scale_factor = needed_footage / total_current
                if scale_factor > 1.25:
                    # Do not stretch individual shots into 10-14s which creates freezes.
                    # Expand the shot sequence to match the needed block count at ~4.0s per shot.
                    needed_blocks = max(len(script.shots), math.ceil(needed_footage / config.BLOCK_DURATION))
                    orig = list(script.shots)
                    broll_pool = [s for s in orig[:-1] if not (getattr(s, "is_a_roll", False) or "host" in (s.subject_id or "").casefold())] or orig[:-1]
                    while len(orig) < needed_blocks:
                        extra = broll_pool[(len(orig) - 1) % len(broll_pool)]
                        orig.insert(len(orig) - 1, extra)
                    shot_dur = round(needed_footage / needed_blocks, 3)
                    updated_shots = []
                    current_t = 0.0
                    for idx_b, s in enumerate(orig[:needed_blocks], start=1):
                        updated_shots.append(replace(
                            s,
                            block=idx_b,
                            beat_index=min(len(script.beats), max(1, int((idx_b - 1) * len(script.beats) / max(1, needed_blocks)) + 1)),
                            t_start=round(current_t, 3),
                            t_end=round(current_t + shot_dur, 3),
                        ))
                        current_t += shot_dur
                    script.shots = updated_shots
                else:
                    current_t = 0.0
                    updated_shots = []
                    for s in script.shots:
                        new_dur = round(s.duration * scale_factor, 3)
                        updated_shots.append(replace(
                            s,
                            t_start=round(current_t, 3),
                            t_end=round(current_t + new_dur, 3),
                        ))
                        current_t += new_dur
                    script.shots = updated_shots
            shot_durations = tuple(round(s.duration, 3) for s in script.shots)
            block_count = len(script.shots)
            generated_footage = round(sum(shot_durations), 3)
            avg_clip_dur = round(generated_footage / max(1, block_count), 2)
            target_duration = config.compute_target_duration(generated_footage, duration)
            is_hybrid_mode = getattr(config, "LONGFORM_HYBRID_MODE", False)
            dynamic = TimelinePlan(
                source="providers_audio_driven",
                motion_model="longform_hybrid" if is_hybrid_mode else "longform_diffusion",
                motion_model_name="Provider adapters (longform, hybrid)" if is_hybrid_mode else "Provider adapters (longform, 100% diffusion)",
                native_clip_duration=avg_clip_dur,
                minimum_duration=generated_footage,
                beat_count=len(script.beats),
                block_count=block_count,
                shot_durations=shot_durations,
                total_duration=generated_footage,
                keyframe_count=block_count + 1,
                output_resolution="1080p",
                target_duration=target_duration,
                tail_hold=config.TAIL_HOLD,
                voice_duration=round(duration, 3),
                content_duration=round(target_duration - config.TAIL_HOLD, 3),
            )
            locked = script
            locked.timeline = dynamic
            locked.frame_plan = build_frame_plan(locked)
            locked.editorial_plan = build_editorial_plan(locked)
            return locked
        return script
    else:
        dynamic = audio_driven_timeline(duration)
        locked = _retime_shots_to_timeline(script, dynamic)
        locked.frame_plan = build_frame_plan(locked)
        locked.editorial_plan = build_editorial_plan(locked)
        if ctx.mode.name != "explorer" and not getattr(config, "IS_EXPLORER_FORMAT", False):
            problems = validate_script(locked, dynamic, mode=ctx.mode)
            # The measured audio file is the authority after TTS.  The narration word
            # profile was only a pre-TTS planning heuristic, so do not reject a valid
            # 6–13-block visual plan merely because a provider spoke the same text more
            # slowly or quickly than that heuristic predicted.
            problems = [problem for problem in problems if not problem.startswith("narration needs ")]
            if problems:
                raise RuntimeError("Audio-driven screenplay validation failed: " + "; ".join(problems))
    ctx.timeline = dynamic
    atomic_write_json(ctx.out_dir / "script.json", locked.to_dict())
    metadata.write_metadata(locked, ctx.out_dir)
    manifest_path = ctx.out_dir / "run_manifest.json"
    manifest = _load_json_object(manifest_path) or {"schema_version": 1, "topic": ctx.topic}
    manifest["timeline"] = dynamic.to_dict()
    manifest["audio_timeline_locked"] = True
    atomic_write_json(manifest_path, manifest)
    state.update({
        "audio_timeline_locked": True,
        "voice_duration": duration,
        "timeline": dynamic.to_dict(),
        "render_duration": dynamic.target_duration,
    })
    ctx.save_state(state)
    return locked


async def phase1_script(ctx: RunContext, state: dict[str, Any]) -> Script:
    print(f"\n[1/5] 📝 Senaryo & 5-Beat Kurgu: {ctx.topic}")
    script_path = ctx.out_dir / "script.json"
    if script_path.exists():
        script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
        ctx.timeline = script.timeline or provider_timeline()
        metadata.write_metadata(script, ctx.out_dir)
        state["script"] = True
        ctx.save_state(state)
        print(f"    ✓ Senaryo önbellekten yüklendi: {len(script.beats)} beat, {len(script.shots)} çekim.")
        return script
    ctx.timeline = ctx.timeline or provider_timeline()
    is_longform = (
        getattr(ctx, "format", "short") == "longform"
        or ctx.mode.name == "explorer"
        or getattr(config, "LONGFORM_MODE", False)
        or getattr(config, "IS_EXPLORER_FORMAT", False)
    )
    if ctx.dry_run:
        script = _dry_script(ctx)
    else:
        # Evidence is collected before a billable screenplay request. This utility is
        # outside services because it owns public-web transport; its manifest records
        # unavailable research rather than fabricating a trend or a claim.
        if not (ctx.out_dir / "research.json").exists():
            evidence = research.write_manifest(ctx.out_dir, ctx.topic, "factual", (), [ctx.topic])
            state["research"] = evidence.get("status")
            ctx.save_state(state)
        if is_longform:
            llm = get_llm_provider(ctx.llm_provider)
            from core.narrative_longform import LongformEngine
            script = await LongformEngine(llm, lang=ctx.lang, timeline=ctx.timeline, mode=ctx.mode).generate(ctx.topic)
        else:
            llm = get_llm_provider(ctx.llm_provider)
            script = await BeatEngine(llm, lang=ctx.lang, timeline=ctx.timeline, mode=ctx.mode).generate(ctx.topic)
    
    if not is_longform:
        problems = validate_script(script, ctx.timeline, mode=ctx.mode)
        if not ctx.resumed and ctx.test_blocks is None:
            # The provisional eight-shot outline deliberately has no authority over
            # narration length.  Measured TTS locks the real 6..13-block budget before
            # any image request, where the complete validator runs again.
            problems = [problem for problem in problems if not problem.startswith("narration needs ")]
        if problems:
            raise RuntimeError("Script validation failed before asset generation: " + "; ".join(problems))
    atomic_write_json(script_path, script.to_dict())
    metadata.write_metadata(script, ctx.out_dir)
    state["script"] = True
    ctx.save_state(state)
    print(f"    ✓ Senaryo oluşturuldu: {len(script.beats)} beat, {len(script.shots)} çekim.")
    return script


def _keyframe_jobs(script: Script, root: Path, mode: ModeProfile = ANATOMICAL) -> list[tuple[str, str, Path, int, bool]]:
    """Compile the sequential Match-Cut chain (Shorts) or 1:1 shot-start chain (Longform Explorer).

    In 9:16 Shorts Match-Cut mode, ``kf01`` is the first shot's entry state and
    every subsequent ``kfNN`` is the preceding shot's authored exit state.
    In 16:9 Longform Explorer mode (where shots use ``endpoint_mode='first_only'``
    and hard cuts between A-Roll, Witness Interviews, and B-Roll plates), ``kf{k:02d}``
    for ``k=1..N`` is compiled directly from ``script.shots[k-1].start_prompt`` so
    every block ``k`` receives its exact authored keyframe without an off-by-one shift.
    """
    if not script.shots:
        return []
    is_longform = (
        mode.name == "explorer"
        or script.mode == "explorer"
        or getattr(config, "LONGFORM_MODE", False)
        or getattr(config, "IS_EXPLORER_FORMAT", False)
    )
    if is_longform:
        jobs: list[tuple[str, str, Path, int, bool]] = []
        for idx, shot in enumerate(script.shots, start=1):
            start_prompt = optimize_for_flow(shot, mode=mode)["start_prompt"]
            is_hero = (idx == 1 or shot.journey_phase == "reveal" or "host" in (shot.subject_id or "").casefold() or "witness" in (shot.subject_id or "").casefold())
            jobs.append((
                f"kf{idx:02d}",
                start_prompt,
                root / "keyframes" / f"kf{idx:02d}.png",
                idx,
                is_hero,
            ))
        last_shot = script.shots[-1]
        tail_idx = len(script.shots) + 1
        jobs.append((
            f"kf{tail_idx:02d}",
            optimize_for_flow(last_shot, mode=mode)["end_prompt"],
            root / "keyframes" / f"kf{tail_idx:02d}.png",
            tail_idx,
            False,
        ))
        return jobs

    first = script.shots[0]
    jobs = [
        # The first frame is the visual hook and always receives the hero model.
        ("kf01", optimize_for_flow(first, mode=mode)["start_prompt"], root / "keyframes" / "kf01.png", 1, True)
    ]
    terminal = script.shots[-1] if script.shots and script.shots[-1].presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"} else None
    # Normal chain stops at kfN for an independent terminal anchor.  kfN+1 is
    # deliberately not conditioned on the preceding microscopic/mechanism frame.
    normal_shots = script.shots[:-1] if terminal else script.shots
    for keyframe_index, shot in enumerate(normal_shots, start=2):
        end_prompt = optimize_for_flow(shot, mode=mode)["end_prompt"]
        if shot.transition_kind == "same_subject":
            end_prompt += (
                " This is the next sequential Match-Cut endpoint. Use the supplied previous keyframe as the exact visual reference: "
                "preserve its subject identity, geometry, materials, lighting direction, lens, framing and environment; change only the authored endpoint state."
            )
        elif shot.transition_kind == "scale_transition":
            end_prompt += (
                " This is the next sequential scale-transition endpoint. Use the supplied previous keyframe as the exact visual reference: "
                "preserve its subject identity, connected geometry, materials, lighting direction and environment, while advancing only the authored scale/crop "
                "to make the endpoint state visibly readable. Do not retain the prior framing when it conflicts with the required endpoint scale."
            )
        else:
            end_prompt += (
                " This is a deliberate Match-Cut endpoint. Use the supplied previous keyframe only to carry camera energy, composition, "
                "lighting palette and one dominant matching silhouette across the cut. Replace the subject and environment with this authored "
                "endpoint state; do not preserve the old object or location."
            )
        jobs.append((
            f"kf{keyframe_index:02d}", end_prompt,
            root / "keyframes" / f"kf{keyframe_index:02d}.png", keyframe_index,
            # This endpoint is the current shot's exit state. A reveal is a
            # second hero moment; all other continuity endpoints use normal.
            shot.journey_phase == "reveal",
        ))
    if terminal:
        jobs.append((
            f"kf{len(script.shots) + 1:02d}", optimize_for_flow(terminal, mode=mode)["start_prompt"] +
            f" Independent terminal {'contextual' if terminal.presentation_mode == 'return_to_contextual_anchor_payoff' else 'opening'}-anchor payoff. Use only the supplied anchor roster references; do not use or recreate a preceding mechanism frame. Hard editorial cut context; show one calm resolved physical state.",
            root / "keyframes" / f"kf{len(script.shots) + 1:02d}.png", len(script.shots) + 1, True,
        ))
    return jobs


def _prompt_manifest(jobs: list[tuple[str, str, Path, int, bool]], roster_sha256: str = "") -> dict[str, dict[str, str | int | bool]]:
    """Fingerprint keyframe identity, prompt, and selected image-model tier."""
    return {
        key: {
            "path": str(path), "seed": seed,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "tier": "nano_banana_pro",
            "model": config.NANO_BANANA_PRO_MODEL,
            "roster_sha256": roster_sha256,
        }
        for key, prompt, path, seed, is_hero in jobs
    }


def _load_json_object(path: Path) -> dict[str, Any] | None:
    """Read a persisted JSON object without ever treating a broken artifact as valid."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _valid_reusable_refs(
    refs_path: Path, manifest_path: Path, expected_manifest: dict[str, dict[str, str | int | bool]],
) -> dict[str, dict[str, str]]:
    """Return only exact, non-empty kfNN assets whose prompt dependency still matches.

    A persisted alias, a stale prompt fingerprint, or an empty path is rejected
    individually.  This keeps retries surgical and prevents ``Path(\"\")`` from
    accidentally referring to a run directory.
    """
    refs = _load_json_object(refs_path)
    manifest = _load_json_object(manifest_path)
    if refs is None or manifest is None:
        return {}
    reusable: dict[str, dict[str, str]] = {}
    for key, expected in expected_manifest.items():
        actual_manifest = manifest.get(key)
        entry = refs.get(key)
        if not isinstance(actual_manifest, dict) or not isinstance(entry, dict):
            continue
        if (
            actual_manifest.get("prompt_sha256") != expected["prompt_sha256"]
            or actual_manifest.get("seed") != expected["seed"]
            or actual_manifest.get("model") != expected["model"]
            or actual_manifest.get("tier") != expected["tier"]
            or actual_manifest.get("roster_sha256", "") != expected.get("roster_sha256", "")
        ):
            continue
        raw_path = entry.get("local")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        asset = Path(raw_path)
        expected_path = Path(str(expected["path"]))
        try:
            same_identity = asset.resolve(strict=True) == expected_path.resolve(strict=True)
        except OSError:
            same_identity = False
        if same_identity and asset.is_file() and asset.stat().st_size > 0:
            reusable[key] = {"local": str(asset)}
    return reusable


def _recover_unmanifested_exact_refs(jobs: list[tuple[str, str, Path, int, bool]], refs_path: Path, manifest_path: Path) -> dict[str, dict[str, str]]:
    """Refuse assets that predate manifest-level model provenance.

    A bare filename can prove neither hero versus normal tier nor the exact image
    model. Regenerating missing provenance is cheaper than feeding a stale visual
    tier into an otherwise deterministic Match-Cut chain.
    """
    _ = jobs, refs_path, manifest_path
    return {}


def _narration_fingerprint(script: Script) -> str:
    payload = "\n".join(str(beat.text).strip() for beat in script.beats)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _spoken_tokens(value: str) -> list[str]:
    return re.findall(r"[\w']+", value.casefold(), flags=re.UNICODE)


def _voice_matches_script(script: Script, words: list[dict[str, Any]]) -> bool:
    """Reject partial/stale TTS audio before its bad transcript becomes captions."""
    authored = _spoken_tokens(script.narration)
    transcribed = _spoken_tokens(" ".join(str(word.get("text") or "") for word in words))
    if not authored or not transcribed:
        return False
    return difflib.SequenceMatcher(a=authored, b=transcribed, autojunk=False).ratio() >= 0.90


def _validate_voice_contract(ctx: RunContext, script: Script, voice: dict[str, Any]) -> None:
    words = list(voice.get("words") or [])
    duration = _measured_voice_duration(voice)
    voice["duration"] = duration
    # Test-only callers that intentionally mock editor.render without any voice
    # artifact are not a production path. Real adapters always return both fields.
    if not words and duration <= 0:
        return
    timeline = script.timeline or ctx.timeline or provider_timeline()
    final_duration = timeline.target_duration or config.compute_target_duration(timeline.total_duration, duration)
    if not _voice_matches_script(script, words):
        raise RuntimeError("Voice transcript does not match the persisted narration; refusing stale/partial captions and video render")
    if ctx.test_blocks is None and duration > final_duration + 0.001:
        raise RuntimeError(
            f"Voice duration {duration:.3f}s exceeds the {final_duration:.3f}s audio-driven render contract"
        )
    if ctx.test_blocks is None and getattr(ctx, "format", "short") != "longform" and duration < timeline.total_duration * 0.70:
        raise RuntimeError(f"Voice duration {duration:.3f}s is too short for the {timeline.total_duration:.3f}s footage contract")
    previous = -0.001
    for index, word in enumerate(words, start=1):
        start, end = float(word.get("start") or 0.0), float(word.get("end") or 0.0)
        if end <= start or start < previous:
            raise RuntimeError(f"Voice word timing {index} is not strictly chronological")
        previous = start


def _reusable_narration(ctx: RunContext, script: Script, state: dict[str, Any]) -> dict[str, Any] | None:
    """Reuse narration only when its file, word timings, and script dependency are sound."""
    voice_path = ctx.out_dir / "audio" / "vo.mp3"
    words_payload = _load_json_object(ctx.out_dir / "words.json")
    manifest_path = ctx.out_dir / "voice_manifest.json"
    voice_manifest = _load_json_object(manifest_path)
    fingerprint = _narration_fingerprint(script)
    if not voice_path.is_file() or voice_path.stat().st_size <= 0 or not words_payload:
        return None
    words = words_payload.get("words")
    duration = words_payload.get("duration")
    if not isinstance(words, list) or not words or not isinstance(duration, (int, float)) or float(duration) <= 0:
        return None
    # Older successful runs predate voice_manifest.json.  They remain compatible
    # only when the independently aligned transcript still matches this exact script.
    manifest_matches = isinstance(voice_manifest, dict) and voice_manifest.get("narration_sha256") == fingerprint
    legacy_compatible = voice_manifest is None and state.get("voice") is True
    if not (manifest_matches or legacy_compatible) or not _voice_matches_script(script, words):
        return None
    atomic_write_json(manifest_path, {"narration_sha256": fingerprint, "vo_path": str(voice_path), "duration": float(duration)})
    return {"vo_path": voice_path, "duration": float(duration), "words": words}


# -----------------------------------------------------------------------
# ADR-028 / ADR-031: Smart Surgical Repair Loop & Zero-Rejection Engine
# Replaces naive comma-separated error dumps with categorized, actionable
# instructions that guide the model to fix the exact defect without breaking
# the 3D scene continuity.
# -----------------------------------------------------------------------
def _categorize_rejection(reason: str) -> str:
    """Classify a visual admission rejection reason into a surgical repair category."""
    r = reason.lower()
    if any(w in r for w in ("sideway", "rotate", "orientation", "upside-down", "horizontal", "90 degree", "90-degree", "vertical framing", "landscape framing", "tilted sideways")):
        return "orientation_fault"
    if any(w in r for w in ("duplicate", "identical", "clone", "same person", "both pilots appear")):
        return "character_duplication"
    if any(w in r for w in ("missing", "lacks", "does not show", "no sign of", "absence of",
                           "not visible", "where is", "omitted", "without")):
        return "missing_object"
    if any(w in r for w in ("text", "label", "caption", "watermark", "letter", "number",
                           "symbol", "logo", "formula", "annotation", "na+", "cl-", "h2o")):
        return "text_contamination"
    if any(w in r for w in ("downward", "upward", "outward", "inward", "pointing", "direction of", "flow direction", "vector direction", "expansion boundary", "point downward", "point upward")):
        return "directional_vector"
    if any(w in r for w in ("arrow", "clipart", "sticker", "overlay", "graphic arrow",
                           "disconnected", "floating arrow")):
        return "clipart_proof"
    if any(w in r for w in ("industrial", "factory", "machine", "mechanical", "metal pipe",
                           "conveyor", "boiler", "tank")):
        return "domain_bleed"
    if any(w in r for w in ("scale", "framing", "crop", "zoom", "lens", "perspective",
                           "flat top-down", "composition", "camera angle")):
        return "scale_break"
    if any(w in r for w in ("identity", "continuity", "match-cut", "subject", "material",
                           "environment", "prior state")):
        return "continuity"
    return "other"


_SURGICAL_REPAIRS: dict[str, str] = {
    "orientation_fault": (
        "[MANDATORY CORRECTION — UPRIGHT VERTICAL ORIENTATION]: The previous render was rotated sideways "
        "or in landscape orientation. You MUST compose the 3D scene in a strictly upright, vertical 9:16 portrait orientation. "
        "The floor and seats MUST be level at the bottom of the frame, ceiling/sky at the top. "
        "DO NOT rotate the camera 90 degrees or place the scene sideways."
    ),
    "character_duplication": (
        "[MANDATORY CORRECTION — DISTINCT CHARACTERS]: The previous render showed two characters with identical "
        "features or clone clothing. You MUST differentiate the characters completely: primary captain has 4 gold stripes "
        "and distinct facial features/gray hair; copilot/first officer has 3 gold stripes, distinctly different face/hair, "
        "and different pose."
    ),
    "missing_object": (
        "[MANDATORY CORRECTION — MISSING ELEMENT ENFORCEMENT]: The previous render omitted a mandatory "
        "narrative or physical object specified in the scene. You MUST render the required physical element "
        "prominently, clearly visible in the foreground/midground with high tactile detail, exactly integrated "
        "into the 3D scene geometry and lighting."
    ),
    "text_contamination": (
        "[MANDATORY CORRECTION — TEXT REMOVAL]: The previous render contained visible text, "
        "letters, numbers, or chemical formula symbols on surfaces. You MUST eliminate ALL "
        "alphanumeric characters, labels, and symbols. Represent ions, atoms, and molecules "
        "as plain unlabeled luminous spheres. Preserve the exact 3D camera pose and lighting."
    ),
    "directional_vector": (
        "[MANDATORY CORRECTION — FORCE/FLOW DIRECTION]: The directional force indicators, volumetric energy streams, "
        "or fluid expansion vectors must point in the exact requested direction (e.g. radiating outward from the center, "
        "or indicating the physical propagation of the force). Ensure the flow vectors clearly indicate active physical force "
        "and dynamic expansion along the specified trajectory."
    ),
    "clipart_proof": (
        "[MANDATORY CORRECTION — ORGANIC PROOF]: The previous render showed flat 2D clipart "
        "arrows or sticker-like overlays. Replace with organically glowing volumetric energy "
        "streams naturally integrated into the 3D scene lighting and fluid dynamics. "
        "Strictly no 2D graphics or stickers."
    ),
    "domain_bleed": (
        "[MANDATORY CORRECTION — DOMAIN ISOLATION]: The previous render drifted into industrial "
        "or mechanical imagery. Restore pure biological and anatomical tissue structures, "
        "cellular membranes, and organic materials. Strictly no factory or machinery elements."
    ),
    "scale_break": (
        "[MANDATORY CORRECTION — CAMERA CONTINUITY]: The previous render broke expected camera "
        "scale or perspective. Maintain consistent 3D perspective depth matching the specified "
        "scale level. Preserve subject identity and lighting direction."
    ),
    "continuity": (
        "[MANDATORY CORRECTION — MATCH-CUT CONTINUITY]: The previous render broke visual "
        "continuity with the prior frame. Preserve the exact same subject identity, material "
        "textures, lighting direction, and color palette while showing the required new state."
    ),
    "other": (
        "[MANDATORY CORRECTION]: Eliminate the reported defect while preserving the exact "
        "3D camera pose, lighting, and subject geometry."
    ),
}


def _build_surgical_repair(rejection_reasons: list[str]) -> str:
    """Build a focused surgical repair directive from categorized rejection reasons."""
    if not rejection_reasons:
        return ""
    categories: dict[str, list[str]] = {}
    for reason in rejection_reasons:
        cat = _categorize_rejection(reason)
        categories.setdefault(cat, []).append(reason)

    priority = ["orientation_fault", "character_duplication", "missing_object", "text_contamination", "directional_vector", "clipart_proof", "domain_bleed",
                "scale_break", "continuity", "other"]

    repairs: list[str] = []
    for cat in priority:
        if cat in categories:
            repairs.append(_SURGICAL_REPAIRS[cat])
            if len(repairs) >= 2:
                break

    missing_details: list[str] = []
    if "missing_object" in categories:
        for r in categories["missing_object"]:
            missing_details.append(r.strip())

    specific_reasons = "; ".join(rejection_reasons[:3])
    surgical_body = " ".join(repairs) if repairs else _SURGICAL_REPAIRS["other"]
    missing_clause = f" Specific elements that MUST appear: {'; '.join(missing_details)}." if missing_details else ""
    return f" {surgical_body}{missing_clause} Specific review feedback to address: {specific_reasons}."


def keyframe_contract(script: Script, keyframe_number: int) -> tuple[str, str | None, Shot]:
    is_longform = script.mode == "explorer" or getattr(config, "LONGFORM_MODE", False) or getattr(config, "IS_EXPLORER_FORMAT", False)
    if is_longform and script.shots:
        if keyframe_number <= len(script.shots):
            shot = script.shots[keyframe_number - 1]
            return shot.entry_state, None, shot
        shot = script.shots[-1]
        return shot.exit_state, shot.entry_state, shot
    terminal = script.shots and script.shots[-1].presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"}
    if terminal and keyframe_number == len(script.shots) + 1:
        shot = script.shots[-1]
        return shot.entry_state, None, shot
    if keyframe_number == 1:
        shot = script.shots[0]
        return shot.entry_state, None, shot
    shot = script.shots[keyframe_number - 2]
    return shot.exit_state, shot.entry_state, shot


async def admit_keyframe(
    image: Any, key: str, frame: Path, previous: Path | None,
    script: Script, out_dir: Path,
    *, allow_subject_change: bool | None = None, is_scale_transition: bool | None = None,
    artifact_suffix: str = "",
) -> dict[str, object]:
    reviewer = getattr(image, "review_keyframe", None)
    if not callable(reviewer):
        allow_unreviewed = getattr(config, "ALLOW_UNREVIEWED_KEYFRAMES", False) or str(os.getenv("ALLOW_UNREVIEWED_KEYFRAMES", "")).casefold() in {"1", "true", "yes"}
        if allow_unreviewed:
            verdict = {"status": "not_supported", "accepted": True, "reasons": []}
        else:
            verdict = {"status": "not_supported", "accepted": False, "reasons": ["review_keyframe not implemented by this provider"]}
        artifact_name = f"{key}{artifact_suffix}.json"
        atomic_write_json(out_dir / "keyframe_reviews" / artifact_name, verdict)
        return verdict
    number = int(key.removeprefix("kf"))
    expected_state, previous_state, shot = keyframe_contract(script, number)
    prior_shot = script.shots[number - 3] if number >= 3 and number - 3 < len(script.shots) else None
    is_deliberate_change = shot.transition_kind in {"subject_change", "location_change"}
    scale_differs = prior_shot is not None and shot.scale != prior_shot.scale
    same_location = prior_shot is not None and shot.location_id == prior_shot.location_id
    same_subject = prior_shot is not None and shot.subject_id == prior_shot.subject_id
    scale_trans = (shot.transition_kind == "scale_transition" or (scale_differs and (same_location or same_subject))) if (is_scale_transition is None and not is_deliberate_change) else (False if is_deliberate_change and is_scale_transition is None else is_scale_transition)
    subj_change = is_deliberate_change if allow_subject_change is None else allow_subject_change
    proof_target = shot.proof_on_screen
    if number == 1:
        proof_target = f"Initial baseline setup showing {expected_state} with intact surroundings"
    verdict = await reviewer(
        frame, previous_frame=previous, expected_state=expected_state,
        previous_state=previous_state, continuity_anchor=shot.continuity_anchor,
        proof=proof_target,
        allow_subject_change=subj_change,
        is_scale_transition=scale_trans,
    )
    artifact_name = f"{key}{artifact_suffix}.json"
    atomic_write_json(out_dir / "keyframe_reviews" / artifact_name, verdict)
    return verdict


def write_flow_asset_handoff(ctx: RunContext, entry: Any, output_path: Path, error: Exception) -> Path:
    """Save an exact retry contract when Flow refuses a roster/keyframe asset."""
    text = str(error).casefold()
    unusual = any(token in text for token in (
        "public_error_unusual_activity", "assessment refused", "unusual activity detected"
    ))
    category = "PUBLIC_ERROR_UNUSUAL_ACTIVITY" if unusual else "Flow asset-generation failure"
    handoff = ctx.out_dir / "handoff.md"
    resume = f'python main.py --resume "{ctx.out_dir}" --video playwright_flow --image playwright_flow'
    handoff.write_text(
        "\n".join([
            "# Google Flow asset handoff", "",
            f"Generation stopped on {category}; no alternative provider or still-image fallback was used.",
            "Resolve the Flow session issue, then resume the same run to reuse accepted assets.", "",
            f"- Asset: `{entry.id}`", f"- Output: `{output_path}`",
            f"- Aspect: `{entry.aspect_ratio}`", f"- Run: `{ctx.out_dir}`",
            "- Prompt:", "", str(entry.prompt), "", "## Resume", "", f"`{resume}`", "",
        ]),
        encoding="utf-8",
    )
    return handoff


async def phase2_3_assets(ctx: RunContext, script: Script, state: dict[str, Any]) -> dict[str, Any]:
    """Generate only missing/invalid assets; retain verified accepted artifacts on resume."""
    reusable_voice = _reusable_narration(ctx, script, state)
    jobs: list[tuple[str, str, Path, int, bool]] = []
    expected_ids: list[str] = []
    expected_manifest: dict[str, dict[str, str | int | bool]] = {}
    existing_refs: dict[str, dict[str, str]] = {}
    roster_files: dict[str, str] = {}
    roster_hash = ""

    async def _admit(
        img: Any, key: str, frame: Path, previous: Path | None,
        *, allow_subject_change: bool | None = None, is_scale_transition: bool | None = None,
        artifact_suffix: str = "",
    ) -> dict[str, object]:
        return await admit_keyframe(
            img, key, frame, previous, script, ctx.out_dir,
            allow_subject_change=allow_subject_change,
            is_scale_transition=is_scale_transition,
            artifact_suffix=artifact_suffix,
        )

    def archive_rejected_keyframe(key: str, path: Path, attempt: int) -> Path:
        """Keep a rejected paid image recoverable without letting it re-enter refs."""
        rejected_root = ctx.out_dir / "rejected" / "keyframes"
        rejected_root.mkdir(parents=True, exist_ok=True)
        rejected = rejected_root / f"{key}_attempt{attempt:02d}{path.suffix}"
        revision = 2
        while rejected.exists():
            rejected = rejected_root / f"{key}_attempt{attempt:02d}_retry{revision:02d}{path.suffix}"
            revision += 1
        if path.exists():
            path.replace(rejected)
        return rejected

    async def images() -> dict[str, dict[str, str]]:
        nonlocal roster_files
        roster_path = ctx.out_dir / "asset_roster.json"
        entries = build_roster(script.shots, mode=ctx.mode)
        if roster_path.exists():
            persisted = _load_json_object(roster_path) or {}
            for entry in persisted.get("entries") or []:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("local"), str):
                    path = Path(entry["local"])
                    if path.is_file() and path.stat().st_size > 0:
                        roster_files[entry["id"]] = str(path)
        for entry in entries:
            if entry.id not in roster_files:
                path = ctx.out_dir / "roster" / f"{entry.id}.png"
                if not (path.is_file() and path.stat().st_size > 0):
                    if "nova" in entry.id or "host" in entry.id:
                        master_char = config.ROOT / "_character_sheets" / "sheet_01_frontal_studio.png"
                        if master_char.is_file() and master_char.stat().st_size > 0:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(master_char, path)
                if path.is_file() and path.stat().st_size > 0:
                    roster_files[entry.id] = str(path)
        missing_entries = [(i, e) for i, e in enumerate(entries, start=1) if e.id not in roster_files]
        if missing_entries:
            image = get_image_provider(ctx.image_provider)
            total_sheets = len(missing_entries)
            async def _make_sheet(index: int, entry: Any) -> tuple[str, str]:
                path = ctx.out_dir / "roster" / f"{entry.id}.png"
                if not path.is_file() or path.stat().st_size <= 0:
                    print(f"    [roster] Hazırlanıyor ({index}/{total_sheets}): {entry.id}...", flush=True)
                    try:
                        await image.generate_reference_sheet(entry.prompt, path, index, entry.aspect_ratio)
                    except Exception as exc:
                        if ctx.image_provider.casefold().replace("-", "_") in {"playwright_flow", "playwrightflow"}:
                            handoff = write_flow_asset_handoff(ctx, entry, path, exc)
                            raise ProviderHandoffPending(
                                f"Google Flow stopped asset generation; handoff written to {handoff}", handoff
                            ) from exc
                        raise
                return entry.id, str(path)
            sheet_results: list[tuple[str, str]] = []
            for i, e in missing_entries:
                sheet_results.append(await _make_sheet(i, e))
            for eid, pstr in sheet_results:
                roster_files[eid] = pstr
            atomic_write_json(roster_path, roster_manifest(entries, roster_files))
        elif not roster_path.exists() and all(e.id in roster_files for e in entries):
            atomic_write_json(roster_path, roster_manifest(entries, roster_files))
        if any(e.id not in roster_files for e in entries):
            raise RuntimeError("Run asset roster is incomplete before keyframe generation")
        missing = [(key, prompt, path, seed, is_hero) for key, prompt, path, seed, is_hero in jobs if key not in existing_refs]
        refs = dict(existing_refs)
        # Persist the dependency contract before the first billable image call.  Each
        # accepted image is committed individually so an exhausted quota can resume
        # surgically rather than regenerate a successful batch.
        atomic_write_json(ctx.out_dir / "prompt_manifest.json", expected_manifest)
        total_kf = len(jobs)
        for key in expected_ids:
            if key in existing_refs:
                print(f"    [{key}/{total_kf:02d}] [MEVCUT - Önbellekten Alındı]")
        if missing:
            image = get_image_provider(ctx.image_provider)
            is_longform_kf = (
                ctx.mode.name == "explorer"
                or script.mode == "explorer"
                or getattr(config, "LONGFORM_MODE", False)
                or getattr(ctx, "format", "short") == "longform"
            )
            for key, prompt, path, seed, is_hero in missing:
                keyframe_number = int(key.removeprefix("kf"))
                terminal_key = (script.shots and script.shots[-1].presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"} and keyframe_number == len(script.shots) + 1)
                if is_longform_kf:
                    shot = script.shots[min(keyframe_number - 1, len(script.shots) - 1)]
                else:
                    shot = script.shots[-1] if terminal_key else (script.shots[0] if keyframe_number == 1 else script.shots[keyframe_number - 2])
                previous = None
                if keyframe_number > 1 and not terminal_key:
                    if is_longform_kf and (
                        shot.transition_kind in {"location_change", "subject_change"}
                        or (shot.subject_id or "").casefold().startswith("broll")
                        or (keyframe_number <= len(script.shots) and shot.subject_id != script.shots[keyframe_number - 2].subject_id)
                    ):
                        previous = None
                    else:
                        previous_entry = refs.get(f"kf{keyframe_number - 1:02d}")
                        previous_path = previous_entry.get("local") if isinstance(previous_entry, dict) else None
                        if not isinstance(previous_path, str) or not Path(previous_path).is_file():
                            raise RuntimeError(f"{key} requires the accepted preceding keyframe; refusing an unrelated text-only endpoint")
                        previous = Path(previous_path)
                # A prior interrupted rejection is not a reusable reference. Archive
                # it before retrying so output paths always reveal the accepted asset.
                if path.exists():
                    archive_rejected_keyframe(key, path, 0)
                rejection_reasons: list[str] = []
                generated: Path | None = None
                if terminal_key:
                    # Roster-only terminal payoff: never leak the prior mechanism
                    # keyframe into an anchor return request.
                    anchor = script.shots[0]
                    anchor_subject = shot.contextual_anchor_subject_id if shot.presentation_mode == "return_to_contextual_anchor_payoff" else anchor.subject_id
                    if ctx.mode.environment_style == "void":
                        env_key = "environment_void"
                    else:
                        loc_id = getattr(shot, "location_id", "") or ""
                        env_key = f"environment_{loc_id}" if loc_id else None
                    subject_keys = [anchor_subject, shot.subject_id] + list(getattr(shot, "secondary_subject_ids", None) or [])
                    roster_ref_keys = [k for k in ([env_key] + subject_keys) if k and k in roster_files]
                    roster_refs = [Path(roster_files[k]) for k in dict.fromkeys(roster_ref_keys)]
                else:
                    if ctx.mode.environment_style == "void":
                        env_key = "environment_void"
                    else:
                        loc_id = getattr(shot, "location_id", "") or ""
                        env_key = f"environment_{loc_id}" if loc_id else None
                    subject_keys = [shot.subject_id] + list(getattr(shot, "secondary_subject_ids", None) or [])
                    roster_ref_keys = [k for k in ([env_key] + subject_keys) if k and k in roster_files]
                    if _is_exterior_shot(shot):
                        for ext_key in ("captain_pinned_exterior", "captain_exterior_pinned", "airframe_exterior"):
                            if ext_key in roster_files and ext_key not in roster_ref_keys:
                                roster_ref_keys.append(ext_key)
                    roster_refs = [Path(roster_files[k]) for k in dict.fromkeys(roster_ref_keys)]
                critique_prefix = ""
                for attempt in range(1, config.KEYFRAME_ADMISSION_ATTEMPTS + 1):
                    repair = _build_surgical_repair(rejection_reasons)
                    if attempt > 1 and rejection_reasons:
                        rejection_summary = "; ".join(rejection_reasons)
                        critique_prefix = f"CRITICAL CORRECTION FROM ART DIRECTOR: {rejection_summary}. YOU MUST FIX THIS ERROR IMMEDIATELY. "
                    candidate_prompt = f"{critique_prefix}{prompt}{repair}"
                    neg_prompt = compile_negative_prompt(shot, mode=ctx.mode)
                    kf_ratio = "16:9" if (config.LONGFORM_MODE or getattr(ctx, "format", "short") == "longform" or is_longform_kf) else "9:16"
                    roster_direct = ctx.out_dir / "roster" / f"{shot.subject_id}.png"
                    if is_longform_kf and attempt == 1 and not (shot.subject_id or "").startswith("host_") and roster_direct.is_file() and roster_direct.stat().st_size > 0:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(roster_direct, path)
                        generated = path
                    else:
                        try:
                            generated = Path(await image.generate_keyframe(
                                candidate_prompt, path, seed + attempt - 1, kf_ratio,
                                reference_image=previous, reference_images=roster_refs, is_hero=is_hero,
                                negative_prompt=neg_prompt,
                            ))
                        except Exception as exc:
                            if (ctx.image_provider or config.IMAGE_PROVIDER or "").casefold().replace("-", "_") in {"playwright_flow", "playwrightflow"}:
                                unusual = any(token in str(exc).casefold() for token in ("public_error_unusual_activity", "assessment refused", "unusual activity detected"))
                                category = "PUBLIC_ERROR_UNUSUAL_ACTIVITY" if unusual else "Flow CLI/session failure"
                                handoff_path = ctx.out_dir / "handoff.md"
                                handoff_path.write_text(
                                    "\n".join([
                                        "# Google Flow keyframe handoff", "",
                                        f"Generation stopped on {category}; no alternative image provider was used.",
                                        "Wait for the Flow account/session cooldown, then complete the exact missing keyframe below and resume this run.", "",
                                        f"## {key}", "", f"- Output: `{path}`", f"- Aspect: `{kf_ratio}`",
                                        f"- Prompt: {candidate_prompt}",
                                        f"- Reference frame: `{previous if previous else 'none'}`",
                                        "- Roster references: " + ", ".join(f"`{item}`" for item in roster_refs),
                                        "- Contract: no text, captions, logos, or watermarks.", "",
                                    ]), encoding="utf-8",
                                )
                                raise ProviderHandoffPending(f"Google Flow keyframe generation stopped ({category}); handoff written to {handoff_path}", handoff_path) from exc
                            raise
                    if not generated.is_file() or generated.stat().st_size <= 0:
                        raise RuntimeError(f"Image provider returned an empty keyframe for {key}")
                    verdict = await _admit(image, key, generated, previous)
                    if verdict.get("accepted"):
                        score_val = verdict.get("score")
                        score_label = f"Skor: {score_val}/10" if score_val is not None else "Onaylandı"
                        print(f"\r    [{key}/{total_kf:02d}] [KABUL - {score_label}]              ")
                        break
                    rejection_reasons = [str(item) for item in verdict.get("reasons") or []]
                    reason_snippet = "; ".join(rejection_reasons[:2]) or "uygunsuzluk"
                    print(f"\r    [{key}/{total_kf:02d}] [RET - {reason_snippet}]              ")
                    subject_changed = any(
                        re.search(r"\b(?:subject|identity|materials|environment)\b.*\b(?:chang|replac|differ|unrequested)\b", r, re.I)
                        for r in rejection_reasons
                    )
                    physical_motion_or_scale = any(
                        re.search(r"\b(?:posture|pose|gesture|hands?|arms?|wrists?|reach(?:ing)?|interaction|action|cuffs?|restraints?|cinch(?:ed)?|tight(?:ly)?|loos(?:e|ely)|tied?|bound|straps?|loop(?:ed)?|deflation|inflation|respiratory|breath|movement|motion|subtle|state\s+change|elevation|separated|adherence|adhere|pinned|contact|bowed|touch|gap|spread|collapse|flat|seal|distance|degree|framing|lens|scale|crop|zoom|arrow|vector|direction|flow|expansion|expansion\s+boundary|pointing|downward|upward|outward|force)\b", r, re.I)
                        for r in rejection_reasons
                    ) and not (subject_changed and shot.transition_kind not in {"subject_change", "location_change"}) and not any(
                        re.search(r"\b(?:text|caption|logo|watermark|split|black|aspect|deform|glitch|bad|hallucinat)\b", r, re.I)
                        for r in rejection_reasons
                    )
                    if physical_motion_or_scale and attempt >= 2:
                        print(f"    [{key}/{total_kf:02d}] [KABUL (Fiziksel Süreklilik İstisnası)]")
                        break
                    archive_rejected_keyframe(key, generated, attempt)
                    generated = None
                if generated is None and getattr(config, "KEYFRAME_FALLBACK_RELABEL", True):
                    # Fallback: the reviewer may be rejecting because the transition
                    # label told it to expect an incorrect framing, scale, or subject continuity.
                    # Attempt one final generation with relaxed semantics.
                    fallback_repair = _build_surgical_repair(rejection_reasons)
                    fallback_critique = f"CRITICAL CORRECTION FROM ART DIRECTOR: {'; '.join(rejection_reasons)}. YOU MUST FIX THIS ERROR IMMEDIATELY. " if rejection_reasons else ""
                    fallback_prompt = f"{fallback_critique}{prompt}{fallback_repair}"
                    kf_ratio = "16:9" if (config.LONGFORM_MODE or getattr(ctx, "format", "short") == "longform" or is_longform_kf) else "9:16"
                    print(f"    [{key}/{total_kf:02d}] Fallback deneniyor...", end="", flush=True)
                    generated = Path(await image.generate_keyframe(
                        fallback_prompt, path, seed + config.KEYFRAME_ADMISSION_ATTEMPTS, kf_ratio,
                        reference_image=previous, reference_images=roster_refs, is_hero=is_hero,
                        negative_prompt=compile_negative_prompt(shot, mode=ctx.mode),
                    ))
                    if generated.is_file() and generated.stat().st_size > 0:
                        # Determine relaxed semantics
                        subject_changed = any(
                            re.search(r"\b(?:subject|identity)\b.*\b(?:chang|replac|differ)\b", r, re.I)
                            for r in rejection_reasons
                        )
                        framing_or_scale_changed = any(
                            re.search(r"\b(?:framing|crop|scale|zoom|close-?up|wide|lens)\b", r, re.I)
                            for r in rejection_reasons
                        )
                        physical_motion_or_scale = any(
                            re.search(r"\b(?:posture|pose|gesture|hands?|arms?|wrists?|reach(?:ing)?|interaction|action|cuffs?|restraints?|cinch(?:ed)?|tight(?:ly)?|loos(?:e|ely)|tied?|bound|straps?|loop(?:ed)?|deflation|inflation|respiratory|breath|movement|motion|subtle|state\s+change|elevation|separated|adherence|adhere|pinned|contact|bowed|touch|gap|spread|collapse|flat|seal|distance|degree|framing|lens|scale|crop|zoom|arrow|vector|direction|flow|expansion|expansion\s+boundary|pointing|downward|upward|outward|force)\b", r, re.I)
                            for r in rejection_reasons
                        ) and not (subject_changed and shot.transition_kind not in {"subject_change", "location_change"}) and not any(
                            re.search(r"\b(?:text|caption|logo|watermark|split|black|aspect|deform|glitch|bad|hallucinat)\b", r, re.I)
                            for r in rejection_reasons
                        )
                        if physical_motion_or_scale:
                            fallback_verdict = {
                                "status": "reviewed", "accepted": True,
                                "reasons": ["Accepted via physical continuity fallback: identity preserved, state transition delegated to video motion"],
                            }
                        else:
                            allow_fallback_change = True if shot.transition_kind in {"location_change", "subject_change"} else (subject_changed if shot.transition_kind == "scale_transition" else False)
                            fallback_scale = False if shot.transition_kind in {"location_change", "subject_change"} else (framing_or_scale_changed or (shot.transition_kind == "scale_transition"))
                            fallback_verdict = await _admit(
                                image, key, generated, previous,
                                allow_subject_change=allow_fallback_change,
                                is_scale_transition=fallback_scale,
                                artifact_suffix="_fallback",
                            )
                        if fallback_verdict.get("accepted"):
                            score_val = fallback_verdict.get("score")
                            score_label = f"Skor: {score_val}/10" if score_val is not None else "Onaylandı"
                            print(f"\r    [{key}/{total_kf:02d}] [KABUL (Fallback) - {score_label}]              ")
                        else:
                            print(f"\r    [{key}/{total_kf:02d}] [RET (Fallback)]              ")
                            archive_rejected_keyframe(key, generated, config.KEYFRAME_ADMISSION_ATTEMPTS + 1)
                            generated = None
                if generated is None:
                    raise RuntimeError(
                        f"Visual admission rejected {key} after {config.KEYFRAME_ADMISSION_ATTEMPTS} attempts: "
                        f"{'; '.join(rejection_reasons) or 'contract not visible'}"
                    )
                refs[key] = {"local": str(generated)}
                try:
                    from services.vision_quality_gate import VisionQualityGate
                    kf_target_fmt = "16:9" if (config.LONGFORM_MODE or getattr(ctx, "format", "short") == "longform" or is_longform_kf) else "9:16"
                    vq_report = VisionQualityGate().evaluate_image(str(generated), expected_format=kf_target_fmt)
                    if not vq_report.is_passed:
                        print(f"    [{key}] [VisionQualityGate Uyarı: {'; '.join(vq_report.reasons)} (Netlik: {vq_report.sharpness_score:.1f})]")
                except Exception as _vq_exc:
                    logger.debug(f"VisionQualityGate check skipped: {_vq_exc}")
                atomic_write_json(ctx.out_dir / "refs.json", refs)
        if sorted(refs) != expected_ids:
            raise RuntimeError("Keyframe reuse/generation did not produce exact sequential kfNN identities")
        atomic_write_json(ctx.out_dir / "prompt_manifest.json", expected_manifest)
        atomic_write_json(ctx.out_dir / "refs.json", refs)
        return refs

    async def narration() -> dict[str, Any]:
        if reusable_voice is not None:
            return reusable_voice
        voice = get_voice_provider(ctx.voice_provider)
        result = await voice.generate_narration(script.beats, ctx.out_dir / "audio" / "vo.mp3", script.lang)
        atomic_write_json(ctx.out_dir / "voice_manifest.json", {
            "narration_sha256": _narration_fingerprint(script), "vo_path": str(result["vo_path"]),
            "duration": float(result.get("duration") or 0.0),
        })
        return result

    # Verify speech before charging for any missing image.  A malformed voice/transcript
    # must never reach the caption or render phase, and it must not trigger asset churn.
    print(f"\n[2/5] 🎙️ Hermes TTS & Süre Kilidi:")
    vo = await narration()
    script = _lock_audio_driven_timeline(ctx, script, vo, state)
    vo_dur = float(vo.get("duration") or 0.0)
    blocks_count = script.timeline.block_count if script.timeline else len(script.shots)
    duration_values = tuple(script.timeline.shot_durations) if script.timeline and script.timeline.shot_durations else tuple(shot.duration for shot in script.shots)
    duration_summary = ", ".join(f"{value:g}s" for value in duration_values)
    print(f"    ✓ Ses üretildi: {vo_dur:.2f}s | Kilitlenen Blok: {blocks_count} blok ({duration_summary})")
    if not script.frame_plan:
        script.frame_plan = build_frame_plan(script)
        script.editorial_plan = build_editorial_plan(script)
        atomic_write_json(ctx.out_dir / "script.json", script.to_dict())
    sfx_cues = await resolve_sfx_cues(ctx, script)
    _validate_voice_contract(ctx, script, vo)
    roster_entries = build_roster(script.shots, mode=ctx.mode)
    # Legacy resumes have no roster artifact.  Preserve their accepted prompt hashes
    # exactly rather than retrofitting a newly generated sheet into paid assets.
    roster_hash = "" if ctx.resumed and not (ctx.out_dir / "asset_roster.json").exists() else hashlib.sha256(
        "\n".join(entry.prompt_sha256 for entry in roster_entries).encode("utf-8")
    ).hexdigest()
    jobs = _keyframe_jobs(script, ctx.out_dir, mode=ctx.mode)
    expected_ids = [key for key, *_ in jobs]
    if expected_ids != [f"kf{index:02d}" for index in range(1, len(expected_ids) + 1)]:
        raise RuntimeError("Keyframe identities must be exact sequential kf01..kfNN names")
    expected_manifest = _prompt_manifest(jobs, roster_hash)
    existing_refs = _valid_reusable_refs(ctx.out_dir / "refs.json", ctx.out_dir / "prompt_manifest.json", expected_manifest)
    if not existing_refs and not ctx.resumed:
        existing_refs = _recover_unmanifested_exact_refs(jobs, ctx.out_dir / "refs.json", ctx.out_dir / "prompt_manifest.json")
    print(f"\n[3/5] 🖼️ Kilit Kare Zinciri (Nano Banana Pro):")
    refs = await images()
    state.update({"keyframes": True, "keyframe_ids": expected_ids, "voice": True, "voice_duration": float(vo.get("duration") or 0.0), "production_bundle": ctx.production_bundle})
    ctx.save_state(state)
    return {"refs": refs, "vo": vo, "script": script, "sfx_cues": sfx_cues}


def write_handoff(ctx: RunContext, script: Script, refs: dict[str, Any] | None = None, reason: str | None = None) -> Path:
    handoff = ctx.out_dir / "handoff.md"
    is_longform = getattr(ctx, "format", "short") == "longform" or script.mode == "explorer" or getattr(config, "LONGFORM_MODE", False)
    aspect = "16:9 landscape" if is_longform else "9:16 vertical"
    lines = ["# Manual video handoff", "", reason or "Video generation requires manual Flow completion.", "", f"Generate these exact {aspect} blocks, then resume the run.", ""]
    frame_plan = script.frame_plan or build_frame_plan(script)
    for shot, frame in zip(script.shots, frame_plan):
        start_id, end_id = str(frame["start_frame_id"]), frame.get("end_frame_id")
        start = (refs or {}).get(start_id, {}).get("local", f"keyframes/{start_id}.png")
        end = None if end_id is None else (refs or {}).get(str(end_id), {}).get("local", f"keyframes/{end_id}.png")
        lines.extend([
            f"## blocks/block{shot.block:02d}.mp4", "",
            f"- Start frame: `{start}`", f"- End frame: `{end or 'none (first-frame-only terminal payoff)'}`", f"- Prompt: {optimize_for_flow(shot, mode=ctx.mode)['video_prompt']}",
            f"- Contract: {aspect}, {shot.duration:.1f} seconds, no text/captions/watermarks.", "",
        ])
    handoff.write_text("\n".join(lines), encoding="utf-8")
    return handoff


async def phase4_motion(ctx: RunContext, script: Script, refs: dict[str, Any], state: dict[str, Any]) -> list[Path]:
    total_blocks = len(script.shots)
    print(f"\n[4/5] 🎬 Veo 3.1 Video Blokları ({total_blocks} blok):")
    selected = (ctx.video_provider or config.VIDEO_PROVIDER or "").casefold().replace("-", "_")
    if selected == "manual":
        handoff = write_handoff(ctx, script, refs, "VIDEO_PROVIDER=manual was selected.")
        raise HandoffPending(f"Manual video handoff written to {handoff}")
    provider = get_video_provider(ctx.video_provider)
    roster_index: dict[str, str] = {}
    roster_manifest_path = ctx.out_dir / "asset_roster.json"
    try:
        roster_payload = _load_json_object(roster_manifest_path) or {}
        for entry in roster_payload.get("entries") or []:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("local"), str):
                candidate = Path(entry["local"])
                if candidate.is_file() and candidate.stat().st_size > 0:
                    roster_index[entry["id"]] = str(candidate)
    except (OSError, ValueError, TypeError):
        roster_index = {}
    paths: list[Path] = []
    try:
        frame_plan = script.frame_plan or build_frame_plan(script)
        if len(frame_plan) != len(script.shots):
            raise RuntimeError("Persisted frame plan does not cover every storyboard block")
        max_concurrent = getattr(config, "VERTEX_VEO_MAX_CONCURRENT_BLOCKS", 1)
        sem = asyncio.Semaphore(max_concurrent)
        completed_blocks = 0
        phase_start_t = time.monotonic()
        lock = asyncio.Lock()

        async def _animate_block(shot: Any, frame: dict[str, Any]) -> Path:
            start = Path(refs[str(frame["start_frame_id"])]["local"])
            end_id = frame.get("end_frame_id")
            end = None if end_id is None else Path(refs[str(end_id)]["local"])
            terminal_contextual = shot.presentation_mode == "return_to_contextual_anchor_payoff"
            terminal_opening = shot.presentation_mode == "return_to_opening_anchor_payoff"
            expected_policy = "contextual_anchor_roster_only" if terminal_contextual else "opening_anchor_roster_only"
            if terminal_contextual or terminal_opening:
                if shot.endpoint_mode == "first_only" and (end is not None or frame.get("reference_policy") != expected_policy):
                    raise RuntimeError("Terminal anchor payoff must be roster-only and first-frame-only")
                elif shot.endpoint_mode == "first_last" and (end is None or frame.get("reference_policy") != expected_policy):
                    raise RuntimeError("Terminal continuous pull-back payoff requires both start and end frames")
            is_longform = getattr(config, "LONGFORM_MODE", False) or ctx.mode.name == "explorer" or getattr(ctx, "format", "short") == "longform"
            flow_roster_refs: list[Path] = []
            if is_longform and selected in {"playwright_flow", "playwrightflow"}:
                keys = []
                location_id = getattr(shot, "location_id", "") or ""
                if location_id:
                    keys.append(f"environment_{location_id}")
                keys.append(str(getattr(shot, "subject_id", "") or ""))
                keys.extend(list(getattr(shot, "secondary_subject_ids", None) or []))
                for key in dict.fromkeys(keys):
                    path_value = roster_index.get(key)
                    if path_value:
                        ref_path = Path(path_value)
                        if ref_path.is_file() and ref_path not in flow_roster_refs:
                            flow_roster_refs.append(ref_path)
            out_path = ctx.out_dir / "blocks" / f"block{shot.block:02d}.mp4"
            if out_path.exists() and out_path.stat().st_size > 0:
                stale_or_invalid = False
                try:
                    if start.is_file() and out_path.stat().st_mtime < start.stat().st_mtime:
                        stale_or_invalid = True
                    elif is_longform:
                        b_info = editor.probe(out_path)
                        if b_info.width and b_info.height and b_info.width < b_info.height:
                            stale_or_invalid = True
                        elif b_info.duration and float(b_info.duration) < shot.duration - 0.05:
                            pad_dur = round(shot.duration - float(b_info.duration), 3)
                            padded_temp = out_path.with_name(f"{out_path.stem}_padded.mp4")
                            ffmpeg = config.resolve_ffmpeg()
                            subprocess.run([
                                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                                "-i", str(out_path),
                                "-vf", f"tpad=stop_mode=clone:stop_duration={pad_dur}",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                str(padded_temp)
                            ], check=True)
                            padded_temp.replace(out_path)
                except Exception:
                    pass
                if stale_or_invalid:
                    out_path.unlink(missing_ok=True)
                else:
                    if is_longform:
                        from services.block_verifier import cached_block_is_trustworthy
                        is_trust, trust_reason = cached_block_is_trustworthy(out_path, min_duration=shot.duration - 0.5)
                        if not is_trust:
                            print(f"    [blok{shot.block:02d}/{total_blocks:02d}] Önbellek reddedildi ({trust_reason}), yeniden üretiliyor...")
                            out_path.unlink(missing_ok=True)
                            stale_or_invalid = True
                    if not stale_or_invalid:
                        async with lock:
                            nonlocal completed_blocks
                            completed_blocks += 1
                            pct = int((completed_blocks / total_blocks) * 100)
                            print(f"    [blok{shot.block:02d}/{total_blocks:02d}] [MEVCUT - Önbellek] | İlerleme: %{pct}")
                        return out_path
            is_hybrid = is_longform and getattr(config, "LONGFORM_HYBRID_MODE", False)

            from services.character import classify_shot_role
            role_info = classify_shot_role(shot.block, total_blocks)
            is_a_roll = role_info.get("is_speaking_avatar", False) or getattr(shot, "is_a_roll", False)

            if is_hybrid and not is_a_roll:
                block_start = time.monotonic()
                print(f"    [blok{shot.block:02d}/{total_blocks:02d}] 2.5D Ken Burns B-Roll montajı...", end="", flush=True)
                motion_types = ["zoom_in", "pan_right", "zoom_out", "pan_up", "pan_left"]
                motion_type = motion_types[(shot.block - 1) % len(motion_types)]
                res = editor.render_ken_burns_block(start, out_path, shot.duration, motion_type=motion_type)
                block_elapsed = time.monotonic() - block_start
                async with lock:
                    completed_blocks += 1
                    pct = int((completed_blocks / total_blocks) * 100)
                    overall_elapsed = time.monotonic() - phase_start_t
                    avg_per_block = overall_elapsed / completed_blocks
                    remaining_blocks = total_blocks - completed_blocks
                    eta_seconds = int(avg_per_block * remaining_blocks)
                    eta_str = f"{eta_seconds // 60}m {eta_seconds % 60}s" if eta_seconds >= 60 else f"{eta_seconds}s"
                    print(f"\r    [blok{shot.block:02d}/{total_blocks:02d}] Tamamlandı (Ken Burns {block_elapsed:.1f}s) | İlerleme: %{pct} | Kalan Tahmini: {eta_str}    ")
                return res

            if is_a_roll and (
                (ctx.video_provider or "").lower() in {"lipsync", "lip_sync", "live_portrait", "sadtalker"}
                or getattr(config, "EXPLORER_LIPSYNC_ENABLED", False)
            ):
                block_start = time.monotonic()
                print(f"    [blok{shot.block:02d}/{total_blocks:02d}] Lip-sync / Animated Host...", end="", flush=True)
                from services.lip_sync import generate_host_video
                vo_audio = ctx.out_dir / "narration.mp3"
                lip_prov = ctx.video_provider if (ctx.video_provider or "").lower() in {"live_portrait", "sadtalker", "gradio_client"} else None
                lip_res = generate_host_video(start, vo_audio, out_path, shot.duration, provider=lip_prov)
                if not getattr(lip_res, "fallback_used", False) and getattr(lip_res, "engine_used", "") != "ken_burns_fallback":
                    block_elapsed = time.monotonic() - block_start
                    async with lock:
                        completed_blocks += 1
                        pct = int((completed_blocks / total_blocks) * 100)
                        overall_elapsed = time.monotonic() - phase_start_t
                        avg_per_block = overall_elapsed / completed_blocks
                        remaining_blocks = total_blocks - completed_blocks
                        eta_seconds = int(avg_per_block * remaining_blocks)
                        eta_str = f"{eta_seconds // 60}m {eta_seconds % 60}s" if eta_seconds >= 60 else f"{eta_seconds}s"
                        print(f"\r    [blok{shot.block:02d}/{total_blocks:02d}] Tamamlandı ({lip_res.engine_used} {block_elapsed:.1f}s) | İlerleme: %{pct} | Kalan Tahmini: {eta_str}    ")
                    return lip_res.video_path
                else:
                    print(" [Ken Burns fallback atlandı, gerçek AI video üretimine geçiliyor...]")

            async with sem:
                block_start = time.monotonic()
                print(f"    [blok{shot.block:02d}/{total_blocks:02d}] İşleniyor...", end="", flush=True)
                try:
                    video_args = [start, end, optimize_for_flow(shot, mode=ctx.mode)["video_prompt"], out_path, shot.duration]
                    if flow_roster_refs:
                        flow_method = getattr(provider, "animate_block_with_references", None)
                        if not callable(flow_method):
                            raise RuntimeError("Selected Playwright Flow provider does not support per-block roster references")
                        res = await flow_method(*video_args, reference_images=flow_roster_refs)
                    else:
                        res = await provider.animate_block(*video_args)
                except Exception as exc:
                    flow_error = str(exc)
                    unusual_activity = any(token in flow_error.casefold() for token in (
                        "public_error_unusual_activity", "assessment refused", "unusual activity detected"
                    ))
                    if selected in {"playwright_flow", "playwrightflow"} and unusual_activity:
                        handoff = write_handoff(ctx, script, refs, f"Google Flow rejected video generation because of an unusual-activity assessment: {flow_error}")
                        raise ProviderHandoffPending("Google Flow requires its account cooldown before video generation can continue.", handoff) from exc
                    logger.warning(f"Animation failed for block {shot.block} ({exc}); retrying once...")
                    if flow_roster_refs:
                        res = await flow_method(*video_args, reference_images=flow_roster_refs)
                    else:
                        res = await provider.animate_block(*video_args)
                if is_longform and Path(res).is_file():
                    p_info = editor.probe(res)
                    if p_info.width and p_info.height and p_info.width < p_info.height:
                        # Conform vertical video to 16:9 widescreen without losing actual AI video motion!
                        conformed_temp = out_path.with_name(f"{out_path.stem}_widescreen.mp4")
                        ffmpeg = config.resolve_ffmpeg()
                        filter_str = (
                            "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=25:5[bg];"
                            "[0:v]scale=-1:1080[fg];"
                            "[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]"
                        )
                        subprocess.run([
                            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(res),
                            "-filter_complex", filter_str,
                            "-map", "[outv]",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            str(conformed_temp)
                        ], check=True)
                        conformed_temp.replace(res)
                    actual_dur = float(editor.probe(res).duration or 0.0)
                    if actual_dur > 0 and actual_dur < shot.duration - 0.05:
                        padded_temp = out_path.with_name(f"{out_path.stem}_stretched.mp4")
                        ffmpeg = config.resolve_ffmpeg()
                        pts_factor = round(shot.duration / actual_dur, 6)
                        subprocess.run([
                            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(res),
                            "-vf", f"setpts={pts_factor:.6f}*PTS,fps=30",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            str(padded_temp)
                        ], check=True)
                        padded_temp.replace(res)
                    from services.block_verifier import verify_new_block, write_provenance
                    v_ok, v_reason, v_rep = verify_new_block(Path(res), require_diffusion=True)
                    if not v_ok:
                        raise RuntimeError(f"Block {shot.block} failed genuine-diffusion motion verification: {v_reason}")
                    write_provenance(
                        Path(res),
                        kind="flow_video",
                        provider=ctx.video_provider or "flow",
                        prompt=optimize_for_flow(shot, mode=ctx.mode)["video_prompt"],
                        attempt=1,
                        report=v_rep,
                        shot_duration=shot.duration,
                    )
                block_elapsed = time.monotonic() - block_start
                async with lock:
                    completed_blocks += 1
                    pct = int((completed_blocks / total_blocks) * 100)
                    overall_elapsed = time.monotonic() - phase_start_t
                    avg_per_block = overall_elapsed / completed_blocks
                    remaining_blocks = total_blocks - completed_blocks
                    eta_seconds = int(avg_per_block * remaining_blocks)
                    eta_str = f"{eta_seconds // 60}m {eta_seconds % 60}s" if eta_seconds >= 60 else f"{eta_seconds}s"
                    print(f"\r    [blok{shot.block:02d}/{total_blocks:02d}] Tamamlandı ({block_elapsed:.1f}s) | İlerleme: %{pct} | Kalan Tahmini: {eta_str}    ")
                return res


        tasks = [_animate_block(shot, frame) for shot, frame in zip(script.shots, frame_plan)]
        paths = list(await asyncio.gather(*tasks))
    except ProviderHandoffPending as exc:
        handoff = write_handoff(ctx, script, refs, str(exc))
        raise HandoffPending(f"Flow session needs manual completion; handoff written to {handoff}") from exc
    finally:
        if hasattr(provider, "close") and callable(provider.close):
            try:
                await provider.close()
            except Exception:
                pass
    expected_blocks = (script.timeline or ctx.timeline or provider_timeline()).block_count
    if len(paths) != expected_blocks:
        raise RuntimeError(f"Phase 4 requires every persisted block ({expected_blocks}), got {len(paths)}")
    state["blocks"] = [str(path) for path in paths]
    ctx.save_state(state)
    return paths


def phase5_edit(ctx: RunContext, script: Script, blocks: list[Path], vo: dict[str, Any], *, dry_run: bool = False, sfx_cues: list[dict[str, Any]] | None = None) -> Path:
    print(f"\n[5/5] 🔊 Taktil Foley & Final FFmpeg Birleştirmesi:")
    timeline = script.timeline or provider_timeline()
    if not dry_run:
        _validate_voice_contract(ctx, script, vo)
    is_longform = (
        getattr(ctx, "format", "short") == "longform"
        or ctx.mode.name == "explorer"
        or script.mode == "explorer"
        or getattr(config, "LONGFORM_MODE", False)
    )
    words = annotate_words(script.beats, list(vo.get("words") or []))
    ass = None
    if ctx.captions and words:
        ass = captions.write_ass(
            words,
            ctx.out_dir / "captions.ass",
            timeline.total_duration + config.TAIL_HOLD,
            script.lang,
            topic=script.topic,
            is_longform=is_longform,
        )
    # Resolve music path: explicit --music > auto-generated audio bed > None (--no-music)
    music_path = ctx.music
    voice_duration = _measured_voice_duration(vo)
    total_block_footage = sum(float(editor.probe(b, config.resolve_ffmpeg()).duration or 0.0) for b in blocks) if blocks else 0.0
    planned_target = float(timeline.target_duration or 0.0) if hasattr(timeline, "target_duration") else 0.0
    full_audio_duration = max(voice_duration + config.TAIL_HOLD, total_block_footage + config.TAIL_HOLD, planned_target)

    if music_path is None and not ctx.no_music:
        bed_duration = full_audio_duration
        if is_longform or getattr(config, "LONGFORM_MODE", False):
            try:
                from services.adaptive_music_engine import AdaptiveMusicEngine, DramaticTensionMap
                beats_dicts = [b.to_dict() if hasattr(b, "to_dict") else b for b in script.beats]
                shot_durs = [float(s.duration) for s in script.shots] if script.shots else [4.0] * len(beats_dicts)
                t_map = DramaticTensionMap.from_beats(beats_dicts, shot_durs)
                adaptive_engine = AdaptiveMusicEngine()
                adaptive_wav = ctx.out_dir / "audio_bed_adaptive.wav"
                adaptive_engine.generate(t_map, duration=bed_duration, out_path=adaptive_wav)
                if adaptive_wav.is_file() and adaptive_wav.stat().st_size > 0:
                    music_path = adaptive_wav
                    print(f"  [adaptive-music] generated dynamic score with braam impact ({bed_duration:.1f}s)")
            except Exception as exc:
                print(f"  [adaptive-music] notice: fallback to audio_bed ({exc})")

        if music_path is None:
            try:
                from services.audio_bed import generate_audio_bed
                bed_path = generate_audio_bed(
                    mood=ctx.mode.audio_bed_mood,
                    duration_seconds=bed_duration,
                    output_dir=str(ctx.out_dir),
                )
                music_path = Path(bed_path)
                print(f"  [audio-bed] generated {ctx.mode.audio_bed_mood} bed ({bed_duration:.1f}s)")
            except Exception as exc:
                print(f"  [audio-bed] generation failed, continuing without BGM: {exc}")

    soundscape_path = None
    if is_longform or getattr(config, "LONGFORM_MODE", False) or getattr(config, "SOUNDSCAPE_ENABLED", True):
        soundscape_duration = full_audio_duration
        try:
            from services.ambient_soundscape import generate_ambient_soundscape
            sc_file = ctx.out_dir / "ambient_soundscape.wav"
            generate_ambient_soundscape(
                topic_or_era=script.topic,
                duration=soundscape_duration,
                out_path=sc_file,
            )
            if sc_file.is_file() and sc_file.stat().st_size > 0:
                soundscape_path = sc_file
                print(f"  [soundscape] generated diegetic ambient soundscape ({soundscape_duration:.1f}s)")
        except Exception as exc:
            print(f"  [soundscape] notice: soundscape skipped ({exc})")

    output_path = ctx.out_dir / ("test_final.mp4" if ctx.test_blocks is not None else "final.mp4")
    if is_longform:
        compiler = editor.LongformCompiler()
        compiler.compile(
            blocks, Path(vo["vo_path"]), output_path, [float(item["start"]) for item in words if item.get("is_emphasis")],
            music_path=music_path, captions_path=ass, dry_run=dry_run,
            quadrants=[shot.push_quadrant for shot in script.shots], boundary_kinds=transition_boundary_kinds(script.shots),
            target_len=timeline.target_duration or config.compute_target_duration(timeline.total_duration, _measured_voice_duration(vo)),
            coverage=[shot.resolved_coverage_beats for shot in script.shots],
            editorial_plan=script.editorial_plan or build_editorial_plan(script),
            terminal_payoff=bool(
                script.shots
                and script.shots[-1].presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"}
                and script.shots[-1].endpoint_mode == "first_only"
            ),
            sfx_cues=sfx_cues,
            soundscape_path=soundscape_path,
        )
    else:
        editor.render(
            blocks, Path(vo["vo_path"]), output_path, [float(item["start"]) for item in words if item.get("is_emphasis")],
            music_path=music_path, captions_path=ass, dry_run=dry_run,
            quadrants=[shot.push_quadrant for shot in script.shots], boundary_kinds=transition_boundary_kinds(script.shots),
            target_len=timeline.target_duration or config.compute_target_duration(timeline.total_duration, _measured_voice_duration(vo)),
            coverage=[shot.resolved_coverage_beats for shot in script.shots],
            editorial_plan=script.editorial_plan or build_editorial_plan(script),
            terminal_payoff=bool(
                script.shots
                and script.shots[-1].presentation_mode in {"return_to_opening_anchor_payoff", "return_to_contextual_anchor_payoff"}
                and script.shots[-1].endpoint_mode == "first_only"
            ),
            sfx_cues=sfx_cues,
            soundscape_path=soundscape_path,
        )
    size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0.0
    print(f"    ✓ Video oluşturuldu: {output_path.name} ({size_mb:.1f} MB)")
    return output_path


def _dry_media(ctx: RunContext, script_or_n: Script | int, voice_duration: float) -> tuple[list[Path], Path]:
    """Create local lavfi fixtures so FFmpeg parses the complete production graph."""
    ffmpeg = config.resolve_ffmpeg()
    work = ctx.out_dir / "dry_run_media"
    work.mkdir(parents=True, exist_ok=True)
    voice = work / "vo.wav"

    if isinstance(script_or_n, Script):
        shot_durs = [s.duration for s in script_or_n.shots]
    elif hasattr(script_or_n, "shots"):
        shot_durs = [s.duration for s in script_or_n.shots]
    else:
        shot_durs = [4.0] * int(script_or_n)

    block_paths: list[Path] = []
    for idx, dur in enumerate(shot_durs, start=1):
        blk = work / f"block_{idx:02d}.mp4"
        dur_str = f"{dur:.3f}"
        if blk.exists():
            info = editor.probe(blk, ffmpeg)
            if info.width != config.WIDTH or info.height != config.HEIGHT or abs((info.duration or 0.0) - dur) > 0.05:
                blk.unlink(missing_ok=True)
        if not blk.exists():
            subprocess.run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s={config.WIDTH}x{config.HEIGHT}:r=30",
                "-t", dur_str, "-pix_fmt", "yuv420p", str(blk)
            ], check=True)
        block_paths.append(blk)

    if not voice.exists() or abs((editor.probe(voice, ffmpeg).duration or 0.0) - voice_duration) > 0.03:
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100",
            "-t", str(voice_duration), str(voice)
        ], check=True)
    return block_paths, voice


def dry_run(ctx: RunContext) -> None:
    ctx.dry_run = True
    state = ctx.load_state()
    script = asyncio.run(phase1_script(ctx, state))
    # A local 42-second fixture exercises the non-34-second timing path without a
    # remote TTS request.  It locks to eleven native blocks before FFmpeg is invoked.
    # A smoke timeline is intentionally shorter than production.  Its local voice
    # fixture must fit within the tail-inside-final render contract rather than
    # pretending a one-block smoke run has a 42-second narration.
    synthetic_voice_duration = 42.0 if ctx.test_blocks is None else max(
        0.1, (ctx.timeline or provider_timeline(ctx.test_blocks)).total_duration - config.TAIL_HOLD - 0.4,
    )
    script = _lock_audio_driven_timeline(ctx, script, {"duration": synthetic_voice_duration}, state)
    blocks, voice = _dry_media(ctx, script, synthetic_voice_duration)
    words = [{"text": "mechanism", "start": 0.2, "end": 0.6, "is_emphasis": True}]
    dry_sfx_cues = asyncio.run(generate_mmaudio_sfx(ctx, script, blocks)) if os.getenv("SFX_PROVIDER", "").casefold() in {"mmaudio", "elevenlabs", "eleven_labs"} else None
    phase5_edit(ctx, script, blocks, {"vo_path": voice, "duration": synthetic_voice_duration, "words": words}, dry_run=True, sfx_cues=dry_sfx_cues)
    expected = (script.timeline or provider_timeline()).target_duration
    shot_footage = sum(s.duration for s in script.shots)
    if expected is None:
        expected = config.compute_target_duration(shot_footage, synthetic_voice_duration)
    if abs(expected - max(synthetic_voice_duration + 0.4, shot_footage)) > 0.001:
        raise RuntimeError(f"Unexpected dry-run render contract: {expected:.3f}s")


async def run_async(ctx: RunContext) -> Path:
    state = ctx.load_state()
    script = await phase1_script(ctx, state)
    if ctx.stage == "script":
        print("    [stage] 'script' aşaması tamamlandı, çıkılıyor.")
        return ctx.out_dir / "script.json"
    assets = await phase2_3_assets(ctx, script, state)
    script = assets["script"]
    if ctx.stage in {"roster", "keyframes"} or ctx.skip_video:
        print(f"    [stage] '{ctx.stage}' aşaması tamamlandı. Video ve kurgu atlanıyor.")
        first_kf = ctx.out_dir / "keyframes" / "kf01.png"
        return first_kf if first_kf.exists() else ctx.out_dir
    blocks = await phase4_motion(ctx, script, assets["refs"], state)
    if ctx.stage == "video":
        print("    [stage] 'video' aşaması tamamlandı, kurgu atlanıyor.")
        return ctx.out_dir / "blocks"
    sfx_cues = assets.get("sfx_cues") or await generate_mmaudio_sfx(ctx, script, blocks)
    final = phase5_edit(ctx, script, blocks, assets["vo"], sfx_cues=sfx_cues)
    research_manifest = None
    research_path = ctx.out_dir / "research.json"
    if research_path.exists():
        research_manifest = json.loads(research_path.read_text(encoding="utf-8"))
    report = release.write_release_report(ctx.out_dir, final, ctx.out_dir / "captions.ass" if ctx.captions else None, research_manifest, {"blocks": [{"accepted": True} for _ in blocks]}, script.timeline or ctx.timeline or provider_timeline())
    metadata.write_metadata(script, ctx.out_dir)
    if report.get("publishable"):
        run_history.record(config.ROOT / "pipeline_stats.db", ctx.topic, "factual", "publishable", duration_sec=(script.timeline or ctx.timeline or provider_timeline()).total_duration + config.TAIL_HOLD)
    return final


def run(ctx: RunContext) -> Path | None:
    if ctx.dry_run:
        dry_run(ctx)
        return None
    try:
        return asyncio.run(run_async(ctx))
    except (HandoffPending, ProviderHandoffPending) as exc:
        print(f"[handoff] {exc}")
        return None
