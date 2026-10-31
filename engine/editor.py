"""Phase 5 post FX: probe, filtergraph construction, final encode.

Every ffmpeg contract used here was compiled empirically with `-f null` before this file
was written. Notable traps that are already solved below:
  * aformat needs `sample_rates=`/`channel_layouts=` keys, not positional args.
  * ffmpeg 7.1 renamed `-filter_complex_script` to `-/filter_complex`.
  * loudnorm resamples to 192k internally, so a trailing aformat restores 44.1kHz.
  * zoompan MUST set d=1 (else it holds 90 frames and the video freezes) and fps=30
    (else it silently resamples to 25).
  * A voiceover label consumed by both sidechaincompress and amix errors with
    "matches no streams" -> asplit=2 gives each consumer its own copy.
  * gblur's sigma is not an expression, so a focus pull has to be built as
    split -> blur one branch -> blend with a time-dependent alpha.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import captions
import config


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """ffmpeg echoes input paths and metadata back on stderr. Without an explicit utf-8
    decode, a non-ASCII path (this project lives under "Masaüstü") raises
    UnicodeDecodeError while parsing the error we were trying to report."""
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


# --------------------------------------------------------------------------------------
# Probe
# --------------------------------------------------------------------------------------

@dataclass
class MediaInfo:
    path: Path
    duration: float | None
    width: int | None
    height: int | None
    fps: float | None
    has_video: bool
    has_audio: bool


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
_DIMS_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"([\d.]+)\s*fps")
_FREEZE_DURATION_RE = re.compile(r"freeze_duration:\s*([\d.]+)")
_FREEZE_START_RE = re.compile(r"freeze_start:\s*([\d.]+)")


def probe(path: str | Path, ffmpeg: str | None = None) -> MediaInfo:
    """Parse `ffmpeg -i` stderr. No ffprobe binary is bundled with imageio-ffmpeg."""
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    path = Path(path)
    proc = _run([ffmpeg, "-hide_banner", "-i", str(path)])
    err = proc.stderr or ""

    duration = None
    if (m := _DUR_RE.search(err)):
        h, mnt, s = m.groups()
        duration = int(h) * 3600 + int(mnt) * 60 + float(s)

    width = height = None
    if (m := _DIMS_RE.search(err)):
        width, height = int(m.group(1)), int(m.group(2))

    fps = None
    if (m := _FPS_RE.search(err)):
        try:
            fps = float(m.group(1))
        except ValueError:
            fps = None

    has_video = "Video:" in err
    has_audio = "Audio:" in err

    if duration is None:
        duration = _probe_via_imageio(path)

    return MediaInfo(path, duration, width, height, fps, has_video, has_audio)


def _probe_via_imageio(path: Path) -> float | None:
    try:
        import imageio_ffmpeg
        reader = imageio_ffmpeg.read_frames(str(path))
        meta = reader.__next__()
        reader.close()
        return meta.get("duration")
    except Exception:
        return None


@dataclass(frozen=True)
class BlockQuality:
    """Result of the deterministic, local admission gate for one generated block."""

    accepted: bool
    reasons: tuple[str, ...]
    duration: float | None
    max_freeze_duration: float


def verify_block_quality(
    path: str | Path,
    ffmpeg: str | None = None,
    min_duration: float | None = None,
) -> BlockQuality:
    """Reject malformed, too-short, or visibly frozen generated clips.

    The gate intentionally measures *intra-clip* continuity only.  Comparing a block's
    first and last frame with SSIM would reject valid designed changes such as a zoom into a
    cross-section, and says nothing reliable about identity preservation.  The actual-frame
    chain handles continuity; `freezedetect` catches the common failure where a provider
    returns a static image packaged as video.
    """
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    path = Path(path)
    reasons: list[str] = []
    info = probe(path, ffmpeg)

    required_duration = config.QUALITY_MIN_DURATION if min_duration is None else min_duration
    if not info.has_video:
        reasons.append("no video stream")
    if info.duration is None:
        reasons.append("unreadable duration")
    elif info.duration < required_duration:
        reasons.append(
            f"duration {info.duration:.2f}s < {required_duration:.2f}s"
        )
    if info.width is None or info.height is None:
        reasons.append("unreadable dimensions")
    elif info.width < config.QUALITY_MIN_WIDTH or info.height < config.QUALITY_MIN_HEIGHT:
        reasons.append(
            f"resolution {info.width}x{info.height} below "
            f"{config.QUALITY_MIN_WIDTH}x{config.QUALITY_MIN_HEIGHT}"
        )

    proc = _run([
        ffmpeg, "-hide_banner", "-loglevel", "info", "-i", str(path),
        "-vf", f"freezedetect=n={config.FREEZEDETECT_NOISE}:d={config.FREEZE_MAX_DURATION}",
        "-an", "-f", "null", "-",
    ])
    max_freeze = 0.0
    if proc.returncode != 0:
        reasons.append("freezedetect could not read clip")
    else:
        durations = [float(x) for x in _FREEZE_DURATION_RE.findall(proc.stderr or "")]
        if durations:
            max_freeze = max(durations)
        # A freeze that runs through end-of-file may only log its start.  Convert it to a
        # duration using the probed clip length so it cannot evade the gate.
        if info.duration is not None and not durations:
            for raw_start in _FREEZE_START_RE.findall(proc.stderr or ""):
                max_freeze = max(max_freeze, max(0.0, info.duration - float(raw_start)))
        if max_freeze > config.FREEZE_MAX_DURATION:
            reasons.append(
                f"frozen for {max_freeze:.2f}s (max {config.FREEZE_MAX_DURATION:.2f}s)"
            )

    return BlockQuality(not reasons, tuple(reasons), info.duration, max_freeze)


# --------------------------------------------------------------------------------------
# Video filter: normalize -> concat -> zoompan (explicit editorial reframes only)
# --------------------------------------------------------------------------------------

def _normalize_chain(idx: int, label: str, duration: float | None = None) -> str:
    trim_clause = f"trim=duration={duration:.3f},setpts=PTS-STARTPTS," if duration else ""
    crop_y = "min((in_h-out_h)/2\\,(in_h-out_h)*0.18)" if config.WIDTH > config.HEIGHT else "(in_h-out_h)/2"
    return (
        f"[{idx}:v]{trim_clause}fps={config.FPS},"
        f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={config.WIDTH}:{config.HEIGHT}:(in_w-out_w)/2:{crop_y},setsar=1[{label}]"
    )



def _zoom_expr(punch_times: list[float]) -> str:
    if not punch_times:
        return f"{config.BASE_ZOOM}"
    terms = []
    for t in punch_times:
        end = t + config.PUNCH_DECAY
        terms.append(
            f"between(time,{t:.3f},{end:.3f})*(1-(time-{t:.3f})/{config.PUNCH_DECAY})"
        )
    return f"{config.BASE_ZOOM} + {config.PUNCH_AMOUNT}*( " + " + ".join(terms) + " )"


def _shake_expr(axis: str, boundaries: list[float]) -> str:
    base = "iw/2-(iw/zoom/2)" if axis == "x" else "ih/2-(ih/zoom/2)"
    if not boundaries or config.SHAKE_AMPLITUDE_PX <= 0 or config.SHAKE_DURATION <= 0:
        return base
    trig = "sin" if axis == "x" else "cos"
    freq = config.SHAKE_FREQ_X if axis == "x" else config.SHAKE_FREQ_Y
    dur = config.SHAKE_DURATION
    terms = [base]
    for b in boundaries:
        # The trailing (1 - elapsed/dur) is the decay envelope. Without it the offset is
        # still at full amplitude when `between` goes false, which reads as a hard jolt.
        terms.append(
            f"between(time,{b:.3f},{b + dur:.3f})*{config.SHAKE_AMPLITUDE_PX}"
            f"*{trig}(2*PI*time*{freq})*(1-(time-{b:.3f})/{dur})"
        )
    return " + ".join(terms)



# --------------------------------------------------------------------------------------
# Targeted spatial camera
# --------------------------------------------------------------------------------------
#
# The camera pushes toward the point the annotation marker indicates instead of the frame
# centre. Three things make this work and each one was arrived at by breaking it first:
#
#   1. The base centre term is written ONCE and the targeted contribution is added on top
#      as a gated DELTA. Replacing the base term with a sum of gated absolute positions
#      collapses x to 0 outside every window, which slams the crop to the left/top edge.
#   2. clip(..., 0, dim-dim/zoom) is evaluated per frame against the LIVE `zoom` variable,
#      which makes a black edge band arithmetically impossible rather than merely unlikely.
#   3. Each window carries its own smoothstep, so at a shared boundary instant the
#      outgoing block is at ease=1 and the incoming one at ease=0. The jump therefore lands
#      exactly on the cut frame, where the existing shake already hides it.

def _ease_local(t0: float, dur: float) -> str:
    """Smoothstep over [t0, t0+dur]. `_ease` below is the global-time variant."""
    p = f"min(max((time-{t0:.3f})/{dur:.3f},0),1)"
    return f"({p}*{p}*(3-2*{p}))"


def _window_gate(t0: float, t1: float) -> str:
    """Half-open [t0, t1).

    between() includes its upper bound, so a frame landing exactly on a boundary would be
    claimed by two windows at once and get one frame of the previous block's framing.
    gte*lt tiles the timeline with no gap and no overlap.
    """
    return f"gte(time,{t0:.3f})*lt(time,{t1:.3f})"


def target_windows(
    boundaries: list[float], target_duration: float | None = None
) -> list[tuple[float, float]]:
    """One (t_start, t_end) per block, in the post-concat GLOBAL time base."""
    if target_duration is None:
        raise ValueError("target_windows requires the persisted timeline duration")
    target_dur = target_duration
    edges = [0.0] + list(boundaries) + [target_dur]
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def coverage_windows(
    block_durations: list[float], coverage: list[list[dict]] | None, quadrants: list[str],
) -> tuple[list[tuple[float, float]], list[str]]:
    """Turn persisted 1.0–1.6s coverage beats into global hard-cut windows.

    The final provider block may be trimmed to reserve the cloned tail.  Each block's
    authored beat proportions are therefore scaled to its actual emitted duration.
    Half-open ownership is still applied later by ``_window_gate``.
    """
    windows: list[tuple[float, float]] = []
    out_quadrants: list[str] = []
    cursor = 0.0
    for index, block_duration in enumerate(block_durations):
        authored = coverage[index] if coverage and index < len(coverage) else []
        beats = authored or [{"duration": block_duration, "quadrant": quadrants[index] if index < len(quadrants) else "center"}]
        total = sum(float(beat.get("duration") or 0.0) for beat in beats) or block_duration
        block_end = cursor + block_duration
        for beat_index, beat in enumerate(beats):
            duration = block_duration * float(beat.get("duration") or 0.0) / total
            if beat_index == len(beats) - 1:
                end = block_end
            else:
                end = cursor + duration
            windows.append((round(cursor, 3), round(end, 3)))
            out_quadrants.append(str(beat.get("quadrant") or (quadrants[index] if index < len(quadrants) else "center")))
            cursor = end
    # Floating-point rounding must never leave a micro-gap at the final tail boundary.
    if windows:
        windows[-1] = (windows[-1][0], round(sum(block_durations), 3))
    return windows, out_quadrants


def _targeted_zoom_terms(
    windows: list[tuple[float, float]], quadrants: list[str], gain: float
) -> list[str]:
    terms = []
    for (t0, t1), quad in zip(windows, quadrants):
        if quad == "center" or t1 <= t0:
            continue
        terms.append(f"{_window_gate(t0, t1)}*{gain}*{_ease_local(t0, t1 - t0)}")
    return terms


def _targeted_pan_terms(
    axis: str, windows: list[tuple[float, float]], quadrants: list[str]
) -> list[str]:
    dim, idx = ("iw", 0) if axis == "x" else ("ih", 1)
    centre = f"({dim}/2-({dim}/zoom/2))"
    terms = []
    for (t0, t1), quad in zip(windows, quadrants):
        if quad == "center" or t1 <= t0:
            continue
        n = config.quadrant_coord(quad)[idx]
        target = f"clip({dim}*{n:.4f}-({dim}/zoom/2),0,{dim}-({dim}/zoom))"
        terms.append(
            f"{_window_gate(t0, t1)}*({target}-{centre})*{_ease_local(t0, t1 - t0)}"
        )
    return terms


def normalize_quadrants(quadrants: list[str] | None, n_blocks: int) -> list[str]:
    """Pad/trim to n_blocks and drop anything not in config.QUADRANTS."""
    if not quadrants:
        return ["center"] * n_blocks
    out = [q if q in config.QUADRANT_COORDS else "center" for q in quadrants[:n_blocks]]
    return out + ["center"] * (n_blocks - len(out))


def normalize_boundary_kinds(kinds: list[str] | None, n_blocks: int) -> list[str]:
    """One "same"/"change" per inter-block boundary; unknown values become "same"."""
    n_bounds = max(0, n_blocks - 1)
    if not kinds:
        return ["same"] * n_bounds
    out = [k if k in ("same", "change") else "same" for k in kinds[:n_bounds]]
    return out + ["same"] * (n_bounds - len(out))


def normalize_editorial_plan(
    editorial_plan: dict | list[dict] | None,
    boundaries: list[float],
    n_blocks: int,
    *,
    terminal_payoff: bool = False,
) -> list[dict]:
    """Bind persisted editorial decisions to real inter-block boundaries.

    Absence means hard cuts with no visual impact.  Only ``subtle`` becomes an
    FFmpeg reframing pulse; ``strong`` is intentionally not synthesized here,
    because its accent must be the clip's authored diegetic action.  The final
    incoming boundary is forced to ``none`` for an opening-anchor payoff.
    """
    raw = editorial_plan.get("boundaries", []) if isinstance(editorial_plan, dict) else editorial_plan or []
    by_index: dict[int, dict] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("boundary")
        if index is None:
            # Persisted plans may identify a boundary by its timestamp.
            time = item.get("time")
            if isinstance(time, (int, float)):
                index = next((i + 1 for i, boundary in enumerate(boundaries) if abs(boundary - float(time)) <= 0.035), None)
        if not isinstance(index, int) or not 1 <= index < n_blocks:
            continue
        level = str(item.get("impact_level") or "none")
        if level not in {"none", "subtle", "strong"}:
            level = "none"
        by_index[index] = {
            "boundary": index,
            "time": boundaries[index - 1],
            "cut_style": "hard",
            "impact_level": level,
            "physical_accent": item.get("physical_accent"),
            "sfx_cue_ids": list(item.get("sfx_cue_ids") or []),
        }

    plan = [by_index.get(i, {"boundary": i, "time": boundaries[i - 1], "cut_style": "hard", "impact_level": "none", "physical_accent": None, "sfx_cue_ids": []}) for i in range(1, n_blocks)]
    # A clip can own at most one non-none effect, effect windows cannot stack,
    # and there are at most two effects in each 12-second interval.  Strong
    # has no FFmpeg effect but is still counted to prevent visual over-scoring.
    accepted: list[float] = []
    for item in plan:
        if item["impact_level"] == "none":
            continue
        time = float(item["time"])
        if (accepted and time - accepted[-1] < config.EDITORIAL_MIN_EFFECT_GAP) or sum(time - old < 12.0 for old in accepted) >= config.EDITORIAL_MAX_IMPACTS_PER_12S:
            item["impact_level"] = "none"
            item["physical_accent"] = None
            item["sfx_cue_ids"] = []
            continue
        accepted.append(time)
    if terminal_payoff and plan:
        plan[-1]["impact_level"] = "none"
        plan[-1]["physical_accent"] = None
        plan[-1]["sfx_cue_ids"] = []
    return plan


def _subtle_impact_terms(editorial_plan: list[dict]) -> list[str]:
    """Return the only allowed FFmpeg impact: a <=1.2% local zoom pulse."""
    amount, duration = config.SUBTLE_IMPACT_AMOUNT, config.SUBTLE_IMPACT_DURATION
    if amount <= 0 or duration <= 0:
        return []
    return [
        f"between(time,{item['time']:.3f},{item['time'] + duration:.3f})*{amount}"
        f"*(1-(time-{item['time']:.3f})/{duration:.3f})"
        for item in editorial_plan if item["impact_level"] == "subtle"
    ]


def _boundary_punch_terms(boundaries: list[float], kinds: list[str]) -> list[str]:
    """Triangular zoom spikes centred on subject-change cuts; they ride the global
    zoompan, so they work no matter how the [cat] stream was assembled."""
    amt, lead = config.BOUNDARY_PUNCH_AMT, config.BOUNDARY_PUNCH_LEAD
    if amt <= 0 or lead <= 0:
        return []
    terms = []
    for b, kind in zip(boundaries, kinds):
        if kind != "change":
            continue
        terms.append(
            f"between(time,{b - lead:.3f},{b + lead:.3f})*{amt}"
            f"*(1-abs(time-{b:.3f})/{lead:.3f})"
        )
    return terms


def _xfade_chain(
    n_blocks: int, boundaries: list[float], kinds: list[str]
) -> tuple[list[str], list[float]]:
    """Replace the plain concat with per-boundary xfades. Returns (statements, D_k list).

    Boundary k blends with duration D_k centred on the nominal cut timestamp, so the
    output timeline keeps the same boundaries as the old concat and captions stay in
    sync. The caller must extend each block's trim by half of each adjacent D_k.
    """
    durs = [
        config.XFADE_SAME_DUR if kind == "same" else config.XFADE_CHANGE_DUR
        for kind in kinds
    ]
    stmts: list[str] = []
    prev = "v0"
    cumulative_shrink = 0.0
    for k in range(n_blocks - 1):
        nxt = "cat" if k == n_blocks - 2 else f"x{k + 1}"
        trans = "fade" if kinds[k] == "same" else "fadeblack"
        offset = boundaries[k] - durs[k] / 2.0 - cumulative_shrink
        stmts.append(
            f"[{prev}][v{k + 1}]xfade=transition={trans}"
            f":duration={durs[k]:.3f}:offset={offset:.3f}[{nxt}]"
        )
        cumulative_shrink += durs[k]
        prev = nxt
    return stmts, durs


def block_boundaries(block_paths: list[Path], ffmpeg: str | None = None) -> list[float]:
    """Cumulative cut positions measured from the blocks themselves."""
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    bounds: list[float] = []
    acc = 0.0
    for p in block_paths[:-1]:
        acc += probe(p, ffmpeg).duration or 0.0
        bounds.append(round(acc, 3))
    return bounds


def select_punch_times(word_timings: list[dict]) -> list[float]:
    """Emphasis word starts, enforcing PUNCH_MIN_GAP and PUNCH_MAX_COUNT."""
    starts = sorted(
        w["start"] for w in word_timings
        if w.get("is_emphasis") and w.get("start") is not None
    )
    chosen: list[float] = []
    for t in starts:
        if not chosen or (t - chosen[-1]) >= config.PUNCH_MIN_GAP:
            chosen.append(t)
        if len(chosen) >= config.PUNCH_MAX_COUNT:
            break
    return chosen


def build_video_filter(
    n_blocks: int,
    punch_times: list[float],
    boundaries: list[float] | None = None,
    final_polish: bool = True,
    captions_path: Path | None = None,
    quadrants: list[str] | None = None,
    zoom_gain: float | None = None,
    block_durations: list[float] | None = None,
    target_duration: float | None = None,
    boundary_kinds: list[str] | None = None,
    transitions_enabled: bool = True,
    coverage: list[list[dict]] | None = None,
    editorial_plan: dict | list[dict] | None = None,
    terminal_payoff: bool = False,
) -> list[str]:
    """Return the video-side filtergraph statements (list, joined with ';' by caller)."""
    if boundaries is None:
        if block_durations and len(block_durations) == n_blocks:
            boundaries = [round(sum(block_durations[:i]), 3) for i in range(1, n_blocks)]
        elif target_duration is not None and n_blocks:
            slot = target_duration / n_blocks
            boundaries = [round(slot * i, 3) for i in range(1, n_blocks)]
        else:
            raise ValueError("Video filter requires timeline boundaries or planned durations")
    kinds = normalize_boundary_kinds(boundary_kinds, n_blocks)
    resolved_editorial_plan = normalize_editorial_plan(
        editorial_plan, boundaries, n_blocks, terminal_payoff=terminal_payoff,
    )
    stmts: list[str] = []
    labels = []
    for i in range(n_blocks):
        lab = f"v{i}"
        dur = block_durations[i] if block_durations and i < len(block_durations) else None
        stmts.append(_normalize_chain(i, lab, dur))
        labels.append(f"[{lab}]")
    tpad_clause = (
        f",tpad=stop_mode=clone:stop_duration={config.TAIL_HOLD}"
        if config.TAIL_HOLD > 0.001
        else ""
    )
    # Deliberately no xfade/cross-dissolve: Sanji-style pacing needs clear editorial
    # cuts, not blended source frames that read as morphing.
    stmts.append(f"{''.join(labels)}concat=n={n_blocks}:v=1:a=0{tpad_clause}[cat]")
    cat_label = "cat"
    stmts.append(f"[{cat_label}]setpts=N/{config.FPS}/TB[cat_pts]")
    cat_label = "cat_pts"

    quads = normalize_quadrants(quadrants, n_blocks)
    emitted_durations = block_durations or [target_duration / n_blocks] * n_blocks
    windows, window_quads = coverage_windows(emitted_durations, coverage, quads)
    if terminal_payoff and boundaries:
        # The final payoff and cloned tail are a calm proof state.  Do not let the
        # generic coverage reframe or global zoom leak into their time ownership.
        terminal_start = boundaries[-1]
        retained = [(window, quad) for window, quad in zip(windows, window_quads) if window[0] < terminal_start]
        windows, window_quads = ([item[0] for item in retained], [item[1] for item in retained])
    gain = config.TARGET_ZOOM_GAIN if zoom_gain is None else zoom_gain

    # Word emphasis and subject changes never infer an impact.  ``punch_times``
    # remains an API-compatible argument for legacy callers but is ignored.
    zexpr = " + ".join(
        [_zoom_expr([])] + _targeted_zoom_terms(windows, window_quads, gain)
        + _subtle_impact_terms(resolved_editorial_plan)
    )
    if terminal_payoff and boundaries:
        t0 = boundaries[-1]
        decay_dur = 0.5
        terminal_pull_out = f"between(time,{t0:.3f},{t0 + decay_dur:.3f})*0.08*(1-(time-{t0:.3f})/{decay_dur:.3f})"
        zexpr = f"1+(({zexpr})-1)*lt(time,{t0:.3f}) + {terminal_pull_out}"
    xexpr = " + ".join(
        [_shake_expr("x", [])] + _targeted_pan_terms("x", windows, window_quads)
    )
    yexpr = " + ".join(
        [_shake_expr("y", [])] + _targeted_pan_terms("y", windows, window_quads)
    )
    stmts.append(
        f"[{cat_label}]zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}'"
        f":d=1:s={config.WIDTH}x{config.HEIGHT}:fps={config.FPS}[zoom]"
    )

    chain: list[str] = []
    if final_polish:
        chain += [
            config.FINAL_UNSHARP,
            config.FINAL_GRAIN,
            config.FINAL_EQ,
            config.FINAL_VIGNETTE,
        ]
    if captions_path is not None:
        chain.append(captions.ass_filter(captions_path))

    stmts.append(f"[zoom]{','.join(chain)}[vout]" if chain else "[zoom]copy[vout]")
    return stmts




# --------------------------------------------------------------------------------------
# Voiceover assembly: per-beat parts + real silence
# --------------------------------------------------------------------------------------

def concat_audio_with_pauses(
    parts: list[Path],
    pauses: list[float],
    out_path: Path,
    ffmpeg: str | None = None,
    lead_silence: float = 0.0,
) -> Path:
    """Join `parts` with `pauses[i]` seconds of true silence after part i.

    edge-tts XML-escapes its input, so <break/> is spoken rather than honoured; the pauses
    that give the narration its Zack-D register have to be real samples. `aevalsrc=0` is
    the generator and `concat` the joiner, but concat refuses to mix formats: edge-tts hands
    back 24 kHz mono while aevalsrc defaults elsewhere, so every leg is forced through
    aresample+aformat first. Without that the filter errors out instead of silently
    resampling.

    `lead_silence` prepends a breath before the first part.
    """
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    if not parts:
        raise ValueError("concat_audio_with_pauses got no parts")
    if len(pauses) != len(parts):
        raise ValueError(f"{len(parts)} parts but {len(pauses)} pauses")

    r = config.AUDIO_RATE
    fmt = f"aformat=sample_fmts=fltp:sample_rates={r}:channel_layouts=mono"

    args = [ffmpeg, "-hide_banner", "-y"]
    for part in parts:
        args += ["-i", str(part)]

    stmts: list[str] = []
    labels: list[str] = []

    def silence(tag: str, seconds: float) -> None:
        stmts.append(f"aevalsrc=0:d={seconds:.3f}:s={r}:channel_layout=mono,{fmt}[{tag}]")
        labels.append(f"[{tag}]")

    if lead_silence > 0.001:
        silence("lead", lead_silence)
    for i, _ in enumerate(parts):
        stmts.append(f"[{i}:a]aresample={r},{fmt}[a{i}]")
        labels.append(f"[a{i}]")
        if pauses[i] > 0.001:
            silence(f"s{i}", pauses[i])

    stmts.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[aout]")

    graph_path = out_path.parent / "_vo_concat.txt"
    graph_path.write_text((";\n").join(stmts), encoding="utf-8")

    args += ["-/filter_complex", str(graph_path), "-map", "[aout]",
             "-c:a", "libmp3lame", "-q:a", "2", "-ar", str(r), "-ac", "1",
             str(out_path)]
    proc = _run(args)
    if proc.returncode != 0:
        raise RuntimeError("voiceover concat failed:\n" + proc.stderr[-2000:])
    return out_path


# --------------------------------------------------------------------------------------
# Audio filter: vo (+ optional music ducking) -> loudnorm
# --------------------------------------------------------------------------------------

def build_audio_filter(
    vo_index: int,
    music_index: int | None,
    sfx_inputs: list[dict] | None = None,
    soundscape_index: int | None = None,
) -> list[str]:
    r = config.AUDIO_RATE
    stmts: list[str] = []
    sfx_inputs = sfx_inputs or []
    if music_index is None and soundscape_index is None and not sfx_inputs:
        stmts.append(
            f"[{vo_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,"
            f"loudnorm=I={config.LOUDNORM_I}:TP={config.LOUDNORM_TP}:LRA={config.LOUDNORM_LRA},"
            f"apad,aformat=sample_rates={r}:channel_layouts=stereo[aout]"
        )
        return stmts

    # Build voice / music / soundscape base first with sidechain ducking
    if music_index is not None and soundscape_index is not None:
        stmts.append(f"[{vo_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,apad,asplit=3[vo1][vo2][vo3]")
        stmts.append(f"[{music_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,aloop=loop=-1:size=2e+09,volume={config.MUSIC_VOLUME}[mus]")
        stmts.append(f"[mus][vo2]sidechaincompress=threshold={config.DUCK_THRESHOLD}:ratio={config.DUCK_RATIO}:attack={config.DUCK_ATTACK}:release={config.DUCK_RELEASE}[duck]")
        stmts.append(f"[{soundscape_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,aloop=loop=-1:size=2e+09,volume=0.22[amb]")
        stmts.append(f"[amb][vo3]sidechaincompress=threshold=0.04:ratio=6:attack=10:release=350[duck_amb]")
        stmts.append("[vo1][duck][duck_amb]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[base]")
    elif music_index is not None:
        stmts.append(f"[{vo_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,apad,asplit=2[vo1][vo2]")
        stmts.append(f"[{music_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,aloop=loop=-1:size=2e+09,volume={config.MUSIC_VOLUME}[mus]")
        stmts.append(f"[mus][vo2]sidechaincompress=threshold={config.DUCK_THRESHOLD}:ratio={config.DUCK_RATIO}:attack={config.DUCK_ATTACK}:release={config.DUCK_RELEASE}[duck]")
        stmts.append("[vo1][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[base]")
    elif soundscape_index is not None:
        stmts.append(f"[{vo_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,apad,asplit=2[vo1][vo2]")
        stmts.append(f"[{soundscape_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,aloop=loop=-1:size=2e+09,volume=0.25[amb]")
        stmts.append(f"[amb][vo2]sidechaincompress=threshold=0.04:ratio=6:attack=10:release=350[duck_amb]")
        stmts.append("[vo1][duck_amb]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[base]")
    else:
        stmts.append(f"[{vo_index}:a]aformat=sample_rates={r}:channel_layouts=stereo,apad[base]")
    labels = ["[base]"]
    for item in sfx_inputs:
        index, start, end = int(item["input_index"]), float(item["start"]), float(item["end"])
        duration = max(0.1, end - start)
        fade_in = float(item.get("fade_in", 0.015))
        fade_out = float(item.get("fade_out", 0.25))
        gain = float(item.get("gain_db", -10.0))
        start_trim = float(item.get("start_trim", 0.0))
        effective_fade_in = min(fade_in, duration * 0.25)
        effective_fade_out = min(fade_out, duration * 0.5)
        fade_out_start = max(0.0, duration - effective_fade_out)
        delay_ms = max(0, int(round(start * 1000)))
        label = f"sfx{index}"
        stmts.append(
            f"[{index}:a]aformat=sample_rates={r}:channel_layouts=stereo,"
            f"atrim={start_trim:.3f}:{start_trim + duration:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={effective_fade_in:.3f}:curve=qsin,afade=t=out:st={fade_out_start:.3f}:d={effective_fade_out:.3f}:curve=exp,"
            f"highpass=f=75,equalizer=f=250:t=q:w=1.5:g=-2.0,equalizer=f=4000:t=q:w=1.8:g=2.0,"
            f"haas=middle_source=mid:side_gain=1.25:left_delay=2.05:right_delay=2.12,"
            f"volume={gain}dB,adelay={delay_ms}|{delay_ms}[{label}]"
        )
        labels.append(f"[{label}]")
    mix_label = "base" if len(labels) == 1 else "mix"
    if len(labels) > 1:
        stmts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0[{mix_label}]")
    stmts.append(
        f"[{mix_label}]loudnorm=I={config.LOUDNORM_I}:TP={config.LOUDNORM_TP}:LRA={config.LOUDNORM_LRA},"
        f"aformat=sample_rates={r}:channel_layouts=stereo[aout]"
    )
    return stmts


# --------------------------------------------------------------------------------------
# Standalone 3 Audio Layers Mix (TTS + Ducked Music + SFX Foley)
# --------------------------------------------------------------------------------------

def mix_3_audio_layers(
    vo_path: Path | str,
    music_path: Path | str | None,
    sfx_cues: list[dict] | None = None,
    out_path: Path | str | None = None,
    target_duration: float | None = None,
    ffmpeg: str | None = None,
) -> Path:
    """Explicitly assemble and render the 3 audio layers into a broadcast master audio track.
    
    Layers:
      Layer 1: Spoken Voiceover (TTS)
      Layer 2: Background Music Bed (sidechain ducked under speech, -14 LUFS normalized)
      Layer 3: Procedural SFX Foley Cues (spatialized / timed)
      
    Outputs a broadcast-compliant 48 kHz stereo PCM/WAV file normalized to -14 LUFS.
    """
    ffmpeg_bin = ffmpeg or config.resolve_ffmpeg()
    vo = Path(vo_path)
    if not vo.is_file():
        raise FileNotFoundError(f"Voiceover track not found: {vo}")

    mus = Path(music_path) if music_path and Path(music_path).is_file() else None
    have_music = mus is not None
    sfx_cues = sfx_cues or []

    if target_duration is None:
        info = probe(vo, ffmpeg=ffmpeg_bin)
        target_len = float(info.duration or 10.0)
    else:
        target_len = float(target_duration)

    dest = Path(out_path) if out_path else vo.parent / "audio_3layers_master.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)

    vo_index = 0
    music_index = 1 if have_music else None
    base_sfx_offset = 2 if have_music else 1

    validated_sfx: list[dict] = []
    for cue in sfx_cues:
        c_path = Path(str(cue.get("local_path") or ""))
        if not c_path.is_file():
            continue
        c_start = float(cue.get("start", 0.0))
        c_end = float(cue.get("end", c_start + 1.0))
        if c_end > target_len:
            c_end = round(target_len, 3)
        if c_end <= c_start:
            continue
        validated_sfx.append(dict(cue, start=c_start, end=c_end, input_index=base_sfx_offset + len(validated_sfx)))

    audio_filter_stmts = build_audio_filter(
        vo_index=vo_index,
        music_index=music_index,
        sfx_inputs=validated_sfx,
    )
    filtergraph = ";\n".join(audio_filter_stmts)

    cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
    cmd += ["-i", str(vo)]
    if have_music:
        cmd += ["-i", str(mus)]
    for cue in validated_sfx:
        cmd += ["-i", str(cue["local_path"])]

    cmd += [
        "-filter_complex", filtergraph,
        "-map", "[aout]",
        "-t", f"{target_len:.3f}",
        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(dest),
    ]

    subprocess.run(cmd, check=True)
    return dest


# --------------------------------------------------------------------------------------

def build_filtergraph(
    n_blocks: int,
    punch_times: list[float],
    have_music: bool,
    boundaries: list[float] | None = None,
    final_polish: bool = True,
    captions_path: Path | None = None,
    quadrants: list[str] | None = None,
    zoom_gain: float | None = None,
    block_durations: list[float] | None = None,
    target_duration: float | None = None,
    boundary_kinds: list[str] | None = None,
    transitions_enabled: bool = True,
    coverage: list[list[dict]] | None = None,
    editorial_plan: dict | list[dict] | None = None,
    terminal_payoff: bool = False,
    sfx_inputs: list[dict] | None = None,
    soundscape_index: int | None = None,
) -> str:
    vo_index = n_blocks
    music_index = n_blocks + 1 if have_music else None
    video = build_video_filter(
        n_blocks, punch_times, boundaries, final_polish, captions_path,
        quadrants, zoom_gain, block_durations, target_duration, boundary_kinds,
        transitions_enabled, coverage, editorial_plan, terminal_payoff,
    )
    audio = build_audio_filter(vo_index, music_index, sfx_inputs, soundscape_index=soundscape_index)
    return ";\n".join(video + audio)


def render(
    block_paths: list[Path],
    vo_path: Path,
    out_path: Path,
    punch_times: list[float],
    music_path: Path | None = None,
    boundaries: list[float] | None = None,
    final_polish: bool = True,
    captions_path: Path | None = None,
    ffmpeg: str | None = None,
    dry_run: bool = False,
    quadrants: list[str] | None = None,
    target_len: float | None = None,
    boundary_kinds: list[str] | None = None,
    coverage: list[list[dict]] | None = None,
    editorial_plan: dict | list[dict] | None = None,
    terminal_payoff: bool = False,
    sfx_cues: list[dict] | None = None,
    soundscape_path: Path | None = None,
) -> tuple[list[str], str]:
    """Compile the graph and (unless dry_run) encode final.mp4.

    Returns (ffmpeg_argv, filtergraph_text). In dry_run the graph is compiled with
    `-f null` so we prove it parses without spending an encode.
    """
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    n = len(block_paths)
    have_music = music_path is not None and Path(music_path).is_file()
    have_soundscape = soundscape_path is not None and Path(soundscape_path).is_file()
    soundscape_index = n + 1 + (1 if have_music else 0) if have_soundscape else None

    blocks = [probe(p, ffmpeg) for p in block_paths]

    voice_duration = probe(vo_path, ffmpeg).duration
    generated_footage = round(sum(float(info.duration or 0.0) for info in blocks), 3)
    # The target is final output duration and includes the clone tail.
    if target_len is None:
        if any(info.duration is None for info in blocks):
            raise ValueError("Render requires target_len when a source duration cannot be probed")
        target_len = config.compute_target_duration(generated_footage, voice_duration)
    target_len = float(target_len)
    content_duration = round(target_len - config.TAIL_HOLD, 3)
    if content_duration <= 0:
        raise ValueError("Render target must exceed the configured cloned tail")
    if content_duration > generated_footage + 0.03:
        raise RuntimeError("Voice duration exceeds available provider footage plus the configured tail; regenerate narration before video work.")
    source_durations = [float(info.duration or 0.0) for info in blocks]
    block_durations_target = list(source_durations)
    block_durations_target[-1] = round(content_duration - sum(block_durations_target[:-1]), 3)
    if block_durations_target[-1] <= 0:
        raise RuntimeError("Tail budget leaves no valid final native block content")
    boundaries = [round(sum(block_durations_target[:i]), 3) for i in range(1, n)]

    kinds = normalize_boundary_kinds(boundary_kinds, n)
    for i, info in enumerate(blocks):
        have = info.duration
        need = block_durations_target[i]
        if have is None or have < need - 0.03:
            raise RuntimeError(
                f"Block {i + 1:02d} is {have or 0:.2f}s but its fixed timeline slot requires "
                f"{need:.2f}s; regenerate this block instead of stretching the edit."
            )

    block_durations = block_durations_target
    print(f"  [edit] hard editorial cuts; final target {target_len:.2f}s includes {config.TAIL_HOLD:.1f}s clone tail")

    # The targeted push crops in, so a sub-1080p source would be upscaled and go soft.
    heights = [b.height for b in blocks if b.height]
    zoom_gain = config.target_zoom_gain(min(heights) if heights else None)

    sfx_cues = sfx_cues or []
    validated_sfx: list[dict] = []
    base_sfx_offset = n + 1 + (1 if have_music else 0) + (1 if have_soundscape else 0)
    for cue in sfx_cues:
        path = Path(str(cue.get("local_path") or ""))
        if not path.is_file():
            raise RuntimeError(f"SFX cue has no verified local asset: {cue.get('cue_id', '<unknown>')}")
        c_start = float(cue["start"])
        c_end = float(cue["end"])
        if c_start < 0 or c_start >= target_len:
            raise RuntimeError(f"SFX cue lies outside final target: {cue.get('cue_id', '<unknown>')}")
        if c_end > target_len:
            c_end = round(target_len, 3)
        if c_end <= c_start:
            raise RuntimeError(f"SFX cue has invalid duration interval: {cue.get('cue_id', '<unknown>')}")
        validated_sfx.append(dict(cue, start=c_start, end=c_end, input_index=base_sfx_offset + len(validated_sfx)))
    graph = build_filtergraph(
        n, punch_times, have_music, boundaries, final_polish, captions_path,
        quadrants, zoom_gain, block_durations=block_durations, target_duration=content_duration,
        boundary_kinds=kinds, transitions_enabled=False, coverage=coverage,
        editorial_plan=editorial_plan, terminal_payoff=terminal_payoff, sfx_inputs=validated_sfx,
        soundscape_index=soundscape_index,
    )


    script_path = out_path.parent / "_filtergraph.txt"
    script_path.write_text(graph, encoding="utf-8")

    args = [ffmpeg, "-hide_banner", "-y"]
    for b in block_paths:
        args += ["-i", str(b)]
    args += ["-i", str(vo_path)]
    if have_music:
        args += ["-i", str(music_path)]
    if have_soundscape:
        args += ["-i", str(soundscape_path)]
    for cue in validated_sfx:
        args += ["-i", str(cue["local_path"])]
    args += ["-/filter_complex", str(script_path), "-map", "[vout]", "-map", "[aout]"]
    render_len = target_len
    args += [
        "-t", f"{render_len:.3f}", "-r", str(config.FPS),
        "-c:v", "libx264", "-crf", str(config.X264_CRF), "-preset", config.X264_PRESET,
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", config.AAC_BITRATE, "-ar", str(config.AUDIO_RATE),
    ]

    if dry_run:
        # A dry run proves that FFmpeg can parse the complete graph; it must not
        # spend minutes evaluating the 34-second 1080x1920 production filter.
        # The audit separately asserts the final [28, 32) window and every live
        # crop clamp is present, while this short pass evaluates the graph itself.
        parse_args = list(args)
        duration_index = parse_args.index("-t") + 1
        parse_args[duration_index] = "0.250"
        proc = _run(parse_args + ["-f", "null", "-"])
        if proc.returncode != 0:
            raise RuntimeError(
                "Dry-run filtergraph failed to compile:\n" + proc.stderr[-2000:]
            )
        return args + [str(out_path)], graph

    args += [str(out_path)]
    proc = _run(args)
    if proc.returncode != 0:
        raise RuntimeError("Final encode failed:\n" + proc.stderr[-2000:])
    return args, graph


# --------------------------------------------------------------------------------------
# Local motion engine: the only animation source in the free tier
# --------------------------------------------------------------------------------------

def _ease(duration: float) -> str:
    """Smoothstep on normalised time. A linear ramp is what makes Ken Burns look cheap."""
    p = f"min(max(time/{duration:.4f},0),1)"
    return f"({p}*{p}*(3-2*{p}))"




# --------------------------------------------------------------------------------------
# Local motion engine: the only animation source in the free tier
# --------------------------------------------------------------------------------------

def _ease(duration: float) -> str:
    """Smoothstep on normalised time. A linear ramp is what makes Ken Burns look cheap."""
    p = f"min(max(time/{duration:.4f},0),1)"
    return f"({p}*{p}*(3-2*{p}))"


def _float_expr(terms: tuple[tuple[float, float], ...], trig: str) -> str:
    """Summed incommensurate sines: organic handheld drift instead of a metronome."""
    return "+".join(f"{amp:.3f}*{trig}(2*PI*time*{hz:g})" for amp, hz in terms)


class MotionEngine:
    """Animate a still keyframe into a block locally.

    This is the whole of phase 4 in the free tier (no image-to-video model is available
    without a key), and the last rung of the paid ladder. New runs derive the eased zoom
    direction from the authored SceneCard transition; a block-number variation remains
    only for legacy/local fallback. Handheld float and directional drift stay continuous.
    """

    def __init__(self, ffmpeg: str | None = None):
        self.ffmpeg = ffmpeg or config.resolve_ffmpeg()
        self._rack_focus_ok: bool | None = None

        # Bind to config dimensions so subclasses can override them safely
        self.width = config.WIDTH
        self.height = config.HEIGHT
        self.fps = config.FPS
        self.src_width = config.MOTION_SRC_WIDTH
        self.src_height = config.MOTION_SRC_HEIGHT
        self.src_unsharp = config.MOTION_SRC_UNSHARP
        self.overscan = config.MOTION_OVERSCAN
        self.motion_zoom = config.MOTION_ZOOM
        self.motion_drift_px = config.MOTION_DRIFT_PX
        self.motion_float_x = config.MOTION_FLOAT_X
        self.motion_float_y = config.MOTION_FLOAT_Y
        self.rack_focus_sigma = config.RACK_FOCUS_SIGMA
        self.rack_focus_start = config.RACK_FOCUS_START
        self.rack_focus_duration = config.RACK_FOCUS_DURATION

    def _source_chain(self) -> str:
        return (
            f"[0:v]scale={self.src_width}:{self.src_height}"
            f":force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={self.src_width}:{self.src_height},setsar=1,"
            f"{self.src_unsharp}[src]"
        )

    def _move_chain(self, block: int, duration: float, transition_hint: str | None = None) -> str:
        # New SceneCards nominate a transition intent.  The numbered camera pattern is
        # retained only as a legacy/local fallback so it can never become the source of a
        # story beat merely because this is block four instead of block three.
        by_transition = {
            "zoom_in": {"motion": "push_in", "drift": "up"},
            "zoom_out": {"motion": "pull_out", "drift": "down"},
            "cross_section": {"motion": "deep_push", "drift": "down"},
            "match_cut": {"motion": "push_in", "drift": "up"},
            "whip": {"motion": "push_in", "drift": "right"},
            "lateral_pan": {"motion": "lateral_pan", "drift": "right"},
            "none": {"motion": "push_in", "drift": "up"},
        }
        cam = by_transition.get(transition_hint or "") or config.block_camera(block)
        
        # Scale drift and zoom relative to a base duration of 4.0s for duration sensitivity
        time_scale = duration / 4.0

        f0, f1 = self.motion_zoom.get(cam["motion"], (1.0, 1.0))
        # duration-sensitive zoom scaling for both start and end
        f0_scaled = 1.0 + (f0 - 1.0) * time_scale
        f1_scaled = 1.0 + (f1 - 1.0) * time_scale

        z0 = self.overscan * f0_scaled
        z1 = self.overscan * f1_scaled
        ease = _ease(duration)

        zexpr = f"{z0:.5f}+({z1 - z0:.5f})*{ease}"
        
        float_x = _float_expr(self.motion_float_x, 'sin')
        float_y = _float_expr(self.motion_float_y, 'cos')

        if cam["motion"] == "lateral_pan":
            # True lateral pan across the entire overscan margin
            if cam.get("drift") == "left":
                base_x = f"(iw-iw/zoom)*(1-{ease})"
            else:
                base_x = f"(iw-iw/zoom)*{ease}"
            base_y = "ih/2-(ih/zoom/2)"
        else:
            dx = {"left": -1.0, "right": 1.0}.get(cam["drift"], 0.0) * self.motion_drift_px * time_scale
            dy = {"up": -1.0, "down": 1.0}.get(cam["drift"], 0.0) * self.motion_drift_px * time_scale
            base_x = f"iw/2-(iw/zoom/2)+({dx:.3f})*{ease}"
            base_y = f"ih/2-(ih/zoom/2)+({dy:.3f})*{ease}"

        xexpr = f"clip({base_x}+({float_x}),0,iw-iw/zoom)"
        yexpr = f"clip({base_y}+({float_y}),0,ih-ih/zoom)"

        return (
            f"[src]zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}'"
            f":d=1:s={self.width}x{self.height}:fps={self.fps}[mo]"
        )

    def _rack_focus_chain(self) -> str:
        start = self.rack_focus_start
        dur = self.rack_focus_duration
        alpha = f"min(max((T-{start:.3f})/{dur:.3f},0),1)"
        return (
            f"[mo]split=2[sharp][soft];"
            f"[soft]gblur=sigma={self.rack_focus_sigma:g}[blurred];"
            f"[blurred][sharp]blend=all_expr='A*(1-{alpha})+B*{alpha}'[vout]"
        )

    def graph(self, block: int, duration: float, rack_focus: bool, transition_hint: str | None = None) -> str:
        stmts = [self._source_chain(), self._move_chain(block, duration, transition_hint)]
        if rack_focus:
            stmts.append(self._rack_focus_chain())
        else:
            stmts.append("[mo]copy[vout]")
        return ";\n".join(stmts)

    def render(
        self,
        image_path: Path,
        out_path: Path,
        block: int,
        duration: float = config.LEGACY_BLOCK_DURATION,
        rack_focus: bool | None = None,
        transition_hint: str | None = None,
    ) -> Path:
        cam = config.block_camera(block)
        want_rack = (cam["rack_focus"] if transition_hint is None else False) if rack_focus is None else rack_focus
        if want_rack and self._rack_focus_ok is False:
            want_rack = False

        for attempt_rack in ([True, False] if want_rack else [False]):
            graph = self.graph(block, duration, attempt_rack, transition_hint)
            graph_path = out_path.parent / f"_motion{block:02d}.txt"
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            graph_path.write_text(graph, encoding="utf-8")
            proc = _run([
                self.ffmpeg, "-hide_banner", "-y", "-loop", "1", "-i", str(image_path),
                "-t", f"{duration:.3f}",
                "-/filter_complex", str(graph_path), "-map", "[vout]",
                "-r", str(self.fps), "-c:v", "libx264", "-crf", "18",
                "-preset", "medium", "-pix_fmt", "yuv420p", str(out_path),
            ])
            if proc.returncode == 0:
                if attempt_rack:
                    self._rack_focus_ok = True
                return out_path
            if attempt_rack:
                # blend with a time-dependent alpha is the one rung not proven on every
                # build; drop to the plain move rather than losing the block.
                self._rack_focus_ok = False
                print(f"  [motion] block {block} rack focus unavailable, using plain move")
                continue
            raise RuntimeError(
                f"MotionEngine failed for block {block}:\n" + proc.stderr[-1500:]
            )
        raise RuntimeError(f"MotionEngine exhausted its fallbacks for block {block}")


class LongformMotionEngine(MotionEngine):
    """A specialized MotionEngine for 16:9 episodic content with longer holds."""
    def __init__(self, ffmpeg: str | None = None):
        super().__init__(ffmpeg)
        self.width = config.LONGFORM_WIDTH
        self.height = config.LONGFORM_HEIGHT
        self.fps = config.LONGFORM_FPS
        self.src_width = config.LONGFORM_MOTION_SRC_WIDTH
        self.src_height = config.LONGFORM_MOTION_SRC_HEIGHT
        self.src_unsharp = config.LONGFORM_MOTION_SRC_UNSHARP
        self.overscan = config.LONGFORM_MOTION_OVERSCAN
        self.motion_zoom = config.LONGFORM_MOTION_ZOOM
        self.motion_drift_px = config.LONGFORM_MOTION_DRIFT_PX
        self.motion_float_x = config.LONGFORM_MOTION_FLOAT_X
        self.motion_float_y = config.LONGFORM_MOTION_FLOAT_Y
        self.rack_focus_sigma = config.LONGFORM_RACK_FOCUS_SIGMA
        self.rack_focus_start = config.LONGFORM_RACK_FOCUS_START
        self.rack_focus_duration = config.LONGFORM_RACK_FOCUS_DURATION


def concat_parts(parts: list[Path], out_path: Path, ffmpeg: str | None = None) -> Path:
    """Join the 5s+5s Kling rung into one 10s block via the concat filter (not the demuxer)."""
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    args = [ffmpeg, "-hide_banner", "-y"]
    for p in parts:
        args += ["-i", str(p)]
    chains = []
    labels = []
    for i in range(len(parts)):
        chains.append(_normalize_chain(i, f"p{i}"))
        labels.append(f"[p{i}]")
    chains.append(f"{''.join(labels)}concat=n={len(parts)}:v=1:a=0[vout]")
    args += [
        "-filter_complex", ";".join(chains), "-map", "[vout]",
        "-r", str(config.FPS), "-c:v", "libx264", "-crf", "18",
        "-preset", "medium", "-pix_fmt", "yuv420p", str(out_path),
    ]
    proc = _run(args)
    if proc.returncode != 0:
        raise RuntimeError("Part concat failed:\n" + proc.stderr[-1500:])
    return out_path


def extract_last_frame(
    block_path: Path, out_path: Path, ffmpeg: str | None = None
) -> Path:
    """Write the decoded final pixel frame of one video, suitable as an I2V input."""
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    block_path = Path(block_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = _run([
        ffmpeg, "-hide_banner", "-y",
        "-sseof", f"-{config.CHAIN_FRAME_SEEK_SECONDS:.3f}", "-i", str(block_path),
        # Seeking only 1 ms before EOF can land after the final timestamp and emit no
        # packets.  Reverse the small decoded tail so its first output is the literal final
        # decoded frame rather than merely the first frame near the end.
        "-vf", "reverse", "-frames:v", "1", "-q:v", "2", str(out_path),
    ])
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"Last-frame extract failed for {block_path.name}:\n{proc.stderr[-800:]}")
    return out_path


def conform_audio_duration(path: Path, target: float, ffmpeg: str | None = None) -> float:
    """Gently conform a finished narration take without changing its pitch.

    Provider voice settings are not a deterministic duration API.  For a small drift we
    use ffmpeg's pitch-preserving `atempo` before word alignment, avoiding repeated paid
    TTS calls and ensuring captions describe the exact audio that ships.
    """
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    path = Path(path)
    duration = probe(path, ffmpeg).duration or 0.0
    if not duration or not target:
        return duration
    factor = duration / target
    # A generated voice can differ materially from its word-budget estimate.  Up to a
    # 40% pitch-preserving conform remains preferable to a new paid TTS + LLM rewrite,
    # especially after a Vertex storyboard has already frozen its visual plan.  Larger
    # deviations remain an explicit timing-review condition.
    if abs(duration - target) <= 0.10 or not (0.60 <= factor <= 1.40):
        return duration
    temp = path.with_name(path.stem + "_tempo.mp3")
    proc = _run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
        "-af", f"atempo={factor:.6f}", "-c:a", "libmp3lame", "-b:a", "128k", str(temp),
    ])
    if proc.returncode != 0 or not temp.exists():
        raise RuntimeError("Narration tempo conform failed:\n" + proc.stderr[-800:])
    temp.replace(path)
    return probe(path, ffmpeg).duration or duration


def extract_last_frames(
    block_paths: list[Path], out_dir: Path, ffmpeg: str | None = None
) -> list[Path]:
    """Extract each block's ACTUAL last frame (plus block 1's first frame) as PNGs.

    The manual Flow workflow feeds these back as the next block's First Frame, which
    chains blocks on real pixels instead of the drifted shared keyframe.
    """
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for i, p in enumerate(block_paths):
        last = out_dir / f"block{i + 1:02d}_last.png"
        written.append(extract_last_frame(p, last, ffmpeg))
        if i == 0:
            first = out_dir / "block01_first.png"
            proc = _run([
                ffmpeg, "-hide_banner", "-y",
                "-i", str(p), "-frames:v", "1", "-q:v", "2", str(first),
            ])
            if proc.returncode == 0 and first.exists():
                written.append(first)
    return written


def extract_quality_frames(block_path: Path, out_dir: Path, prefix: str,
                           duration: float | None = None, ffmpeg: str | None = None) -> list[Path]:
    """Extract full-resolution first/middle/last frames for model visual review."""
    ffmpeg = ffmpeg or config.resolve_ffmpeg()
    block_path, out_dir = Path(block_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = duration or probe(block_path, ffmpeg).duration or 1.0
    frames: list[Path] = []
    for label, seek in (("first", 0.0), ("middle", duration / 2.0), ("last", max(0.0, duration - 0.04))):
        frame = out_dir / f"{prefix}_{label}.jpg"
        proc = _run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seek:.3f}",
            "-i", str(block_path), "-frames:v", "1", "-q:v", "2", str(frame),
        ])
        # Some H.264 files report an exact container duration yet have no decodable
        # frame at duration - 0.04 after timestamp seeking.  A short EOF-relative
        # fallback still gives the visual gate a genuine final state instead of making
        # a report fail solely because of a container timestamp boundary.
        if label == "last" and (proc.returncode != 0 or not frame.exists()):
            proc = _run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-0.20",
                "-i", str(block_path), "-frames:v", "1", "-q:v", "2", str(frame),
            ])
        if proc.returncode != 0 or not frame.exists():
            raise RuntimeError(f"Quality-frame extract failed for {block_path.name} ({label}): {proc.stderr[-500:]}")
        frames.append(frame)
    return frames


class LongformCompiler:
    """Chunk-based compilation workflow for long-form episodes (Item D).
    
    Breaks the total block sequence into manageable chunks to avoid FFmpeg command-line
    length limits and memory constraints. Renders each chunk to an intermediate .mp4,
    stitches them together using the FFmpeg concat demuxer, and finally applies audio
    and polish.
    """
    def __init__(self, chunk_size: int = 15, ffmpeg: str | None = None):
        self.chunk_size = chunk_size
        self.ffmpeg = ffmpeg or config.resolve_ffmpeg()

    def compile(self, block_paths: list[Path], vo_path: Path, out_path: Path,
                punch_times: list[float], music_path: Path | None = None,
                boundaries: list[float] | None = None, final_polish: bool = True,
                captions_path: Path | None = None, dry_run: bool = False,
                quadrants: list[str] | None = None, target_len: float | None = None,
                boundary_kinds: list[str] | None = None, coverage: list[list[dict]] | None = None,
                editorial_plan: dict | list[dict] | None = None, terminal_payoff: bool = False,
                sfx_cues: list[dict] | None = None,
                soundscape_path: Path | None = None) -> tuple[list[str], str]:
        orig_w = config.WIDTH
        orig_h = config.HEIGHT
        config.WIDTH = config.LONGFORM_WIDTH
        config.HEIGHT = config.LONGFORM_HEIGHT
        try:
            return self._compile_internal(
                block_paths, vo_path, out_path, punch_times, music_path, boundaries,
                final_polish, captions_path, dry_run, quadrants, target_len,
                boundary_kinds, coverage, editorial_plan, terminal_payoff, sfx_cues,
                soundscape_path
            )
        finally:
            config.WIDTH = orig_w
            config.HEIGHT = orig_h

    def _compile_internal(self, block_paths: list[Path], vo_path: Path, out_path: Path,
                          punch_times: list[float], music_path: Path | None = None,
                          boundaries: list[float] | None = None, final_polish: bool = True,
                          captions_path: Path | None = None, dry_run: bool = False,
                          quadrants: list[str] | None = None, target_len: float | None = None,
                          boundary_kinds: list[str] | None = None, coverage: list[list[dict]] | None = None,
                          editorial_plan: dict | list[dict] | None = None, terminal_payoff: bool = False,
                          sfx_cues: list[dict] | None = None,
                          soundscape_path: Path | None = None) -> tuple[list[str], str]:
        n_blocks = len(block_paths)
        if n_blocks <= self.chunk_size:
            return render(
                block_paths, vo_path, out_path, punch_times, music_path, boundaries,
                final_polish, captions_path, self.ffmpeg, dry_run, quadrants, target_len,
                boundary_kinds, coverage, editorial_plan, terminal_payoff, sfx_cues,
                soundscape_path=soundscape_path
            )
            
        print(f"  [longform] chunking {n_blocks} blocks into {self.chunk_size}-block segments")
        
        work_dir = out_path.parent / "chunks"
        work_dir.mkdir(parents=True, exist_ok=True)
        
        blocks = [probe(p, self.ffmpeg) for p in block_paths]
        voice_duration = probe(vo_path, self.ffmpeg).duration
        generated_footage = round(sum(float(info.duration or 0.0) for info in blocks), 3)
        if target_len is None:
            target_len = config.compute_target_duration(generated_footage, voice_duration)
        target_len = float(target_len)
        content_duration = round(target_len - config.TAIL_HOLD, 3)
        
        source_durations = [float(info.duration or 0.0) for info in blocks]
        block_durations_target = list(source_durations)
        block_durations_target[-1] = round(content_duration - sum(block_durations_target[:-1]), 3)

        chunk_files = []
        concat_list = work_dir / "concat.txt"
        
        quads = normalize_quadrants(quadrants, n_blocks)
        b_kinds = normalize_boundary_kinds(boundary_kinds, n_blocks)
        cov = coverage or []
        while len(cov) < n_blocks:
            cov.append([])
            
        raw_plan = editorial_plan.get("boundaries", []) if isinstance(editorial_plan, dict) else (editorial_plan or [])
        old_tail = config.TAIL_HOLD
        
        active_boundaries = {
            item["boundary"] for item in raw_plan
            if isinstance(item, dict) and "boundary" in item and item.get("impact_level", "none") != "none"
        }
        
        chunks = []
        i = 0
        while i < n_blocks:
            end = i + self.chunk_size
            if end < n_blocks:
                # Avoid splitting exactly on an active boundary by pulling the split point back
                while end in active_boundaries and end > i + 1:
                    end -= 1
            else:
                end = n_blocks
            chunks.append((i, end))
            i = end
        
        try:
            for chunk_idx, (i, end) in enumerate(chunks):
                chunk_blocks = block_paths[i:end]
                chunk_durations = block_durations_target[i:end]
                chunk_quadrants = quads[i:end]
                chunk_coverage = cov[i:end]
                chunk_b_kinds = b_kinds[i:end-1]
                
                chunk_plan = []
                for item in raw_plan:
                    if isinstance(item, dict) and "boundary" in item:
                        if i < item["boundary"] < end:
                            new_item = dict(item)
                            new_item["boundary"] = item["boundary"] - i
                            chunk_plan.append(new_item)
                
                chunk_out = work_dir / f"chunk_{chunk_idx:03d}.mp4"
                chunk_boundaries = [round(sum(chunk_durations[:j]), 3) for j in range(1, end - i)]
                
                config.TAIL_HOLD = old_tail if (end == n_blocks) else 0.0
                is_terminal = terminal_payoff if (end == n_blocks) else False
                
                graph_lines = build_video_filter(
                    n_blocks=len(chunk_blocks),
                    punch_times=[],
                    boundaries=chunk_boundaries,
                    final_polish=False,
                    captions_path=None,
                    quadrants=chunk_quadrants,
                    zoom_gain=None,
                    block_durations=chunk_durations,
                    target_duration=sum(chunk_durations),
                    boundary_kinds=chunk_b_kinds,
                    transitions_enabled=False,
                    coverage=chunk_coverage,
                    editorial_plan=chunk_plan,
                    terminal_payoff=is_terminal,
                )
                
                graph = ";\n".join(graph_lines)
                script_path = work_dir / f"_chunk_{chunk_idx:03d}_graph.txt"
                script_path.write_text(graph, encoding="utf-8")
                
                args = [self.ffmpeg, "-hide_banner", "-y"]
                for b in chunk_blocks:
                    args += ["-i", str(b)]
                args += [
                    "-/filter_complex", str(script_path),
                    "-map", "[vout]",
                    "-c:v", "libx264", "-crf", str(config.X264_CRF), "-preset", config.X264_PRESET,
                    "-pix_fmt", "yuv420p"
                ]
                
                if dry_run:
                    parse_args = list(args) + ["-t", "0.250", "-f", "null", "-"]
                    proc = _run(parse_args)
                    if proc.returncode != 0:
                        raise RuntimeError(f"Dry-run chunk {chunk_idx} failed:\n" + proc.stderr[-2000:])
                else:
                    args += [str(chunk_out)]
                    proc = _run(args)
                    if proc.returncode != 0:
                        raise RuntimeError(f"Chunk {chunk_idx} failed:\n" + proc.stderr[-2000:])
                
                chunk_files.append(chunk_out)
        finally:
            config.TAIL_HOLD = old_tail

        stitched_video = work_dir / "stitched_video.mp4"
        if not dry_run:
            concat_lines = [f"file '{c.name}'" for c in chunk_files]
            concat_list.write_text("\n".join(concat_lines), encoding="utf-8")
            proc = _run([
                self.ffmpeg, "-hide_banner", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list), "-c", "copy", str(stitched_video)
            ])
            if proc.returncode != 0:
                raise RuntimeError("Stitching chunks failed:\n" + proc.stderr[-2000:])
            
        have_music = music_path is not None and Path(music_path).is_file()
        have_soundscape = soundscape_path is not None and Path(soundscape_path).is_file()
        soundscape_index = 2 + (1 if have_music else 0) if have_soundscape else None
        base_sfx_offset = 2 + (1 if have_music else 0) + (1 if have_soundscape else 0)

        validated_sfx = []
        for cue in (sfx_cues or []):
            c_start, c_end = float(cue["start"]), float(cue["end"])
            if c_end > target_len: c_end = round(target_len, 3)
            validated_sfx.append(dict(cue, start=c_start, end=c_end, input_index=base_sfx_offset + len(validated_sfx)))
        
        audio_lines = build_audio_filter(1, 2 if have_music else None, validated_sfx, soundscape_index=soundscape_index)
        
        chain = []
        if final_polish:
            chain += [config.FINAL_UNSHARP, config.FINAL_GRAIN, config.FINAL_EQ, config.FINAL_VIGNETTE]
        if captions_path is not None:
            chain.append(captions.ass_filter(captions_path))
            
        video_lines = [f"[0:v]{','.join(chain)}[vout]" if chain else "[0:v]copy[vout]"]
        final_graph = ";\n".join(video_lines + audio_lines)
        
        final_script = out_path.parent / "_filtergraph.txt"
        final_script.write_text(final_graph, encoding="utf-8")
        
        args = [self.ffmpeg, "-hide_banner", "-y", "-i", str(stitched_video), "-i", str(vo_path)]
        if have_music:
            args += ["-i", str(music_path)]
        if have_soundscape:
            args += ["-i", str(soundscape_path)]
        for cue in validated_sfx:
            args += ["-i", str(cue["local_path"])]
            
        args += ["-/filter_complex", str(final_script), "-map", "[vout]", "-map", "[aout]"]
        args += [
            "-t", f"{target_len:.3f}", "-r", str(config.FPS),
            "-c:v", "libx264", "-crf", str(config.X264_CRF), "-preset", config.X264_PRESET,
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", config.AAC_BITRATE, "-ar", str(config.AUDIO_RATE),
        ]
        if dry_run:
            return args + [str(out_path)], final_graph
            
        args += [str(out_path)]
        proc = _run(args)
        if proc.returncode != 0:
            raise RuntimeError("Final mux failed:\n" + proc.stderr[-2000:])
            
        return args, final_graph


def render_ken_burns_block(
    image_path: Path,
    out_path: Path,
    duration: float,
    *,
    motion_type: str = "zoom_in",
    width: int | None = None,
    height: int | None = None,
    fps: int = 24,
    ffmpeg: str | None = None,
) -> Path:
    """Render a high-resolution 2.5D Ken Burns Pan/Zoom video block from an image plate.

    Used for 16:9 longform documentary Model A hybrid compilation (ancient structures,
    maps, archaeological plates) while reserving generative AI video for key A-roll moments.
    """
    ffmpeg_exe = ffmpeg or config.resolve_ffmpeg()
    w = width or getattr(config, "WIDTH", 1920)
    h = height or getattr(config, "HEIGHT", 1080)
    total_frames = max(1, int(round(duration * fps)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    N = max(1, total_frames)
    texture_filter = ",unsharp=5:5:0.4,noise=alls=2:allf=t+u,eq=contrast=1.04:saturation=1.03,vignette=PI/6"

    # Smoothstep progress formula in FFmpeg zoompan: S = min(1, on/N)^2 * (3 - 2*min(1, on/N))
    smoothstep_clause = f"(min(1,on/{N})*min(1,on/{N})*(3-2*min(1,on/{N})))"

    if motion_type == "zoom_out":
        scale_w, scale_h = int(w * 1.20), int(h * 1.20)
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.16 - 0.14*{smoothstep_clause}':d={total_frames}:"
            f"x='clip(iw/2-(iw/zoom/2),0,iw-(iw/zoom))':y='clip(ih/2-(ih/zoom/2),0,ih-(ih/zoom))':s={w}x{h}:fps={fps}"
            f"{texture_filter}"
        )
    elif motion_type == "pan_right":
        scale_w, scale_h = int(w * 1.25), int(h * 1.25)
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.10':d={total_frames}:"
            f"x='clip(iw*0.04 + (iw*0.14)*{smoothstep_clause},0,iw-(iw/zoom))':y='clip(ih/2-(ih/zoom/2),0,ih-(ih/zoom))':s={w}x{h}:fps={fps}"
            f"{texture_filter}"
        )
    elif motion_type == "pan_left":
        scale_w, scale_h = int(w * 1.25), int(h * 1.25)
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.10':d={total_frames}:"
            f"x='clip(iw*0.18 - (iw*0.14)*{smoothstep_clause},0,iw-(iw/zoom))':y='clip(ih/2-(ih/zoom/2),0,ih-(ih/zoom))':s={w}x{h}:fps={fps}"
            f"{texture_filter}"
        )
    elif motion_type == "pan_up":
        scale_w, scale_h = int(w * 1.20), int(h * 1.30)
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08':d={total_frames}:"
            f"x='clip(iw/2-(iw/zoom/2),0,iw-(iw/zoom))':y='clip(ih*0.22 - (ih*0.14)*{smoothstep_clause},0,ih-(ih/zoom))':s={w}x{h}:fps={fps}"
            f"{texture_filter}"
        )
    else:  # zoom_in (default)
        scale_w, scale_h = int(w * 1.20), int(h * 1.20)
        vf = (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.02 + 0.14*{smoothstep_clause}':d={total_frames}:"
            f"x='clip(iw/2-(iw/zoom/2),0,iw-(iw/zoom))':y='clip(ih/2-(ih/zoom/2),0,ih-(ih/zoom))':s={w}x{h}:fps={fps}"
            f"{texture_filter}"
        )

    cmd = [
        ffmpeg_exe, "-hide_banner", "-y",
        "-loop", "1", "-i", str(image_path),
        "-vf", vf,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "fast",
        str(out_path),
    ]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"Ken Burns rendering failed for {image_path.name}:\n{proc.stderr[-1000:]}")
    return out_path
