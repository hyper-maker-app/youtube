"""Motion authenticity analysis: is a clip real video or a still photo being moved?

A Ken Burns clip (zoom/pan over one still) is *globally rigid*: every pixel's motion
between two frames is explained by ONE 2D affine transform. Genuine diffusion video
has parallax, cloth, dust, water and body motion, so after the best global affine fit
is removed a *spatially coherent* residual remains.

Why not "frame difference" or scene-score? A zoom changes every pixel, so those
metrics read Ken Burns as "lots of motion". That is exactly how earlier checks were fooled.

Metrics (per clip):
  frozen_ratio        fraction of sampled steps with ~zero temporal change
  freeze_tail_s       seconds of frozen footage at the END of the clip (tpad/clone padding)
  coherent_residual   median over steps of the p90 of the *smoothed* non-affine flow (px @320w)
                      - smoothing kills sensor/film-grain noise (spatially incoherent)
  verdict             "frozen" | "rigid_2d_motion" | "diffusion_motion" | "unreadable"

Thresholds were calibrated on synthetic clips (see scripts/selftest_motion_gate.py);
override via env if real Flow footage needs different values.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

ANALYSIS_W = 320
ANALYSIS_H = 180
STEP_SECONDS = 0.25
MAX_STEPS = 40

FROZEN_MAD = float(os.getenv("MOTION_FROZEN_MAD", "0.35"))          # mean abs gray diff (0-255)
FROZEN_RATIO_FAIL = float(os.getenv("MOTION_FROZEN_RATIO_FAIL", "0.60"))
FREEZE_TAIL_FAIL_S = float(os.getenv("MOTION_FREEZE_TAIL_FAIL_S", "1.0"))
RESIDUAL_PX_MIN = float(os.getenv("MOTION_RESIDUAL_PX_MIN", "0.30"))


@dataclass
class ClipMotionReport:
    path: str
    readable: bool = True
    duration: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    steps: int = 0
    frozen_ratio: float = 0.0
    freeze_tail_s: float = 0.0
    mean_abs_diff: float = 0.0
    coherent_residual: float = 0.0
    global_motion_px: float = 0.0
    verdict: str = "unreadable"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _read_gray_frames(path: Path) -> tuple[list[tuple[float, np.ndarray]], float, float, int, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return [], 0.0, 0.0, 0, 0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if fps <= 0 or n <= 0:
        cap.release()
        return [], fps, 0.0, w, h
    duration = n / fps
    stride = max(1, int(round(fps * STEP_SECONDS)))
    frames: list[tuple[float, np.ndarray]] = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % stride == 0 or idx == n - 1:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            g = cv2.resize(g, (ANALYSIS_W, ANALYSIS_H), interpolation=cv2.INTER_AREA)
            frames.append((idx / fps, g))
        idx += 1
    cap.release()
    return frames, fps, duration, w, h


def _fit_affine_to_flow(flow: np.ndarray) -> np.ndarray:
    """Robust least-squares affine fit of a dense flow field -> modelled flow (same shape)."""
    h, w = flow.shape[:2]
    ys, xs = np.mgrid[0:h:4, 0:w:4]
    px = xs.ravel().astype(np.float64)
    py = ys.ravel().astype(np.float64)
    fx = flow[0:h:4, 0:w:4, 0].ravel().astype(np.float64)
    fy = flow[0:h:4, 0:w:4, 1].ravel().astype(np.float64)
    A = np.stack([px, py, np.ones_like(px)], axis=1)
    keep = np.ones(len(px), dtype=bool)
    coef_x = coef_y = np.zeros(3)
    for _ in range(4):  # IRLS-style: drop worst 25% each round so moving objects don't bias the fit
        coef_x, *_ = np.linalg.lstsq(A[keep], fx[keep], rcond=None)
        coef_y, *_ = np.linalg.lstsq(A[keep], fy[keep], rcond=None)
        res = np.hypot(A @ coef_x - fx, A @ coef_y - fy)
        thr = np.quantile(res[keep], 0.75)
        keep = res <= max(thr, 1e-3)
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    mx = coef_x[0] * gx + coef_x[1] * gy + coef_x[2]
    my = coef_y[0] * gx + coef_y[1] * gy + coef_y[2]
    return np.stack([mx, my], axis=-1).astype(np.float32)


def analyze_clip(path: str | Path) -> ClipMotionReport:
    path = Path(path)
    rep = ClipMotionReport(path=str(path))
    frames, fps, duration, w, h = _read_gray_frames(path)
    rep.fps, rep.duration, rep.width, rep.height = fps, duration, w, h
    if len(frames) < 3:
        rep.readable = False
        rep.reasons.append("clip unreadable or shorter than 3 sampled frames")
        return rep

    mads: list[float] = []
    residuals: list[float] = []
    gmotion: list[float] = []
    for (t0, a), (t1, b) in zip(frames, frames[1:]):
        mad = float(np.mean(cv2.absdiff(a, b)))
        mads.append(mad)
        if mad < FROZEN_MAD:
            continue
        flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 21, 3, 5, 1.1, 0)
        model = _fit_affine_to_flow(flow)
        resid = np.linalg.norm(flow - model, axis=-1)
        resid = cv2.GaussianBlur(resid, (0, 0), 6.0)  # keep only spatially coherent residual
        residuals.append(float(np.quantile(resid, 0.90)))
        gmotion.append(float(np.median(np.linalg.norm(model, axis=-1))))

    rep.steps = len(mads)
    frozen_flags = [m < FROZEN_MAD for m in mads]
    rep.frozen_ratio = sum(frozen_flags) / max(1, len(frozen_flags))
    rep.mean_abs_diff = float(np.mean(mads))
    tail = 0
    for flag in reversed(frozen_flags):
        if not flag:
            break
        tail += 1
    rep.freeze_tail_s = round(tail * STEP_SECONDS, 2)
    rep.coherent_residual = float(np.median(residuals)) if residuals else 0.0
    rep.global_motion_px = float(np.median(gmotion)) if gmotion else 0.0

    if rep.frozen_ratio >= FROZEN_RATIO_FAIL:
        rep.verdict = "frozen"
        rep.reasons.append(f"{rep.frozen_ratio:.0%} of sampled steps show no change")
    elif rep.coherent_residual < RESIDUAL_PX_MIN:
        rep.verdict = "rigid_2d_motion"
        rep.reasons.append(
            f"all motion explained by one 2D affine transform (residual {rep.coherent_residual:.3f}px "
            f"< {RESIDUAL_PX_MIN}px): digital zoom/pan of a still"
        )
    else:
        rep.verdict = "diffusion_motion"
    if rep.verdict == "diffusion_motion" and rep.freeze_tail_s >= FREEZE_TAIL_FAIL_S:
        rep.reasons.append(f"frozen tail of {rep.freeze_tail_s}s (clone padding)")
    return rep


def is_genuine(rep: ClipMotionReport) -> bool:
    return rep.readable and rep.verdict == "diffusion_motion" and rep.freeze_tail_s < FREEZE_TAIL_FAIL_S
