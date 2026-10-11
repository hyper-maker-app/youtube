# Gemini / Antigravity Project Instructions - YouTube Shorts Automation

Follow `PROJECT_CONTEXT.md`, `AGENTS.md`, and `WALKTHROUGH.md` as authoritative references.
Consult `DECISIONS.md` (ADR log), `DURUM.md` (status), and `WALKTHROUGH.md` (release log) before proposing or implementing changes.

## Core Invariants
1. Timeline: Provider-native 6–13 x 4.0s (or 5–8s Veo/H3) blocks based on measured voice duration. 1.5s cloned tail. **Max 120 words** for English Deepgram productions. Resumed runs preserve their saved timeline.
2. FFmpeg math: Do not touch `gte(time,t0)*lt(time,t1)` gates or `clip(...,0,dim-(dim/zoom))` clamps in `editor.py`.
3. Zack D. Films style: Benchmark is https://www.youtube.com/@zackdfilms. Characters never speak or lip-sync (closed/neutral mouth). 9:16 vertical framing. Lower-middle caption-safe area. Camera scale flow: `wide <-> medium <-> close <-> macro <-> micro <-> nano` with center lock on scale transitions.
4. Evidence only: Markers (arrows/trajectories) only when `proof_on_screen` explicitly demands it.
5. Environment: Secrets only in `.env`; keep `.env.example` synchronized.
6. No acoustic void: `--music` overrides, auto-generated lavfi bed is default, `--no-music` disables (ADR-025). Sidechain ducking without voice pumping (`MUSIC_VOLUME = 0.19`, ADR-017).
7. Tri-modality: `incident > mechanical > anatomical` detection priority (ADR-026).
8. Dynamic block/word bands: Micro/Shock (6–7 blocks, 60–75 words), Standard (8–10 blocks, 75–100 words), Deep Mechanism (11–13 blocks, 100–120 words). Ceiling: strictly max 120 words and 13 blocks.
9. Diction tempo: Deepgram Hermes `aura-2-hermes-en`, 1.12x speed, 2.75 WPS (165 WPM) staccato rhythm. Sentences max 18–20 words.
10. Broadcast audio: Integrated -14 LUFS / -1.5 dBTP. ASMR Foley natural decay envelope (0.55–0.75s, -10 dBFS) aligned to peak transient (ADR-029).
11. Benchmark POV, Underwater Continuity & Flow Agent Invariants (ADR-037, ADR-038, ADR-039): Match 1-fps reference camera POV (first-person driver POV), warm tan/beige interior palette, bare forearm/wardrobe lock (no sleeves, no watch, white crew-neck t-shirt, blue jeans), sealed-cabin water-plunge physics (water rises *outside* the windshield while cabin stays dry), dim cool-blue underwater interior lighting with dark blue water outside side windows (no sunny parking-lot hallucination or glass face reflections), solid 3D volumetric force arrows (never hollow 2D outlines), safe static keyframe phrasing (`drives toward a calm blue lake`), Flow Agent port `8001` isolation without daemonizing `flow-windows.exe bridge`, `FLOW_IMAGE_MODEL=beluga` stability, `FLOW_RECAPTCHA=http` broker bypass, upward swimming POV egress, and circular door mechanical cutaways with waterlogged electronics.
12. 16:9 Longform Time-Traveler Nova Mode & Model A Hybrid Background Factory (ADR-040, ADR-042, ADR-043): Two production formats supported: (A) 16:9 Widescreen Longform documentary (`--format longform`, `LONGFORM_MODE=true`) starring 28yo female chronological time-traveler & explorer "Nova" with locked facial features (hazel eyes, freckles, bone structure), signature temporal chronometer wrist artifact, era wardrobe camouflage, and Model A Hybrid compilation (`LONGFORM_HYBRID_MODE=true`): 3 key A-Roll scenes (10-15%) animated via Google Flow CDP port 9223 (`chrome_flow.bat`), and 85-90% B-Roll archaeological mystery footage rendered via high-res 2.5D Ken Burns Pan/Zoom montages, accompanied by Deepgram natural pacing narration (1.0x) and 40 Hz deep-bass `epic_curiosity` audio bed; (B) 9:16 Shorts mode (`--format short`). Video and image generation runs 100% in the background via Playwright CDP (`IMAGE_PROVIDER=playwright_flow`, `VIDEO_PROVIDER=playwright_flow`, port `9223`) started once via `chrome_flow.bat`, minting real browser reCAPTCHA Enterprise tokens (2500+ chars) and syncing live cookies over `ws://127.0.0.1:9222` to `flow-windows.exe` with zero OS mouse movement and zero window focus stealing while user plays CS2.


## Decision Memory (ADR) Mandate
- Always check `DECISIONS.md` (`youtube-decision-memory` MCP or `python scripts/decision.py search "query"`) before changing architecture or visual styles.
- Automatically document cancelled or failed experiments in `DECISIONS.md` with status `ABANDONED` or `REJECTED`.

## Automatic Maintenance & Git Push Mandate (Zero User Effort)
- The user will never manually run audit or synchronization scripts, nor any git commands.
- The assistant must automatically execute `python scripts/audit_and_sync.py` after code/prompt modifications to ensure 0 failures.
- Mandatory Git Commit & Push: Whenever any code, documentation, prompts, configs, or assets are modified, the assistant must automatically commit and push all changes (`git add .`, `git commit -m "..."`, `git push origin main`) to GitHub before concluding the turn. Leaving uncommitted or unpushed changes is strictly forbidden.

## MCP Active Usage Mandate
- Actively use `youtube-decision-memory` (`search_decisions`), `youtube-research` (`evaluate_claim`, `research_topic`), `youtube-media-inspector` (`measure_audio_loudness`, `detect_black_or_freeze`, `analyze_audio_spectrum`, `analyze_video_stability`), and `youtube-pipeline-db` (`recent_topics`, `record_run`) for verification, claim evaluation, loudness/quality inspection, and run history.

