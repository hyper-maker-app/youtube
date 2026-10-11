#!/usr/bin/env python3
"""Self-test for services/motion_authenticity.py.

Builds synthetic clips with known ground truth and asserts the gate classifies them correctly.
NOTE: the "diffusion" class here is a *proxy* (layered parallax + non-rigid warp + moving blobs).
Always re-validate on one real Flow clip: `python scripts/benchmark_quality_gate.py --clip block02.mp4`.
Exit code 1 if any expectation fails.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from services.motion_authenticity import analyze_clip  # noqa: E402

try:
    import config  # noqa: E402
    FFMPEG = config.resolve_ffmpeg()
except Exception:  # pragma: no cover - standalone fallback
    FFMPEG = "ffmpeg"

W, H, FPS, SECS = 1280, 720, 30, 4
rng = np.random.default_rng(7)


def _texture(w: int, h: int) -> np.ndarray:
    base = rng.integers(0, 255, (h // 8, w // 8, 3), dtype=np.uint8)
    img = cv2.resize(base, (w, h), interpolation=cv2.INTER_CUBIC)
    for _ in range(60):
        cv2.circle(img, (int(rng.integers(0, w)), int(rng.integers(0, h))), int(rng.integers(10, 60)),
                   [int(x) for x in rng.integers(0, 255, 3)], -1)
    return cv2.GaussianBlur(img, (0, 0), 1.2)


def _write(frames, out: Path) -> None:
    p = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "18", str(out)], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close()
    p.wait()


def make_frozen(out: Path):
    img = cv2.resize(_texture(W, H), (W, H))
    _write((img for _ in range(FPS * SECS)), out)


def _kb_frames(zoom_per_s=0.06, pan_px_per_s=0.0, grain=0.0):
    still = _texture(int(W * 1.4), int(H * 1.4))
    n = FPS * SECS
    for i in range(n):
        t = i / FPS
        s = 1 + zoom_per_s * t
        cw, ch = W / s, H / s
        cx = still.shape[1] / 2 + pan_px_per_s * t
        cy = still.shape[0] / 2
        M = np.float32([[W / cw, 0, -(cx - cw / 2) * W / cw], [0, H / ch, -(cy - ch / 2) * H / ch]])
        fr = cv2.warpAffine(still, M, (W, H), flags=cv2.INTER_CUBIC)
        if grain > 0:
            fr = np.clip(fr.astype(np.float32) + rng.normal(0, grain, fr.shape), 0, 255).astype(np.uint8)
        yield fr


def make_kb_zoom(out: Path):
    _write(_kb_frames(zoom_per_s=0.06), out)


def make_kb_pan(out: Path):
    _write(_kb_frames(zoom_per_s=0.0, pan_px_per_s=60), out)


def make_kb_grain_cheat(out: Path):
    """Ken Burns + animated film grain: tries to fake 'life' with per-frame noise."""
    _write(_kb_frames(zoom_per_s=0.06, grain=6.0), out)


def make_parallax(out: Path, freeze_tail_s: float = 0.0):
    """3 depth layers at different speeds + cloth-like sinusoidal warp + drifting dust blobs."""
    far = _texture(int(W * 1.5), H)
    mid = _texture(int(W * 1.5), H)
    near = _texture(int(W * 1.5), H)
    mask_mid = cv2.GaussianBlur((rng.random((H, int(W * 1.5))) > 0.55).astype(np.float32), (0, 0), 25)[..., None] > 0.5
    mask_near = cv2.GaussianBlur((rng.random((H, int(W * 1.5))) > 0.7).astype(np.float32), (0, 0), 35)[..., None] > 0.5
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    n = FPS * SECS
    live = n - int(freeze_tail_s * FPS)
    last = None
    def gen():
        nonlocal last
        for i in range(n):
            if i >= live and last is not None:
                yield last
                continue
            t = i / FPS
            def crop(layer, speed):
                x0 = int(speed * t)
                return layer[:, x0:x0 + W]
            fr = crop(far, 15).copy()
            m1 = crop(mask_mid.astype(np.uint8), 45).astype(bool)
            fr = np.where(m1, crop(mid, 45), fr)
            m2 = crop(mask_near.astype(np.uint8), 110).astype(bool)
            fr = np.where(m2, crop(near, 110), fr)
            mapx = gx + 6 * np.sin(gy / 40 + t * 3.0)
            mapy = gy + 4 * np.sin(gx / 55 + t * 2.2)
            fr = cv2.remap(fr, mapx, mapy, cv2.INTER_LINEAR)
            for k in range(25):
                cx = int((k * 97 + 70 * t * (1 + k % 3)) % W)
                cy = int((k * 53 - 25 * t * (1 + k % 2)) % H)
                cv2.circle(fr, (cx, cy), 6, (230, 230, 230), -1)
            last = fr
            yield fr
    _write(gen(), out)


CASES = [
    ("frozen_still", make_frozen, "frozen"),
    ("ken_burns_zoom", make_kb_zoom, "rigid_2d_motion"),
    ("ken_burns_pan", make_kb_pan, "rigid_2d_motion"),
    ("ken_burns_plus_grain_cheat", make_kb_grain_cheat, "rigid_2d_motion"),
    ("parallax_diffusion_proxy", make_parallax, "diffusion_motion"),
]


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        for name, maker, expected in CASES:
            out = Path(td) / f"{name}.mp4"
            maker(out)
            rep = analyze_clip(out)
            ok = rep.verdict == expected
            failures += 0 if ok else 1
            print(f"[{'OK ' if ok else 'BAD'}] {name:30s} expected={expected:18s} got={rep.verdict:18s} "
                  f"resid={rep.coherent_residual:.3f}px frozen={rep.frozen_ratio:.0%} mad={rep.mean_abs_diff:.2f}")
        out = Path(td) / "parallax_frozen_tail.mp4"
        make_parallax(out, freeze_tail_s=1.5)
        rep = analyze_clip(out)
        ok = rep.verdict == "diffusion_motion" and rep.freeze_tail_s >= 1.0
        failures += 0 if ok else 1
        print(f"[{'OK ' if ok else 'BAD'}] {'parallax_with_1.5s_freeze_tail':30s} tail={rep.freeze_tail_s}s verdict={rep.verdict}")
    print("\nSELFTEST", "PASSED" if failures == 0 else f"FAILED ({failures})")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
