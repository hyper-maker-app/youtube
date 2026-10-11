# YouTube Shorts Automation - Agent Execution Rules

This repository produces Zack D. Films-style 3D documentary Shorts in a vertical
9:16 frame. A real new run starts from an eight-shot screenplay outline, measures the
generated narration, then locks a provider-native 6–13 x 4.0-second plan (24–52s
footage) plus a 1.5-second cloned tail. The locked plan is persisted in `script.json`;
a resume must preserve it exactly.

## Benchmark reference and hook architecture

- The sole aesthetic reference is **https://www.youtube.com/@zackdfilms** (30M+ subscribers,
  45–58s sweet spot). Every prompt, edit, and audio decision must align with this benchmark.
- Hook architecture: the first 2–3 seconds must use second-person address ("You") with an
  immediate curiosity or shock scenario (e.g., "What happens if you try to open an airplane
  door mid-flight?"). Never start with third-person narration or dry facts.
- Camera scale progression follows a logical flow: `wide <-> medium <-> close <-> macro <-> micro <-> nano`.
  The story never pauses; continuous scale transitions (`scale_transition`) lock `center` framing.
- Visual DNA: glossy stylized 3D mannequins (Glossy Claymation, SSS subsurface scattering),
  mineralized cortical bone, translucent internal organs, viscous non-Newtonian fluids.
  Mannequin token contamination in internal organ/mechanical cutaways is strictly forbidden (ADR-024).

## Non-negotiable safety and visual rules

- Do not alter the `editor.py` half-open window gate `gte(time,t0)*lt(time,t1)`
  or the live crop clamp `clip(...,0,dim-(dim/zoom))`. They prevent double-owned
  boundary frames and black-edge exposure.
- Never add an API key, session token, endpoint URL, or provider model selection
  directly to Python source. Read configuration from `.env` through the provider
  boundary; keep `.env.example` synchronized with every new key.
- Characters do not speak. Prompts must require closed or neutral mouths; no
  dialogue and no lip-sync. Captions are FFmpeg/ASS only, never model-generated.
- Preserve 9:16 geometry throughout image generation, video generation, and
  FFmpeg assembly. Do not crop or letterbox into a landscape frame.
- Keep visual proof out of the lower-middle caption-safe zone. Use a baked marker
  (for example a neon-green arrow or red trajectory) only when the authored
  `proof_on_screen` demands it; never add decorative overlays automatically.
- No acoustic void: videos must never have silence behind narration. When `--music`
  is not provided, the pipeline auto-generates a mood-matched audio bed via FFmpeg
  lavfi synthesis (ADR-025). `--no-music` disables BGM entirely.
- Mode detection priority: `incident > mechanical > anatomical` (default). The
  pipeline supports three production modes with distinct visual, SFX, and audio bed
  profiles (ADR-026). Do not override detection priority.
- Broadcast audio target: integrated -14 LUFS / -1.5 dBTP per YouTube Shorts broadcast standard.
- Music volume (BGM): `MUSIC_VOLUME = 0.19` (-14.4 dBFS). No hard ducking pumping on
  narration voice for SFX; voiceover must never be artificially dipped (ADR-017).
- ASMR Foley hits: 0.55–0.75s natural decay envelope (ADR-029); no abrupt cutoffs or prolonged synthetic loops.
  Peak-transient synchronized to visual impact moment via `detect_peak_transient`.
  Mastering EQ & Gain: HP 75 Hz, +2.0 dB @ 4.0 kHz (crisp ASMR presence), -10.0 dBFS gain staging to prevent voice pumping.

## Timeline and smoke tests

- Full new runs: after narration measurement, 6–13 blocks x 4.0 seconds and N+1
  sequential Match-Cut keyframes. The temporary eight-shot outline is never a render cap.
- `--test-blocks N` is an isolated new-run smoke test for 1 through 8 blocks. It
  persists a clearly marked short test timeline, generates only its keyframes and
  blocks, and writes `test_final.mp4`. It cannot be combined with `--resume`.
- A normal resume must use its stored `timeline`; do not replan it because current
  defaults differ.

## Provider and cost boundary

- `python main.py --dry-run --topic "..."` makes no remote LLM, image, voice, or
  video request. It compiles the complete local FFmpeg graph against lavfi fixtures.
- A non-dry run uses the explicit LLM/image/video/voice provider selections from
  `.env` or CLI overrides. The factory never silently falls back.
- A Flow CLI/session failure raises `HandoffPending` and writes `handoff.md`.
  Complete those exact blocks manually or intentionally start a separate run with
  `--video vertex_veo` or `--video local`; never substitute a provider invisibly.

## Decision memory and experiment history (ADR Mandate)

- Consult `DECISIONS.md` (`youtube-decision-memory` MCP or `python scripts/decision.py search "<topic>"`) before proposing or implementing changes to pipeline architecture, video models, audio logic, or visual styling.
- Do not repeat or re-propose previously `ABANDONED` or `REJECTED` approaches (such as lip-sync, decorative neon arrows, or fast crash zooms).
- If an experiment fails, produces bad visual output, or the user requests cancellation/revert ("olmadı / iptal et / geri al"), the AI agent must AUTOMATICALLY record it into `DECISIONS.md` using `scripts/decision.py record` documenting what was requested, what was done, why it was abandoned, and the permanent lesson learned.

## Automatic maintenance and git push mandate (Zero manual effort for user)

- The user will NEVER manually run `python scripts/audit_and_sync.py`, git commands, or MCP sync scripts.
- Whenever ANY developer or AI agent (Gemini, Claude, Cursor, Codex, Antigravity, etc.) modifies code, configs, prompts, documentation, or assets:
  1. The agent must AUTOMATICALLY run `python scripts/audit_and_sync.py` in the background and verify that all checks pass (0 failures) before responding to the user.
  2. The agent must AUTOMATICALLY stage, commit, and push all changes (`git add .`, `git commit -m "..."`, `git push origin main`) to GitHub (`https://github.com/hyper-maker-app/youtube.git`). Leaving uncommitted or unpushed modifications in the local workspace is strictly forbidden.
- If MCP configurations or server scripts change, the agent must automatically run `python scripts/sync_mcp_configs.py`.
- Read `ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, `DURUM.md`, and `WALKTHROUGH.md` as companion references.


## Autonomous production protocol

For a real user request to produce a video, ask only: “Hangi video üretim yöntemini
kullanalım? [1] Vertex AI (resmî API) / [2] Flow Agent (GitHub repo/CLI)”. After 1 or
2, do not ask for a topic, duration, voice, captions, model, cost, or block count.
Use `--auto-topic` (or omitted `--topic` after an explicit route) to write a sourced
`topic_selection.json`, exclude only completed/published history, and start the
audio-driven native-block plan. `--dry-run` is local-only and never asks a provider question.

Prompt compilation is provider-neutral: every keyframe and motion prompt carries the
same 9:16 style, scale-aware lighting, continuity anchor, caption-safe, proof, and
closed-mouth/no-text contract. Markers are optional evidence only: use one only when
`proof_on_screen` authors it, keep it out of lower-middle, and make its quadrant match
the camera target. One clip may depict one visible causal state change and one location.

## Dynamic block & word matrix (6–13 blocks / 60–120 words)

- **Micro / Shock Facts:** 6–7 blocks | 24–28s | 60–75 words. Instant reflexes, rapid biological reactions.
- **Standard Zack D. Story (Sweet Spot):** 8–10 blocks | 32–40s | 75–100 words. Accidents, human cases, myths.
- **Deep Mechanism & Surgery:** 11–13 blocks | 44–52s | 100–120 words. Airplane door, submarine pressure, turbines.
- **Red line ceiling:** Narration text NEVER exceeds 120 words (`safe_target = min(120, target)` in `config.py`),
  video NEVER exceeds 13 blocks (52s + 1.5s cloned tail).
- **Diction tempo:** Deepgram Hermes (`aura-2-hermes-en`), 1.12x speed, 2.75 WPS (165 WPM) staccato rhythm.
  Sentences maximum 18–20 words.

## MCP active usage mandate

During all operations, actively utilize the project's local MCP servers:
- `youtube-decision-memory`: Query before proposing/implementing architectural changes (`search_decisions`).
  Never re-propose ABANDONED or REJECTED approaches.
- `youtube-research`: Validate medical and physical claims (`evaluate_claim`, `research_topic`).
- `youtube-media-inspector`: Measure audio LUFS (`measure_audio_loudness`), detect black frames/freezes
  (`detect_black_or_freeze`), inspect audio spectral dynamics & clipping (`analyze_audio_spectrum`),
  and score video motion smoothness (`analyze_video_stability`) on rendered outputs.
- `youtube-pipeline-db`: Check run history (`recent_topics`, `topic_exists`) and record runs (`record_run`).

## Zack D. Films benchmark replication & POV continuity rules (ADR-037, ADR-038)

- **1-FPS Frame-by-Frame Reference Audit (ADR-037):** When replicating or benchmarking against a Zack D. Films video, extract 1 fps frames (`fps=1`) first and match camera POV (first-person driver POV vs third-person), interior material palette (`warm tan/beige leather`), forearm/wardrobe continuity (`bare male forearms with warm natural skin tone, no sleeves, no watch, plain white crew-neck t-shirt, blue denim jeans`), and color-coded interactive highlights (glowing red-orange jammed door handle, glowing neon-green `#39FF14` seatbelt strap, matte-black electric window switch).
- **Sealed-Cabin Plunge Physics & Underwater Lighting Lock (ADR-038):** During vehicle water-plunge transitions (`block01`), water must splash and rise *outside* the glass windshield while the cabin interior stays dry. For all submerged cabin keyframes and blocks (`kf02`–`kf04`, `block02`–`block03`), explicitly lock dim cool-blue underwater interior lighting and specify dark blue underwater lake water outside the side window/mirror so the I2V model never hallucinates sunny daylight or a dry asphalt parking lot outside. Explicitly forbid face/head reflections in submerged glass (`No faces or heads reflected in the glass`) and forbid chin/neck intrusion at the bottom edge of high-angle torso POV shots.
- **Solid 3D Volumetric Force Arrows:** Never render pressure or force vectors as flat hollow 2D neon outlines (`->`). Always specify `solid 3D glowing volumetric arrows (solid 3D conical arrowheads with glowing cylindrical shafts, NOT flat hollow outline arrows)`.
- **NanoBanana (`NARWHAL`) Inline Safety Phrasing:** In static keyframe prompts (`kf01`), avoid self-harm-adjacent collision phrasing like `"drives off ... straight into a lake"` (which triggers an inline empty-frame refusal); use `"drives toward a calm blue lake on a sunny day"` for the static keyframe and reserve the water plunge for the `abra_i2v_4s` motion prompt.
- **Flow Agent Port 8001 Isolation:** Use only the `http://127.0.0.1:8001` Flow Agent service (`--video flow_agent --image flow_agent`) with `account_index='0'` locked in `flow.db`. Never leave `flow-windows.exe bridge` running in the background as a daemon so CDP port `9222` is never locked.
- **Flow Agent Beluga Image Model & HTTP Captcha Bypass (ADR-039):** Use `FLOW_IMAGE_MODEL=beluga` as default image model to eliminate batchexecute refusals. Set `FLOW_RECAPTCHA=http` in `.env` to avoid broken broker assessment blocks (`PUBLIC_ERROR_UNUSUAL_ACTIVITY`).
- **Underwater Egress & Circular Mechanical Cutaway Invariants (ADR-039):** For submerged escape progressions, render upward swimming POV looking toward the shimmering sunlit water surface with bare breaststroke arms and rising bubbles. For electrical failure explanations, author macro circular door cutaways showing bright yellow window gear motors and waterlogged green PCB circuit boards shorting out.

## 16:9 Longform Documentary & Zero-Focus Background Video Factory (ADR-040, ADR-042, ADR-043)

- **Format Selection & Model A Hybrid Architecture (ADR-043):**
  - **16:9 Longform Documentary (`--format longform`, `LONGFORM_MODE=true`):** 1920x1080 / 1280x720 Widescreen format starring 28-year-old female chronological time-traveler and investigative explorer "Nova" (`services/character.py`).
    - **Persona & Identity Invariants:** Immutable facial features across all videos (striking hazel eyes with warm amber flecks, defined cheekbones, natural skin texture with subtle fine freckles across nose bridge, dark chestnut wavy hair); signature time-traveler artifact (intricate celestial brass temporal chronometer wrist device with glowing gyroscopic dials worn on her left wrist); and era-appropriate wardrobe camouflage (Neolithic, Egyptian, Greco-Roman, Ottoman, Medieval, Victorian).
    - **Model A Hybrid Compilation (`LONGFORM_HYBRID_MODE=true`):** Key A-Roll on-camera host moments (opening arrival hook, midpoint turning point discovery, closing verdict; 10-15% of runtime) use generative AI Video via Google Flow (`playwright_flow`, port 9223). Detailed historical/archaeological B-Roll plates (85-90% of runtime: ancient architecture, subterranean chambers, relics, maps) use high-resolution 2.5D Ken Burns Pan/Zoom montages (`editor.render_ken_burns_block`).
    - **Voice & Audio:** Deepgram Aura-2 narration with natural documentary pacing (1.0x, `DEEPGRAM_TTS_SPEED=1.0`), accompanied by 40 Hz deep-bass `epic_curiosity` audio bed.
  - **9:16 Shorts Mode (`--format short`):** Vertical format (1080x1920), Zack D. Films 3D mannequin style, characters do not speak, lower-middle caption-safe area.
- **Zero-Focus Background Factory (`playwright_flow`, Port `9223`):**
  - Uses an isolated minimized Chrome session on CDP port `9223` (`FlowCDPProfile`), launched once via `chrome_flow.bat`.
  - Mints genuine 2500+ char browser reCAPTCHA Enterprise tokens on `flow.google.com` and synchronizes live cookies and `WIZ_global_data` page tokens (`SNlM0e` / `FdrFJe`) over `ws://127.0.0.1:9222` to `flow-windows.exe`.
  - Guarantees zero window focus stealing and zero OS mouse movement so the user can play games (e.g. Counter-Strike 2) or work while videos generate in the background.
  - Production invocation: `python main.py --format longform --topic "The Lost Labyrinth of Hawara" --video playwright_flow --image playwright_flow`.




