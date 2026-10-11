# Claude Assistant Guidelines - YouTube Shorts Automation

Follow `PROJECT_CONTEXT.md`, `AGENTS.md`, and `WALKTHROUGH.md` as authoritative references.
Consult `DECISIONS.md` (ADR log), `DURUM.md` (status), and `WALKTHROUGH.md` (release log) before proposing or implementing changes.

## Non-negotiable Production Contracts
1. Dynamic provider-native plan: 6–13 x 4.0s (or 5–8s Veo/H3) blocks based on measured voice duration; 1.5s cloned tail; preserve persisted resumes.
2. FFmpeg safety: Never modify `gte(time,t0)*lt(time,t1)` gates or `clip(...,0,dim-(dim/zoom))` clamps in `editor.py`.
3. Characters never speak, lip-sync, or move mouths; captions are FFmpeg/ASS only.
4. Keep all assets and renders 9:16 vertical (1080x1920 or 720x1280) with clear lower-middle caption-safe zones.
5. All credentials and models come from `.env`; keep `.env.example` synchronized.
6. Benchmark POV, Underwater Continuity & Flow Agent Invariants (ADR-037, ADR-038, ADR-039): Match 1-fps reference POV, warm tan/beige interior palette, bare forearm/wardrobe lock (no sleeves/watch), sealed-cabin plunge physics (water rises outside windshield, cabin stays dry), cool-blue underwater lighting lock with dark blue water outside side windows (no face reflections or dry asphalt hallucinations), solid 3D volumetric arrows (never flat hollow outlines), safe static keyframe phrasing (`drives toward a calm blue lake`), Flow Agent `http://127.0.0.1:8001` isolation without running `flow-windows.exe bridge` daemon, `FLOW_IMAGE_MODEL=beluga` stability, `FLOW_RECAPTCHA=http` broker bypass, upward swimming POV egress, and circular door mechanical cutaways with waterlogged electronics.
7. 16:9 Longform Time-Traveler Nova Mode & Model A Hybrid Background Factory (ADR-040, ADR-042, ADR-043): Two production formats supported: (A) 16:9 Widescreen Longform documentary (`--format longform`, `LONGFORM_MODE=true`) starring 28yo female chronological time-traveler & explorer "Nova" with locked facial features (hazel eyes, freckles, bone structure), signature temporal chronometer wrist artifact, era wardrobe camouflage, and Model A Hybrid compilation (`LONGFORM_HYBRID_MODE=true`): 3 key A-Roll scenes (10-15%) animated via Google Flow CDP port 9223 (`chrome_flow.bat`), and 85-90% B-Roll archaeological mystery footage rendered via high-res 2.5D Ken Burns Pan/Zoom montages, accompanied by Deepgram natural pacing narration (1.0x) and 40 Hz deep-bass `epic_curiosity` audio bed; (B) 9:16 Shorts mode (`--format short`). Video and image generation runs 100% in the background via Playwright CDP (`IMAGE_PROVIDER=playwright_flow`, `VIDEO_PROVIDER=playwright_flow`, port `9223`) started once via `chrome_flow.bat`, minting real browser reCAPTCHA Enterprise tokens (2500+ chars) and syncing live cookies over `ws://127.0.0.1:9222` to `flow-windows.exe` with zero OS mouse movement and zero window focus stealing while user plays CS2.


## Decision Memory & Experiment History (ADR Mandate)
- Before proposing or implementing any new architecture, animation, style, or workflow change, search `DECISIONS.md` (`python scripts/decision.py search "topic"`).
- If an idea was previously marked `ABANDONED` or `REJECTED`, warn the user with the ADR reasoning and do not re-introduce failed patterns.
- If a change is attempted and fails, or if the user requests cancellation/revert ("olmadı / iptal et / geri al"), AUTOMATICALLY record it into `DECISIONS.md` using `scripts/decision.py record`.

## Automatic Maintenance and Git Push Mandate (Zero Manual Effort for User)
- The user will NEVER manually run `python scripts/audit_and_sync.py` or git commands.
- Whenever you make changes to pipeline code, providers, shaders, prompts, configs, or docs, you MUST automatically:
  1. Run `python scripts/audit_and_sync.py` and verify 0 failures before finishing.
  2. Automatically commit and push all changes (`git add .`, `git commit -m "..."`, `git push origin main`) to GitHub. Leaving uncommitted or unpushed modifications is strictly forbidden.
- If MCP configurations or tools change, automatically run `python scripts/sync_mcp_configs.py`.

