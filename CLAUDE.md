# CLAUDE.md - Grok Imagine Cinematic Studio v3.11.4
# Anthropic Claude Code (CLI & Desktop) Operational Guide

> **Project Identity:** Independent community cinematic production framework for advanced Grok 4.5/4.6 multi-agent orchestration, Google Flow CDP video rendering, voice synthesis, Remotion motion graphics, and procedural foley pipelines. Not affiliated with or endorsed by xAI.

---

## 1. Core Directives & Critical Invariants (Read First)

### ⚠️ Invariant 1: ZERO Ad-Hoc Probing & No Forensic Rabbit Holes
- **STRICTLY FORBIDDEN:** Do NOT write scratch probe scripts (`test_gemini.py`, `check_api.py`, `test_port.py`), run network socket scanners, or manually inspect Chrome CDP (port 9223), local proxy (port 8085), or cookie state.
- **MANDATORY EXECUTION PATH:** Always execute production directly via the canonical CLI:
  ```bash
  python tools/cinematic_studio_cli.py produce-film "Title" --genre "..." --duration <sec> --plan-only
  ```
- The underlying engine handles all health checks, server lifecycles, and cookie rotation internally. Wasting turns probing infrastructure violates workspace invariants.
- When comparing with past handoffs, read the handoff file directly and run the CLI; never try to "re-verify" historical server states.

### 🎥 Invariant 2: Physical Render Engine is Google Flow CDP
- In this repository, **"Flow"** refers exclusively to the **Google Flow CDP (Port 9223) + Deepgram Aura-2 / Voyslity / ElevenLabs + FFmpeg** physical production factory located in `engine/` (`flow_bridge.py`, `editor.py`).
- **NEVER** confuse "Flow" with ComfyUI or standalone Grok Imagine web prompts.
- **No Orphan Image Generations:** If character hero plates or concept art are generated, never leave them abandoned in chat artifacts. Always save them to `characters/<character_slug>_hero.jpg` and reference them in `sequences/<project>_handoff.json` for Google Flow CDP.

### 🛡️ Invariant 3: Pure Engine & Zero Hardcode Standard
- **Python Engines (`engine/`, `tools/`):** MUST NEVER hardcode creative narrative text, visual styles, camera instructions, scene lines, or word substitution dictionaries (e.g. `{"needle": "sensor"}`). Engines are strictly pure execution pipelines (I/O, formatting, schema enforcement, API calls, FFmpeg/Remotion execution).
- **Skill Files (`.grok/skills/*.md`):** MUST NEVER contain hardcoded scene lines, synthetic dialogues, or literal Call-to-Action (CTA) sentences (e.g. literal *"You must subscribe..."*). All skill intelligence consists exclusively of **universal directing principles, thermodynamic/physical laws, and structural/formal storytelling constraints**. CTAs are structural constraints (strict 2nd-person POV, terminal sentence of Scene 38, zero preceding mention, model-generated per scenario).
- **Motion Graphics & Remotion Templates:** React components must be 100% parametric (`props`). Absolutely zero hardcoded city coordinates, telemetry values, event counts, or headlines inside TSX/JSX components. All values are driven dynamically via JSON payloads.
- **No Engine Overrides:** Python code may never override, hard-wrap, or shadow directives defined in markdown skill files or reference guides.

### 🎬 Invariant 4: Viral Second-Person & Foley Standard (Protocol v4.0)
- **100% English Invariant:** Every script beat, spoken voiceover, subtitle caption, and alignment dictionary must run exclusively in English (`en` / `en-US`). Zero Turkish or mixed-language text.
- **Second-Person Singular POV ("You"):** Strict 2nd-person singular perspective with an immediate in-media-res crisis hook within the first 3 seconds. 3rd-person narrator is strictly prohibited.
- **Micro-Survival Mathematics:** Include concrete, tangible resource tracking (water in ml, calories, decibel thresholds, battery %, duct tape barricade layers).
- **Spoken Text Sanitizer Gateway:** All narration text must pass through `engine/services/text_sanitizer.py` to strip metadata ("Act 1:", "Scene 02:") and bracketed directives (`[Sound of sirens]`, `(whispering)`).
- **Atmospheric / Situational Framing:** Prioritize door peephole POV, macro tool grips, battery LEDs, and backlit rain silhouettes to eliminate uncanny-valley AI facial defects.
- **Dual-Stage SFX & Procedural Foley:** Primary Hugging Face Space (`fffiloni/audiogen`, `declare-lab/TangoFlux`) with automatic fallback to local FFmpeg Lavfi synthetic foley (whoosh, sub-bass thud, tension heartbeat, wind drone).
- **Transition Boundary Triplet QA:** Gemini 2.5 Flash / OpenCV evaluates cross-block continuity `[Hero DNA] | [Block N Exit] | [Block N+1 Entry]` with 1x corrective re-roll on score < 0.85.
- Specification reference: `references/agents/VIRAL_SECOND_PERSON_RETENTION_FOLEY_PROTOCOL_v4.0.md`.

### 🪟 Invariant 5: Windows File Editing & Terminal Execution
- **Host OS is Windows (PowerShell):**
  - **Terminal / Pytest:** ALWAYS run pytest via `python -m pytest` (bare `pytest` is not on the Windows PATH).
  - **File Editing Tools (`Edit`, `str_replace`):** Beware of CRLF (`\r\n`) vs LF (`\n`) mismatches and 4 vs 8 vs 12 space indentations.
  - If a string replacement fails with "String to replace not found", immediately view the target lines with exact whitespace or rewrite the module section cleanly rather than repeating failed edits.

---

## 2. Skills & Agent Architecture (Never Reinvent Wheels)

This workspace contains **64 specialized production skills** in `.grok/skills/` and comprehensive agent role definitions in `references/agents/AGENT_INDEX.md`.

> **Mandatory Rule:** Claude MUST consult and leverage existing skills and role cards whenever performing directing, cinematography, character DNA extraction, sound/foley design, sequence extending, or quality assurance tasks. DO NOT reinvent ad-hoc guidelines.

### Core Department Agent Directory (Slugs)
| Department / Role | Skill Slug (Activate / Read) | Primary Focus |
|---|---|---|
| **Studio Director** | `studio-director` | Multi-agent orchestration, department handoffs, executive pacing |
| **Mega Production Architect** | `mega-production-architect` | Full-stack production bible architecture, budget & pipeline locks |
| **Director of Photography** | `director-of-photography` | Lighting, lenses, optics, volumetric atmosphere, camera movement |
| **Production Designer** | `production-designer-set-decorator` | Environmental architecture, wear-and-tear, physical props, tactile dressing |
| **Character DNA Extractor** | `character-dna-extractor` | Visual DNA prompt formulas, facial landmarks, wardrobe locking |
| **Identity Lock Specialist** | `identity-lock-specialist` | Identity continuity protocol, face anchor drift gates |
| **Performance & Emotion** | `performance-emotion-director` | Micro-expressions, vocal strain, somatic distress, eye saccades |
| **Sequence Director** | `sequence-director` | Multi-shot continuity, temporal coherence, shot transitions |
| **Cinematic Sequence Extender** | `cinematic-sequence-extender` | Video extension prompt chaining, drift prevention |
| **Sonic Architect** | `sonic-architect-native-audio-virtuoso` | Soundscape design, dynamic range, audio momentum |
| **Foley Specialist** | `foley-sound-design-specialist` | Dual-stage foley, Lavfi synthetic sound design, physical impacts |
| **Quality Assurance Guardian** | `quality-assurance-guardian` | Adversarial script linting, drift detection, AUP safety validation |
| **Color Grading Supervisor** | `post-production-color-grading-supervisor` | LUTs, film stock emulation, contrast ratios, gamut safety |
| **AI Polish Director** | `ai-polish-director` | Final pass editorial refinement, cadence polish, visual grading |
| **Grok Doctor** | `grok-doctor` | System diagnostic integrity, environment & tool validation |

*Full index and specialized agents (NSFW, Animatic, VFX, Subtitle, etc.):* Consult `references/agents/AGENT_INDEX.md`.

---

## 3. Essential CLI & Production Commands

All operations center around `tools/cinematic_studio_cli.py` (aliased as `cinematic-studio`):

### Film Production Pipeline (`produce-film`)
```bash
# 1. Zero-Cost / Plan-Only Mode (Generates screenplay, prompts, DNA, and sequence plan without rendering)
python tools/cinematic_studio_cli.py produce-film "Title" --genre "Sci-Fi Horror" --duration 60 --plan-only

# 2. Dry-Run Simulation (Simulates full pipeline execution without API calls)
python tools/cinematic_studio_cli.py produce-film "Title" --genre "Sci-Fi Horror" --duration 60 --dry-run

# 3. Full Physical Render (Google Flow CDP + Deepgram / Voyslity / ElevenLabs + FFmpeg)
python tools/cinematic_studio_cli.py produce-film "Title" --genre "Sci-Fi Horror" --duration 60 --voice-provider deepgram
```

### System Diagnostics & Model Registry
```bash
# Run system doctor diagnostics
python tools/cinematic_studio_cli.py doctor

# List registered models and aliases
python tools/cinematic_studio_cli.py models list

# Verify model registry connections
python tools/cinematic_studio_cli.py models verify
```

### Testing & Surface Verification
```bash
# Run surface smoke test script
python scripts/smoke_studio_surfaces.py

# IMPORTANT on Windows: Always run pytest via 'python -m pytest' (bare pytest is not in Windows PATH)
python -m pytest tests/

# Run specific targeted test suites
python -m pytest tests/test_engine_hardening.py
python -m pytest tests/test_universal_cinematic_engine.py
python -m pytest tests/test_phase6_youtube_multiplexer.py
python -m pytest tests/test_phase7_adversarial_heal.py
python -m pytest tests/test_video_qa_core.py
```

---

## 4. Model Layer & Multi-Surface Control Plane

### Grok 4.6 Registry Defaults
- **Stack Lock Default:** `grok-4.6` (used for Production Bible `model_stack`, Build CLI, and multi-agent coordination).
- **1M Long-Context Opt-in:** `grok-4.3` (`--chat-model grok-4.3` or alias `long-context`) used only for massive context memory banks (>400k tokens).
- **Specialist Routing:**
  - Multi-agent orchestration, handoffs, sequence chains: `grok-4.6` (Chat **Heavy**, `reasoning="high"`).
  - Specialist craft (DNA, cinematography, audio, QA): `grok-4.6` (Chat **Expert**, `reasoning="high"`).
  - Drafts, animatics, quota-sensitive routing: `grok-4-auto` (`reasoning="medium"`).
- **Video & Image Models:**
  - Video: `grok-imagine-video` (1.0 default) / `grok-imagine-video-1.5` (audio/r2v/1080p).
  - Image: `grok-imagine-image-2.0` (hero plates / quality mode) / `grok-imagine-image` (draft).

### Multi-Surface Architecture (`studio_core`)
All operator surfaces share `studio_core/services/` (`dashboard.py`, `actions.py`, `execute.py`):
- **CLI:** `python tools/cinematic_studio_cli.py`
- **TUI (Textual):** `cinematic-studio ui` (or `cinematic-studio ui --print` for non-TTY)
- **Streamlit:** `streamlit run web_ui/app.py` (web dashboard, batch generation, PDF tools)
- **NiceGUI:** `cinematic-studio web --host 127.0.0.1 --port 8088` (browser cockpit)
- **FastAPI Control Plane:** `cinematic-studio api --host 127.0.0.1 --port 8090` (API & OpenAPI docs)
- **React SPA:** `cinematic-studio web-react` (TanStack SPA on FastAPI at http://127.0.0.1:5173)

---

## 5. Repository File Structure & Output Conventions

```
<repo-root>/
├── .grok/
│   └── skills/                  # 64 Specialized production skills (one directory per skill)
├── engine/                      # Google Flow CDP, FFmpeg editor, TTS voice engines, motion graphics
│   ├── flow_bridge.py           # Google Flow CDP (Port 9223) browser driver
│   ├── editor.py                # FFmpeg assembly & timeline concatenation
│   ├── services/
│   │   └── text_sanitizer.py    # Spoken narration cleaner (strips scene headers & stage directions)
│   └── motion_graphics/         # Remotion TSX parametric components
├── tools/                       # CLI toolchain & model registry (models.py)
├── studio_core/                 # Shared UI-agnostic services (dashboard, ActionSpec, execute)
├── references/
│   ├── agents/                  # Role cards & protocols (AGENT_INDEX.md, Protocol v4.0)
│   └── MODELS_v3.6.md           # Model specifications & pricing
├── web_ui/                      # Streamlit dashboard
├── web_nicegui/                 # NiceGUI control cockpit
├── web_react/                   # React SPA
├── studio_api/                  # FastAPI REST backend
├── characters/                  # Character DNA sheets & hero plates (<slug>_hero.jpg)
├── sequences/                   # Sequence handoff packets (<project>_handoff.json)
└── tests/                       # Pytest automated test suite
```

### Output File Invariants:
- All character hero plates go to `characters/<character_slug>_hero.jpg`.
- All sequence handoff packets go to `sequences/<project>_handoff.json`.
- All generated audio files go to `artifacts/audio/` or project build directories.
- All final film renders are assembled via `engine/editor.py` into `artifacts/`.
