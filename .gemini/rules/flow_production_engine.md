# Flow Production Engine Invariant (v4.6 Hyper Maker)

## CRITICAL: "Flow" Definition & Mandatory Production Workflow

1. **What "Flow" Means in This Workspace:**
   - In this repository, **"Flow" ALWAYS refers to Google Flow CDP (Port 9223) + Deepgram Aura-2 + Remotion 60 FPS + FFmpeg Broadcast Editor** located in `engine/` and bridged via `engine/flow_bridge.py`.
   - It does NOT mean generic ComfyUI, Grok Sequence Runner, or conceptual workflow diagrams.

2. **3-Tier Production Policy & Unified CLI Commands:**
   - **Tier 1 (Zero-Cost Draft & Experiment Mode):**
     `python tools/cinematic_studio_cli.py produce-film "<Title>" --genre "<Genre>" --duration <Seconds> --plan-only` (or `--dry-run`)
     *Cost:* 0 Flow Credits. Generates the screenplay via Grok 4.6, Deepgram Aura-2 voiceover, Remotion graphics, and color storyboard proxy cards.
   - **Tier 2 (Rapid Test Validation Mode):**
     `python tools/cinematic_studio_cli.py produce-film "<Title>" --genre "<Genre>" --duration <Seconds> --test`
     *Cost:* ~30-40 credits for 60s (360p low-cost validation). Uses **Omni 1.1 Flash** (360p / 4s = 4 credits) until December 5, 2026; automatically falls through to **Veo 3.1 - Lite** (10 credits) after December 5, 2026.
   - **Tier 3 (Broadcast Cinematic Master Mode):**
     `python tools/cinematic_studio_cli.py produce-film "<Title>" --genre "<Genre>" --duration <Seconds> --real`
     *Cost:* Optimized 720p HD Master driven by **Gemini Omni 1.2 Flash** (November 2026 flagship). Uses **🍌 Nano Banana 2.1** (0-Credit Free Image Model) to generate character Hero DNA plates upfront and feeds them as `first_frame` into Omni 1.2 Flash, completely preventing AI facial morphing.

3. **Universal Omni Flash Prompting Standard & Sanitizer:**
   - **Syntax Order:** `[Subject & Distinct Features] + [Action / Physical Physics] + [Setting / Environment] + [Camera & Movement Vector] + [Lighting & Atmosphere]`.
   - **Sanitizer Gateway (`sanitize_omni_flash_prompt`):** Strips keyword stuffing that degrades Omni Flash latent space (`"hyperrealistic"`, `"4k photorealistic"`, `"trending on artstation"`, `"unreal engine 5"`, `"octane render"`). Enforces authentic physical/optical camera grammar (`dolly zoom`, `locked off`, `macro grip`, `anamorphic lens flare`, `35mm`).
   - **Unbroken Take Lock:** Automatically appends `"one continuous shot, a single unbroken take"` to prevent Omni Flash from making unwanted sub-clip cuts.
   - **First-Frame Persistence Directive:** When conditioning with `first_frame`, enforces `"Using the provided image reference as the starting frame, keep facial geometry, wardrobe, and physical attributes strictly identical."`

4. **Screenwriter Pacing Authority & Duration Packer Native Preservation:**
   - **Screenwriter (Grok 4.6 / Universal Narrative) is the primary authority on shot duration:**
     - Fast action, pursuit, sudden breaches, kinetic shock: **`duration: 4.0`**.
     - Dialogue, internal monologue, dread, survival preparation, environmental exploration: **`duration: 8.0`** (leveraging Omni 1.2 Flash native 8s coherence).
     - Radar, maps, tactical HUD, resource depletion counters: **`is_data_broll: true`** (Remotion 60 FPS B-roll, 0 Flow credits).
   - **Duration Packer Native Preservation:** The legacy artificial `5.2s` ceiling is removed; `duration_packer.py` preserves 4s and 8s native tiers directly without unwanted slicing.

5. **No Orphan Image Generations:**
   - If an agent generates Character Hero Plates (e.g. using `image-generator` or Nano Banana 2.1), it MUST:
     a) Save them into the `characters/` folder (e.g. `characters/captain_cole_vance_hero.jpg`).
     b) Link them as reference plates in the project's handoff packet (`sequences/<slug>_handoff.json`).
     c) Feed them directly into `produce-film` as `first_frame` anchor for Google Flow video generation.
   - Never generate images and leave them abandoned in the chat artifact directory without connecting them to the video production pipeline.

6. **Chrome CDP (Port 9223) & Gemini WebAPI (Port 8085) Execution Protocol:**
   - Chrome CDP must run on port `9223` with isolated profile `%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile`.
   - Always launch via dedicated launcher or script (`chrome_flow.bat`).
   - ZERO ad-hoc probing: Never write scratch probing scripts against ports 9223/8085; use direct CLI execution.
