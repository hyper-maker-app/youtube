---
name: ffmpeg-diagnostics
description: Diagnose and inspect FFmpeg filtergraphs, half-open window math, ASS subtitles, and audio loudness.
---

# FFmpeg diagnostics

Use this skill when diagnosing render glitches, audio ducking, freeze frames, or caption errors.

- Never modify the half-open window gate: `gte(time,t0)*lt(time,t1)` in `editor.py`.
- Never modify the live crop clamp: `clip(dim*target - dim/zoom/2, 0, dim - dim/zoom)`.
- Use the `youtube-media-inspector` MCP or `scripts/audit_and_sync.py` to inspect LUFS loudness (-16 to -13 LUFS is optimal) and detect freeze/black frames.
- Subtitle ASS files must fit the vertical 1080x1920 layout and must never collide with visual proof markers.
