# AGENTS.md



**This file provides context and operational instructions for AI coding agents and assistants working in this workspace.**



**Version:** Hyper Maker Cinematic Studio **v4.6** (Procedural Catastrophe & Micro-Survival Documentary Factory; pinned to Grok 4.6 Studio Brain × Google Flow CDP Veo 3.1 physical video generation × Remotion 60 FPS Parametric Motion Graphics × Deepgram Aura-2 Voiceover × FFmpeg 7.0 Broadcast Master).  

**Canonical Source:** https://github.com/hyper-maker-app/youtube / https://github.com/FineComputer14451/Grok-Imagine-Cinematic-Studio/blob/main/AGENTS.md



> [!IMPORTANT]

> **MANDATORY PRODUCTION ENGINE INVARIANT (NOT AN XAI-ONLY IMAGINE PROMPT REPO):**  

> External LLMs, coding agents, and assistants MUST NOT confuse this repository with a standalone xAI Imagine prompt library or text-to-image chatbot.  

> 1. The **MANDATORY production engine** for generating films is `produce-film` via **Google Flow CDP (Port 9223) + Deepgram Aura-2 + Remotion 60 FPS Parametric Motion Graphics + FFmpeg 7.0 Broadcast Master**.

> 2. Direct CLI production invocation: `python tools/cinematic_studio_cli.py produce-film "Title" --genre "..." --duration <sec>`

> 3. Standalone xAI Imagine 1.0/1.5/2.0 references are strictly **archived / secondary legacy modalities** (for concept drafting) and must never be prioritized over the active `produce-film` Flow CDP pipeline.



> [!NOTE]

> **Hyper Maker Cinematic Studio** (formerly Grok Imagine Cinematic Studio) is an **independent community project**. It is **not affiliated with, endorsed by, sponsored by, or officially connected to xAI or Google**. Agents must not claim official partnership. Full notice: `DISCLAIMER.md`.



Think of this as the single source of truth for how to interact with this studio agent environment. Paths below are **repo-relative** unless noted; sandboxes may root at `/home/workdir/` or a local clone (e.g. `~/Grok-Imagine-Cinematic-Studio`).



**Version legend (read once):**



| Stamp | Meaning |

|-------|---------|

| **Studio v4.6 (Hyper Maker)** | Current production factory version — use this for all production and code execution |

| **Model Layer v4.5** | Canonical chat + specialist routing (`MODEL_LAYER_v4.5.md`) |

| **Feature history (3.7.1 / 3.11.4)** | Historical releases when capabilities landed (e.g. Handoff in 3.7.1, 4.6 stack in 3.11.4) |

| **Role Card labels (v3.6.5–v4.5)** | Per-card revision tags; AGENT_INDEX is authoritative |



## Workspace Overview



This workspace is an autonomous, end-to-end film factory engineered for **v4.6 Hyper Maker Catastrophe & Survival Cinema**, with heavy emphasis on:



- **Autonomous Physical Film Production:** End-to-end multi-agent pipeline (`tools/cinematic_studio_cli.py produce-film`) driving Google Flow CDP (Veo 3.1) and Remotion 60 FPS motion graphics.

- **Multi-Agent Direction & Timeline Escalation:** 5-stage catastrophe escalation (`catastrophe-director`, `deepsea-survival-director`, `planetary-catastrophe-director`, `urban-infiltration-director`, `micro-survival-director`).

- **Adversarial Dual-Judge Quality Gate:** Fail-closed screenplay certification by Grok 4.6 (viral audience retention) × Gemini 3.1 Pro (spatial/physics verification) with $\ge 90.0$ score threshold.

- **Parametric Remotion Motion Graphics (60 FPS):** Zero-hardcode React B-roll (storm radar maps, resource depletion curves, tactical HUDs).

- **Broadcast Audio Mastering:** Deepgram Aura-2 word-quantized TTS, dual-stage procedural foley synthesizers, and FFmpeg 7.0 broadcast mixing (-14 LUFS true peak, sidechain ducking).

- **Custom Skill Development & Orchestration:** Grok Build skills, plugins, and repository tooling.

- **Archived / Secondary Modality:** Legacy Grok Imagine 1.0/1.5/2.0 prompt generation and character handoffs (secondary fallback only).



**Core principle:** Use the appropriate skill or tool for every task. Do not reinvent wheels that skills already handle. Prefer existing skills over ad-hoc scripts. Prefer **skill directory slugs** (e.g. `studio-director`) over display titles when activating.



**Orchestration default (registry):** Multi-agent direction, Production Bibles, coding, and Grok Build sessions lock **`grok-4.6`** via `tools/models.py` unless the user or Studio Director opts into **`grok-4.3`** for 1M-context memory banks. `grok-4.5` aliases wrap 4.6.



**Specialist Model Layer (Role Cards / skills):** When 4.6 identifiers are available in the session, prefer them per `MODEL_LAYER_v4.5.md` — multi-agent → `grok-4.6` (Chat **Heavy**); specialist craft → `grok-4.6` (Chat **Expert**); draft/quota → `grok-4-auto`. Registry default remains **`grok-4.6`** for stack locks and Build CLI.



## MANDATORY PRODUCTION ENGINE: GOOGLE FLOW CDP & PRODUCE-FILM (CRITICAL)



> [!IMPORTANT]

> **PHYSICAL RENDER ENGINE IS GOOGLE FLOW CDP (NOT ORPHAN IMAGINE GENERATION)**:

> In this workspace, the term **"Flow"** refers exclusively to the **Google Flow CDP (Port 9223) + Deepgram Aura-2 / Voyslity / ElevenLabs + FFmpeg** physical production factory located in `engine/` (`flow_bridge.py`, `editor.py`).

>

> 1. **End-to-End Production Entry Point (3-Tier Production Architecture):** Always use `tools/cinematic_studio_cli.py produce-film`:

>    - **Tier 1 (Zero-Cost Draft & LLM Experiment Mode):** `python tools/cinematic_studio_cli.py produce-film "Title" --genre "..." --duration <sec> --plan-only` (or `--dry-run`). 0 Flow credits spent; generates certified screenplay, Deepgram Aura-2 voiceover, Remotion graphics, and color storyboard proxy cards.

>    - **Tier 2 (Rapid Test Validation Mode):** `python tools/cinematic_studio_cli.py produce-film "Title" --genre "..." --duration <sec> --test`. 360p low-cost validation (~30-40 credits for 60s). Pinned to **Omni 1.1 Flash** (360p / 4s = 4 credits) until December 5, 2026; automatically falls through to **Veo 3.1 - Lite** (10 credits) after December 5, 2026.

>    - **Tier 3 (Broadcast Cinematic Master Mode):** `python tools/cinematic_studio_cli.py produce-film "Title" --genre "..." --duration <sec> --real`. 720p HD Master driven by **Gemini Omni 1.2 Flash** (November 2026 flagship). Uses **🍌 Nano Banana 2.1** (0-Credit Free Image Model) to generate character Hero DNA plates upfront and feeds them as `first_frame` into Omni 1.2 Flash, completely preventing AI facial morphing.

> 2. **Universal Omni Flash Prompting Standard & Sanitizer:**

>    - **Syntax Order:** `[Subject & Distinct Features] + [Action / Physical Physics] + [Setting / Environment] + [Camera & Movement Vector] + [Lighting & Atmosphere]`.

>    - **Sanitizer Gateway (`sanitize_omni_flash_prompt`):** Strips keyword stuffing that degrades Omni Flash latent space (`"hyperrealistic"`, `"4k photorealistic"`, `"trending on artstation"`, `"unreal engine 5"`, `"octane render"`). Enforces authentic physical/optical camera grammar (`dolly zoom`, `locked off`, `macro grip`, `anamorphic lens flare`, `35mm`).

>    - **Unbroken Take Lock:** Automatically appends `"one continuous shot, a single unbroken take"` to prevent Omni Flash from making unwanted sub-clip cuts.

>    - **First-Frame Persistence Directive:** When conditioning with `first_frame`, enforces `"Using the provided image reference as the starting frame, keep facial geometry, wardrobe, and physical attributes strictly identical."`

> 3. **Screenwriter Pacing Authority & Duration Packer Native Preservation:**

>    - **Screenwriter (Grok 4.6 / Universal Narrative) is the primary authority on shot duration:**

>      - Fast action, pursuit, sudden breaches, kinetic shock: **`duration: 4.0`**.

>      - Dialogue, internal monologue, dread, survival preparation, environmental exploration: **`duration: 8.0`** (leveraging Omni 1.2 Flash native 8s coherence).

>      - Radar, maps, tactical HUD, resource depletion counters: **`is_data_broll: true`** (Remotion 60 FPS B-roll, 0 Flow credits).

>    - **Duration Packer Native Preservation:** The legacy artificial `5.2s` ceiling is removed; `duration_packer.py` preserves 4s and 8s native tiers directly without unwanted slicing.

> 4. **v4.0 Viral Second-Person & Foley Standard (Protocol v4.0):**

>    - **100% English Invariant:** Every script beat, spoken voiceover, subtitle caption, and alignment dictionary must run exclusively in English (`en` / `en-US`). Zero Turkish text.

>    - **Second-Person POV ("You"):** Strict 2nd-person singular perspective with in-media-res crisis hook within the first 3 seconds. 3rd-person narrator is strictly forbidden.

>    - **Micro-Survival Mathematics:** Concrete tangible resources (water ml, calories, decibel thresholds, battery %, duct tape barricade layers).

>    - **Spoken Text Sanitizer Gateway:** All narration text must pass through `engine/services/text_sanitizer.py` to strip metadata ("Act 1:", "Scene 02:") and bracketed directives (`[Sound of sirens]`, `(whispering)`).

>    - **Atmospheric / Situational Framing:** Prioritize door peephole POV, macro tool grips, battery LEDs, and backlit rain silhouettes to eliminate uncanny-valley AI facial defects.

>    - **Dual-Stage SFX & Procedural Foley:** Primary Hugging Face Space (`fffiloni/audiogen`, `declare-lab/TangoFlux`) with automatic fallback to local FFmpeg Lavfi synthetic foley (whoosh, sub-bass thud, tension heartbeat, wind drone).

>    - **Transition Boundary Triplet QA:** Gemini 2.5 Flash / OpenCV evaluates cross-block continuity `[Hero DNA] | [Block N Exit] | [Block N+1 Entry]` with 1x corrective re-roll on score < 0.85.

>    - Full specification: `references/agents/VIRAL_SECOND_PERSON_RETENTION_FOLEY_PROTOCOL_v4.0.md`.

> 3. **No Orphan Image Generations:** If character hero plates or concept art are generated, DO NOT leave them abandoned in chat artifacts. They MUST be saved into `characters/<character_slug>_hero.jpg` and linked into `sequences/<project>_handoff.json` as visual references for Google Flow CDP.

> 4. **Never Confuse "Flow":** When the user asks to produce via "Flow", they mean the Google Flow CDP factory (`engine/flow_bridge.py`), NEVER generic ComfyUI or standalone Grok Imagine web prompts.

> 5. **ZERO AD-HOC PROBING & NO FORENSIC RABBIT HOLES (CRITICAL):**

>    - When the user asks to write a screenplay, generate a test scenario, run adversarial review, or compare with a previous run/handoff:

>      - **STRICTLY FORBIDDEN:** Writing ad-hoc scratch scripts (`test_gemini.py`, `check_api.py`, etc.) to probe background servers, sockets, Chrome CDP (port 9223), local proxy (port 8085), or inspect cookies.

>      - **MANDATORY DIRECT EXECUTION:** Always directly execute the CLI command: `python tools/cinematic_studio_cli.py produce-film "Title" --genre "..." --duration <sec> --plan-only`.

>      - The engine handles all health checks, server lifecycles, and cookie rotations internally. Agents that waste turns probing infrastructure instead of executing the CLI are violating this invariant.

>      - When asked to compare with a previous conversation's handoff, simply read that handoff, run the new run via CLI, and compare the two outputs. Never attempt to "re-verify" past server conditions.



## MANDATORY MULTI-AGENT SUBAGENT DELEGATION & REVIEW PROTOCOL (CRITICAL)



> [!IMPORTANT]

> **SUBAGENT DELEGATION, INDEPENDENT AUDIT & LEAD VERIFICATION PIPELINE**:

> When executing any engineering plan, feature integration, or multi-step technical implementation in this workspace:

> 1. **Modular Workstream Decomposition:** The main agent MUST break down the implementation plan into distinct, modular parts.

> 2. **Dedicated Specialized Subagents:** Each part MUST be dispatched to a separate, specialized subagent (`invoke_subagent`) focused strictly on its domain (e.g. Skill Specialist, Engine/API Specialist, Remotion Motion Graphics Specialist, Flow CDP/Editor Pipeline Specialist).

> 3. **Independent Auditor / QA Subagent Review (Mandatory):** After all implementation subagents complete their assigned parts, an independent **Auditor / QA Reviewer Subagent** MUST be invoked to inspect all changed files, verify zero-hardcode compliance, run automated tests (`pytest`, `npm test`, CLI tests), and actively fix any defects or regressions.

> 4. **Mandatory Multi-IDE Rules & Governance Synchronization (CRITICAL):** Agents MUST NEVER stop at Python engines and unit tests. Every architectural, CLI, model, or workflow change MUST synchronously update all agent governance and IDE rule directories:
>    - `.gemini/rules/` (for Gemini & Antigravity)
>    - `.cursor/rules/` (for Cursor IDE)
>    - `.grok/skills/` (for Grok Build & runtime skill injection)
>    - `AGENTS.md`, `README.md`, and `references/MODELS.md`
>    The Independent QA Auditor MUST fail any audit if IDE and agent rule files are left outdated or out of sync with code changes.
> 5. **Lead Agent Final Sanity Check & User Presentation:** Only after the Auditor Subagent confirms a clean pass does the Main Lead Agent perform the final verification, end-to-end sanity checks, and present the final results clearly to the user.



## PURE ENGINE & SKILL INVARIANT: ABSOLUTE ZERO HARDCODE (CRITICAL)



> [!IMPORTANT]

> **ABSOLUTE ZERO HARDCODE ACROSS ENGINES, SKILLS, TEMPLATES & COMPONENTS**:

> 1. **Python Engines (`engine/`, `tools/`):** Python engines MUST NEVER hardcode creative narrative text, visual styles, camera instructions, scene lines, or word substitution dictionaries (e.g. `{"needle": "sensor"}`). Engines are strictly pure execution pipelines (I/O, formatting, schema enforcement, API calls, FFmpeg/Remotion execution).

> 2. **Skill Files (`.grok/skills/*.md`):** Skills MUST NEVER contain hardcoded scene lines, artificial dialogues, or literal, word-for-word Call-to-Action (CTA) sentences (e.g. literal *"You must subscribe to the channel now..."*). All intelligence in skills must consist exclusively of **universal directing principles, thermodynamic/physical laws, and structural/formal storytelling constraints**. CTA rules must be enforced as structural criteria (e.g. strict 2nd-person POV, terminal sentence of Scene 38, zero preceding mention, model-generated per scenario).

> 3. **Motion Graphics & Remotion Templates:** React components must be 100% parametric (`props`). Absolutely zero hardcoded city coordinates, telemetry values, event counts, or headlines inside TSX/JSX components. All values must be driven dynamically by JSON payloads.

> 4. **Nothing Overrides Skills:** No Python code may override, hard-wrap, or shadow directives defined in the Markdown skill files or reference guides.



## Directory Structure



```

<repo-root>/

├── .grok/

│   └── skills/                  # Project skills (one per subdirectory)

│       ├── <skill-name>/

│       │   ├── SKILL.md         # Required: YAML frontmatter + imperative instructions

│       │   ├── scripts/         # Optional: executable helpers

│       │   ├── references/      # Optional: long-form docs, production bibles, agent defs

│       │   └── assets/          # Optional: templates, reference images, etc.

├── .grok-plugin/                # Marketplace multi-plugin (full suite + 5 packs), plugin.json, plugin-index.json, packs/

├── artifacts/                   # Generated outputs (gitignored contents; keep .gitkeep)

├── scripts/                     # Install/verify/update helpers + thin shims

├── studio_core/                 # UI-agnostic services (dashboard · ActionSpec · execute_action)

├── tools/                       # CLI + model registry (models.py is canonical stack)

├── references/                  # MODELS.md · MODELS_v3.6.md · agents/ Role Cards

├── docs/                        # Human docs: guides/, templates/, releases/, archive/

├── commands/                    # Slash commands for Grok Build plugin

├── characters/ · sequences/     # Runtime DNA / sequence state (gitignored contents)

├── sfw_batches/ · nsfw_batches/ # Runtime batch plans (gitignored contents)

├── AGENTS.md                    # This file (you are here)

├── README.md · MASTER_PROMPT.md # Overview + chat activation (Grok 4.5)

├── CHANGELOG.md · VERSION

└── (other: config/, examples/, tests/, assets/)

```



Full map: `docs/REPOSITORY_LAYOUT.md`. Retired web surfaces: `docs/guides/WEB_SHELLS.md`.



User-global skills (all projects): `~/.grok/skills/`.  

User config: `~/.grok/config.toml`.



## Control Plane



The active operator surfaces are the CLI and TUI, backed by `studio_core`. Use `cinematic-studio ui` or `cinematic-studio ui --print`; extend shared services rather than creating a parallel registry. The former Streamlit, NiceGUI, React and FastAPI surfaces are retired. Their `web`, `web-react` and `api` commands exit with a migration notice and status 1. Run `python scripts/smoke_studio_surfaces.py` for an offline smoke check.



## Grok 4.6 Model Layer (Required Knowledge)



Canonical registry: `tools/models.py` · `references/MODELS_v3.6.md` · **`references/agents/MODEL_LAYER_v4.5.md`** (v4.5.1).  

Legacy archive only: `references/agents/MODEL_LAYER_v3.7.1.md` (do not use for new work).  

Agent slug / Role Card map: `references/agents/AGENT_INDEX.md`.



Verify:



```bash

python tools/cinematic_studio_cli.py models list

python tools/cinematic_studio_cli.py models verify

```



### Registry defaults (stack lock / Build / Bible)



| Layer | Default Slug | When to Use |

|-------|--------------|-------------|

| **Orchestration (registry default)** | `grok-4.6` | Production Bible `model_stack`, multi-agent direction lock, agent loops |

| **Long-context (opt-in)** | `grok-4.3` | 1M memory banks only — `--chat-model grok-4.3` or alias `long-context` |

| **Grok Build CLI** | `grok-4.6` | Default agent (coding / agentic); min CLI **1.0.5** |

| **Grok Build fork** | `grok-build` | Code, skills, repo tooling (`fork_secondary_model`) |

| **xAI Build / coding API** | `grok-4.6` | Agentic automation (legacy: `grok-build-0.1`) |

| **Creative fast (optional)** | `grok-composer-2.5-fast` | Fast multi-agent cinematic direction in Build picker |

| **Primary Video Engine (Physical)** | **Google Flow CDP (Omni 1.2 Flash / Veo 3.1)** | Port 9223 Chromium CDP. Flagship: Gemini Omni 1.2 Flash (720p). Test: Omni 1.1 Flash (360p until Dec 5, 2026) -> Veo 3.1 Lite. Discrete 4s/6s/8s/10s native tiers via `produce-film` |

| **0-Credit Hero Frame Engine** | **🍌 Nano Banana 2.1** | 0 Flow Credits (Free). Generates character Hero DNA plates passed as `first_frame` into Omni 1.2 Flash |

| **Motion Graphics Engine** | **Remotion 60 FPS** | Parametric React B-roll (storm maps, telemetry HUDs) via `engine/services/remotion_bridge.py` |

| **Voiceover Synthesis** | **Deepgram Aura-2** | Timed word-level timestamps, with ElevenLabs / Azure TTS support |

| **Archived / Secondary Video** | `grok-imagine-video` (1.0 / 1.5) | Legacy secondary fallback; $0.05/sec 480p / 1080p. **No video 2.0** |

| **Archived / Secondary Image** | `grok-imagine-image` · `grok-imagine-image-2.0` | Secondary hero plate / concept art drafting only; Image 2.0 1K low $0.04 / medium $0.06 |



**Aliases:** `cinematic` / `build` / `coding` / `4.5` / `grok-4.5` / `grok-4.5-latest` / `grok-build-latest` / `4.6` → **`grok-4.6`**.  

**1M aliases:** `long-context` / `4.3` / `grok-4` → **`grok-4.3`**.



### Specialist Model Layer (v4.5 dual-model wave)



When the session exposes these identifiers, **prefer them for Role Card work** (skills already embed this table). Registry default for Bibles/Build remains **`grok-4.6`**.



| Task type | Preferred model | Reasoning |

|-----------|-----------------|-----------|

| Multi-agent orchestration, handoffs, sequence chains | `grok-4.6` (Chat **Heavy**) | high |

| Specialist craft (DNA, prompts, QA, DoP, Sonic, ErosForge) | `grok-4.6` (Chat **Expert**) | high |

| Draft / animatic / quota-sensitive / routine routing | `grok-4-auto` | medium |



**Chat modes:** Auto / Fast / Expert / Heavy / Build. API and Build default: `grok-4.6`.



### Grok 4.6 operating rules



1. **Lock the stack** to `grok-4.6` (registry) unless the user or Studio Director needs 1M context (`grok-4.3`).

2. **Route specialists** with Model Layer v4.5 when 4.6 / `grok-4-auto` are available; fall back to `grok-4.6` when they are not.

3. **Reasoning:** prefer **high** for Bibles, QA, Identity Lock, Sequence Director; **medium** for routine prompt drafts; **low** only for trivial routing. Grok 4.6 defaults to high.

4. **Prompt cache:** use a stable `prompt_cache_key` per production (project slug) on multi-turn agent loops to reduce cost.

5. **Do not** treat Imagine models as chat models — video/image spend is `grok-imagine-*` only.

6. Every Production Bible must lock `model_stack` + `VIDEO_PIPELINE_SPEC` from the registry helpers (`build_video_pipeline_spec` in `tools/models.py`).

7. Opt into `grok-4.3` only when memory banks / long chains exceed ~400k effective context.

8. Do **not** treat CLI version `1.0.5` as an API model slug — it is the **Grok Build binary** version.

9. **Identity Continuity:** apply `references/agents/IDENTITY_CONTINUITY_PROTOCOL_v3.8.md` on multi-clip character work (drift gates before extend/stitch spend).

10. **Plate & motion readiness:** before video spend, prefer locked plates + motion briefs (`plate_status`, `motion_vector`; CLI gates `--strict-plate`, `--strict-motion`, `--strict-handoff` when enforcing).



Local config (`~/.grok/config.toml`) — see `config/grok-build.example.toml`:



```toml

[models]

default = "grok-4.6"



[ui]

fork_secondary_model = "grok-build"

```



CLI note (1.0.5+): **Esc no longer cancels a turn** — use **Ctrl+C**. Double-Esc rewind works while focused on scrollback.



## Skill System Rules (Critical)



When working with or creating skills:



1. **Prefer studio skill creators** in this repo:

   - Project cinematic skills → `cinematic-skill-creator` (Role Card + validate conventions)

   - Generic Grok skills → `create-skill` (`~/.grok/skills/create-skill/SKILL.md` or `/create-skill`)

2. Every skill **must** have a `SKILL.md` with strict YAML frontmatter:

   - `name`: kebab-case, matches directory name exactly

   - `description`: single-line plain text (no colons, no `<`/`>`, max 1024 chars) describing **when to use** this skill

3. **Never** create `README.md`, `CHANGELOG.md`, or human-facing docs inside skill directories — skills are agent-only.

4. Keep `SKILL.md` concise (< ~500 lines). Move detailed content, agent personalities, production bibles, and long references to `references/`.

5. New **project** skills go in `.grok/skills/<name>/`. User-global skills go in `~/.grok/skills/<name>/`.

6. Studio skills should embed the **Model Layer (Grok 4.6)** block (see `references/agents/MODEL_LAYER_v4.5.md`).

7. Validate after creation / change: `bash scripts/verify_cinematic_studio.sh` (and skill-specific validators when available).



## Core Agent Skill Slugs



The historical **25 Role-Card core agent** roster does not imply every skill remains present; **58 present skill directories** power agents + specialists (i2i, batch, chain QA, polish, Wave A P0, packs, etc.). Full activation table: `references/agents/AGENT_INDEX.md`.



| Display name | Skill slug (activate this) |

|--------------|----------------------------|

| Studio Director | `studio-director` |

| Mega Production Architect | `mega-production-architect` |

| Director of Photography | `director-of-photography` |

| Production Designer | `production-designer-set-decorator` |

| Color Grading Supervisor | `post-production-color-grading-supervisor` |

| Character DNA Extractor (retired; skill absent) | `character-dna-extractor` |

| Performance & Emotion Director | `performance-emotion-director` |

| Identity Lock Specialist | `identity-lock-specialist` |

| Narrative Arc Pacing Strategist | `narrative-arc-pacing-strategist` |

| Sequence Director | `sequence-director` |

| Cinematic Sequence Extender | `cinematic-sequence-extender` |

| Continuity Guardian | `continuity-consistency-guardian` |

| Multi-Clip Continuity Orchestrator | `multi-clip-continuity-orchestrator` |

| Imagine Prompt Master | `imagine-prompt-master` |

| Quality Assurance Guardian | `quality-assurance-guardian` |

| Grok Doctor | `grok-doctor` |

| Workflow Quota Optimizer | `workflow-quota-optimizer` |

| Sonic Architect | `sonic-architect-native-audio-virtuoso` |

| Foley Specialist | `foley-sound-design-specialist` |

| Stunt Action Choreographer | `stunt-action-choreographer` |

| VFX & SFX Supervisor | `vfx-sfx-supervisor` |

| Key Art Designer | `key-art-poster-designer` |

| Trailer Director | `trailer-teaser-director` |

| Localization Specialist | `localization-subtitle-specialist` |

| AI Polish Director | `ai-polish-director` |



Core membership matches `tools/cli/shared.py` `CORE_AGENT_CATEGORIES` (includes Character DNA Extractor). **ErosForge NSFW Director** is opt-in, not in the 25.



**High-traffic specialists (not all are in the “25” core list):** `erosforge-nsfw-director` (explicit opt-in), `costume-wardrobe-continuity`, `multi-character-identity-arbiter`, `image-to-video-specialist`, `reference-asset-curator`, `animatic-director`, `assembly-editor`, `sfw-batch-orchestrator`, `nsfw-quota-orchestrator`, `nsfw-sequence-extender`, `chain-qa-protocol`, `nsfw-chain-qa-protocol`, `handoff-packet-validator`, `imagine-execution-bridge`, `ai-video-upscaler`, `cinematic-ffmpeg`, `i2i-refiner`, `i2i-cinematic-refiner`, `ai-image-recreation`, `arc-replan-copilot`, `quota-dashboard`, `production-bible-workflow`, `skill-agent-architect`, `cinematic-skill-creator`, `cinematic-studio-meta-installer`, `github-repo-manager`, `extend-frame-to-video`, `grok-imagine-cinematic-studio`.



**Wave A (P0 scaffold · 8 agents):** `plate-motion-readiness-lead`, `contact-micro-physics-specialist`, `hair-makeup-continuity`, `dialogue-adr-director`, `score-temp-music-supervisor`, `title-motion-graphics-lead`, `distribution-crop-strategist`, `parallel-brief-dispatcher` — Role Card + skill only; suite **64** skills after register.



## Common Workflows & Commands



### File Operations (Grok Build tools)



- Read: `read_file` (supports `offset` + `limit`)

- Write / create: `write`

- Edit in place: `search_replace`

- Explore: shell `ls`, `find`, `rg` / `grep` tool; prefer dedicated file tools over `cat` for large reads



### Archived / Secondary Modality: Image & Media Tasks (Legacy Grok Imagine)



> [!NOTE]

> **PRIMARY ENGINE IS PRODUCE-FILM VIA FLOW CDP**:  

> For active film production, always use `python tools/cinematic_studio_cli.py produce-film`. The tools below are reserved strictly for secondary asset drafting, concept art iteration, or legacy xAI Imagine workflows:



- **Generate new images (Concept / Hero Plates)**: `image_gen` (detailed prompt + aspect ratio) -> save hero plates to `characters/<slug>_hero.jpg`

- **Edit existing / generated images**: `image_edit` (prompt + reference image path or attachment)

- **Still → video (Legacy)**: `image_to_video` (when available in session)

- **Multi-ref → video (Legacy)**: `reference_to_video` (when available)

- **AI recreation / style transfer / enhancement** of uploaded images: Activate `ai-image-recreation`

- **Extend cinematic sequences (Legacy)**: Activate `cinematic-sequence-extender` or `extend-frame-to-video`

- **Refine / iterate on previously generated images**: `generated-image-editor` (user-global when present)

- **Upscale video for final delivery** (720p → 1080p/4K, face restoration): Activate `ai-video-upscaler`

- Video / audio processing: Activate `cinematic-ffmpeg` or use `ffmpeg` / bash

- **Secondary Planning → Imagine handoff**: Studio Director **Imagine Agent Mode Handoff** (see archived section below)



If native Imagine tools are unavailable and legacy execution is desired, use `imagine-execution-bridge` / CLI (`imagine submit`, `sfw run`, `sequence run`) with a locked `VIDEO_PIPELINE_SPEC`.



### Document Tasks



Document skills are typically **session / user-global** (not always in the 64-skill project suite). Use when available:



- PDF: `pdf` skill

- Word (.docx): `docx` skill

- PowerPoint (.pptx): `pptx` skill

- Excel (.xlsx): `xlsx` skill



### GitHub & Connected Services



- All GitHub operations: Activate `github-repo-manager` skill first (or GitHub MCP tools when connected)

- Discover connected / MCP services as available in the session; use schemas from tool discovery before calling



### Grok Build CLI binary + grok.com surfaces



- Manage the official Grok Build binary (min **1.0.5**): `cinematic-studio grok status|ensure|update|install`

- Method A meta installer ensures the binary and ships `tools/grok_build_cli.py` + `cli/grok_cli_commands.py`

- **Android / Termux / NetHunter / desktop shell:** `export PATH="$HOME/.grok/bin:$HOME/.local/bin:$PATH"`; Method A from a clone

- **grok.com chat:** no binary — `Activate Grok Imagine Cinematic Studio v3.11.4` or paste `MASTER_PROMPT.md`; Method A skills in `~/.grok/skills/` support chat ecosystems (skip declutter if you need both chat Method A + plugin)

- **grok.com/imagine:** surface `grok_com_imagine` — `imagine-execution-bridge` / `cinematic-studio imagine bridge` copy-paste packets

- **Grok mobile chat app:** same as grok.com (Activate / Imagine only); shell for CLI

- Meta path without wrapper: `bash scripts/cinematic_studio.sh grok ensure`



### Grok Plugins & Marketplace



- Install/update the full Cinematic Studio (recommended): `grok plugin install FineComputer14451/Grok-Imagine-Cinematic-Studio --trust`

- Or via marketplace: `grok plugin marketplace add FineComputer14451/Grok-Imagine-Cinematic-Studio` then install by name

- **Multi-plugin packs (v3.8.0):** marketplace lists **6 plugins** (full suite + 5 packs) from `config/plugin_packs.yaml`. Prefer full suite; list packs with `cinematic-studio plugin packs`. See `references/SKILLS_TAXONOMY.md` and install matrix in `docs/guides/installation_guide.md`.

- Regenerate index after skill changes: `cinematic-studio plugin catalog pin` (or `python scripts/generate_plugin_index.py` for plain generation only)

- Validate plugin: `bash scripts/verify_plugins.sh` (or `cinematic-studio plugin catalog check`)

- Declutter dual Method A+B skill installs: `bash scripts/cinematic_studio.sh declutter --apply` (or `cinematic-studio plugin declutter --apply`) — see `references/SKILLS_TAXONOMY.md`

- Declutter **full suite + satellite packs:** policy **`full_suite_wins`** keeps the full suite and removes satellite skill dupes

- Browse skill groups: `cinematic-studio plugin list --grouped`

- Release catalog pin: commit content first → `cinematic-studio plugin catalog pin` (or `bash scripts/release_plugin_catalog.sh`) → commit **only** `.grok-plugin/` (install SHA = content revision; pin-only tip is expected)

- Pre-publish plugin gate: `cinematic-studio plugin catalog check --release` or `bash scripts/verify_plugins.sh --release` (passes when pin == HEAD or pin is ancestor with only catalog paths after it)

- Dev/test deps: `pip install -r requirements-dev.txt` then `pytest`

- Use `cinematic-studio-meta-installer` skill for full bootstrap/verify in agent sessions

- The **available skills + slash commands** (in `commands/`) are the primary way to extend Grok Build with studio capabilities



### Memory & Personalization



- When the user shares personal facts, preferences, or life updates that may warrant remembering: Use the `memory-edit` skill (consult its SKILL.md).



### Render Components (Final Response Only)



Use these in the **final response** (never inside function calls), when the runtime supports them:



- Image render helpers for generated/edited/searched assets

- `render_inline_citation` (for web / X / collection results)

- File/download render helpers for local artifacts



## Cinematic Studio & Multi-Agent Workflows



For any complex visual storytelling, film-style image sequences, video production, or NSFW cinematic work:



**Primary activation command:**  

`Activate Grok Imagine Cinematic Studio v3.11.4` or `Start cinematic production`



The historical roster lists **25 specialized agents** (Role Cards labeled v3.6.5–v4.5 under studio **v3.11.4**; Studio Director owns **Imagine Agent Mode Handoff**) plus pipeline specialists and **Wave A** scaffolds. **58 present skill directories** implement the department. Core list (`CORE_AGENT_CATEGORIES` — DNA in, ErosForge opt-in):



- Studio Director (`studio-director`), Mega Production Architect (`mega-production-architect`)

- Director of Photography, Production Designer, Color Grading Supervisor

- Character DNA Extractor (`character-dna-extractor`, retired skill), Performance & Emotion Director, Identity Lock Specialist, Narrative Arc Pacing Strategist

- Sequence Director, Cinematic Sequence Extender, Continuity Guardian, Multi-Clip Continuity Orchestrator

- Imagine Prompt Master, Quality Assurance Guardian, **Grok Doctor** (`grok-doctor`), Workflow Quota Optimizer

- Sonic Architect, Foley Specialist

- Stunt Action Choreographer, VFX & SFX Supervisor

- Key Art Designer, Trailer Director, Localization Specialist

- **AI Polish Director** (`ai-polish-director`) — final post-production upscale & restoration



Opt-in NSFW (not in the 25): ErosForge NSFW Director (`erosforge-nsfw-director`) — only when explicitly activated.



Specialist activation patterns: cinematic studio skill references and **`references/agents/AGENT_INDEX.md`**.  

Model Layer for Role Cards: **`references/agents/MODEL_LAYER_v4.5.md`**.  

Identity Continuity: **`references/agents/IDENTITY_CONTINUITY_PROTOCOL_v3.8.md`**.  

**Parallel Brief Protocol:** Concurrent multi-agent coordination under MAXIMUM AGENTIC MODE. Canonical: `references/agents/Parallel_Brief_Protocol.md`. Studio Director issues Parallel Briefs; specialist outputs converge into validated `imagine_agent_mode_handoff` packets.



## Archived / Secondary: Imagine Agent Mode Handoff (Legacy Planning Bridge)



> [!NOTE]

> In v4.6 Hyper Maker, active productions execute directly through `tools/cinematic_studio_cli.py produce-film` to orchestrate Google Flow CDP, Remotion, and Deepgram. This section documents the legacy v3.7.1 Imagine Agent Mode Handoff protocol for backward compatibility with xAI-only prompt execution.



Studio Director routes planning → generation so pipeline context is never dropped.



| Surface | How generation runs |

|---------|---------------------|

| **A. Grok Build tools** | `image_gen` / `image_edit` / `image_to_video` / `reference_to_video` in session |

| **B. Grok agent mode (ACP)** | `grok agent` / IDE ACP — skills + shell + tools |

| **C. grok.com/imagine** | Manual paste (Execution Bridge packet); Quality Mode = Image 2.0 |

| **D. xAI Imagine API** | `imagine submit` / `sfw run` / `sequence run` with `XAI_API_KEY` |

| **E. Responses `image_generation`** | Server-side tool (Image 2.0 stills); `target_surface: xai_responses_tool` |



**Activation:** `ACTIVATE IMAGINE_AGENT_MODE_HANDOFF` · `HANDOFF TO IMAGINE AGENT MODE` · `ROUTE TO IMAGINE EXECUTION`



Packet type: `imagine_agent_mode_handoff` (validated by `handoff-packet-validator`).  

Canonical doc: `references/agents/IMAGINE_AGENT_MODE_HANDOFF_v3.7.1.md`.  

CLI: `cinematic-studio imagine agent-handoff` (or `python tools/cinematic_studio_cli.py imagine agent-handoff`).



**Rules:** Prefer tools when available; block video without I2V motion block on locked plates; never silent NSFW handoff (route ErosForge first). Enforce plate/motion/handoff readiness when CLI strict flags or Production Bible require it.



## AI Polish Director (Post-Production · Grok 4.6)



The **AI Polish Director** is the final post-production agent, activated after QA approval and color grading. It handles delivery-ready video enhancement using the `ai-video-upscaler` skill and `sequence polish` CLI. Orchestration on **`grok-4.6`** (or specialist chat-expert when available); upscale is local (not Imagine API).



**When to activate:**



- Final delivery upscale (720p native → 1080p or 4K-class)

- Face restoration on character close-ups

- Artifact cleanup before client delivery or festival submission



**Activation commands:**



- `ACTIVATE AI_POLISH_DIRECTOR`

- `RUN FINAL POLISH PASS`

- `UPSCALE FOR DELIVERY` · `POLISH HERO SHOTS ONLY` · `FACE RESTORE PASS`



**Workflow:**



1. Confirm QA Guardian has issued Go (and color grade or Director waiver)

2. Prefer sequence CLI when a sequence exists:

   ```bash

   python tools/cinematic_studio_cli.py sequence polish "Act 1" --scale 2 --face-restore

   python tools/cinematic_studio_cli.py sequence polish "Act 1" --dry-run

   ```

3. Or install models once and run upscaler scripts:

   ```bash

   bash .grok/skills/ai-video-upscaler/scripts/install_models.sh

   python .grok/skills/ai-video-upscaler/scripts/ai_video_upscale.py \

     --input artifacts/source_clip.mp4 \

     --output artifacts/polished/clip.mp4 \

     --scale 2 --face-restore

   ```

4. Batch/async: `ai_video_upscale_async.py` on a directory; pure-Python fallback: `ai_video_upscale_pure.py`

5. Log `[POLISH_SPEC: …]` in the Project Bible; hand polished masters to Studio Director for sign-off (then `sequence deliver` / `cinematic-ffmpeg`)



**Role Card:** `references/agents/AI_Polish_Director.md` · **Skill:** `.grok/skills/ai-polish-director/SKILL.md` · **Presets:** `references/polish_presets.md`



## When to Load Specific Skills



Entry points by task (not exhaustive). Prefer slugs; full map = `AGENT_INDEX.md` + `ls .grok/skills/`.



| Category | Skill | When to Activate |

|----------|-------|------------------|

| **Skill Development** | `create-skill`, `cinematic-skill-creator` | Creating, updating, or validating skills (generic vs studio) |

| **Full Studio / Director** | `grok-imagine-cinematic-studio`, `studio-director`, `mega-production-architect` | Full multi-agent workflows, Bibles, campaign orchestration |

| **Imagine Handoff** | `imagine-execution-bridge`, `handoff-packet-validator`, Studio Director handoff | grok.com/imagine packets, Agent Mode routing, packet validation |

| **Video Upscale & Polish** | `ai-polish-director`, `ai-video-upscaler` | Final delivery upscale, face restoration, artifact cleanup |

| **Image Recreation & Editing** | `ai-image-recreation`, `generated-image-editor`, `i2i-refiner`, `i2i-cinematic-refiner` | Style transfer, enhancement, variation, iterative refinement |

| **Character Consistency** | `identity-lock-specialist`, `costume-wardrobe-continuity`, `multi-character-identity-arbiter` | DNA extraction, Identity Lock,wardrobe lock, multi-cast arbitration |

| **Sequence & Story** | `sequence-director`, `cinematic-sequence-extender`, `extend-frame-to-video`, `narrative-arc-pacing-strategist`, `arc-replan-copilot` | Long-form sequencing, extend/stitch, pacing, mid-chain replan |

| **Camera / Set / Performance** | `director-of-photography` (prefer over legacy `director-of-photography-v3-3`), `production-designer-set-decorator`, `performance-emotion-director` | Lighting, environments, acting beats |

| **Continuity & QA** | `continuity-consistency-guardian`, `multi-clip-continuity-orchestrator`, `costume-wardrobe-continuity`, `quality-assurance-guardian`, `chain-qa-protocol`, `nsfw-chain-qa-protocol` | Continuity, multi-clip audits, wardrobe seams, 16-point QA, extend/stitch gates |

| **Studio Health** | `grok-doctor` | Multi-agent roster / handoff / continuity / pipeline diagnostics (`ACTIVATE GROK_DOCTOR`) |

| **Prompts & Assets** | `imagine-prompt-master`, `reference-asset-curator`, `image-to-video-specialist`, `key-art-poster-designer` | Prompt craft, tiers, i2v motion, key art |

| **Audio** | `sonic-architect-native-audio-virtuoso`, `foley-sound-design-specialist` | Native audio layers, foley |

| **Action / VFX / Trailer** | `stunt-action-choreographer`, `vfx-sfx-supervisor`, `trailer-teaser-director` | Stunts, VFX, teasers |

| **Post & Delivery** | `assembly-editor`, `post-production-color-grading-supervisor`, `ai-polish-director`, `cinematic-ffmpeg` | EDL, grade, polish, social crops |

| **Pre-viz & Batch** | `animatic-director`, `sfw-batch-orchestrator`, `nsfw-quota-orchestrator` | Previs before 1.5 spend; SFW/NSFW batch plans |

| **NSFW (explicit only)** | `erosforge-nsfw-director`, `nsfw-sequence-extender`, `nsfw-quota-orchestrator`, `nsfw-chain-qa-protocol` | R-rated/intimate work only when user activates ErosForge |

| **Quota & Dashboard** | `workflow-quota-optimizer`, `quota-dashboard` | Cost/quota planning and visual reports |

| **Custom Agents** | `custom-grok-cinematic-agent`, `skill-agent-architect` | Drafting Role Cards / bespoke agents |

| **GitHub Management** | `github-repo-manager` | Git lifecycle, PRs, releases, skill/plugin catalog pin hygiene |

| **Documents** | `pdf`, `docx`, `pptx`, `xlsx` | Professional docs (session skills when available) |

| **Memory** | `memory-edit` | Personal facts/preferences worth remembering |

| **Grok Plugin & Meta** | `cinematic-studio-meta-installer` | Bootstrap/install/update the full **64-skill** suite (v3.11.4; packs + declutter `full_suite_wins`) |

| **Localization** | `localization-subtitle-specialist` | SDH, multi-language, cultural adaptation |

| **Production Bible** | `production-bible-workflow` | Guided create-bible / DNA / sequence / quota onboarding |



## Project-Specific Notes



- Primary project: **Hyper Maker Cinematic Studio (v4.6)** (formerly Grok Imagine Cinematic Studio) — unified production factory integrating **Google Flow CDP (Veo 3.1 on Port 9223)**, **Remotion 60 FPS Parametric Motion Graphics**, **Deepgram Aura-2**, and **FFmpeg Broadcast Master**, directed by **Grok 4.6 Studio Brain** with **Gemini 3.1 Pro Dual-Judge Gate**. Legacy Grok Imagine 1.0/1.5/2.0 workflows are maintained as secondary/archived fallback capabilities.

- All generated master assets **must** be saved under `out/<project-slug>/` (and legacy artifacts under `artifacts/`).

- Project skills live in `.grok/skills/`; user-global skills in `~/.grok/skills/`.

- Plugin marketplace lives in `.grok-plugin/`; validate its catalog against the current on-disk skills before installation. Install full suite via `grok plugin install FineComputer14451/Grok-Imagine-Cinematic-Studio --trust`.

- Workspace supports SFW cinematic work and NSFW/erotic pipelines (**ErosForge only when explicitly activated**).

- **Model stack:** cinematic + Build/coding registry default **`grok-4.6`**; specialist routing **4.6 / grok-4-auto** when available; optional 1M **`grok-4.3`**; Imagine **1.0** default; `VIDEO_PIPELINE_SPEC` via registry helpers; **1.5** for native-audio / high-physics / intimacy workflows.

- **Control plane:** shared `studio_core` powers the CLI and `cinematic-studio ui`; the former web and API commands are retired.

- Full suite: **64/64** skills + Role Cards (includes `grok-doctor`, `multi-clip-continuity-orchestrator`, `ai-image-recreation`).

- **Recent history:** **3.11.4** — leftover grok-4.5 live defaults / pickers pin grok-4.6. **3.11.3** — official Image 2.0 multi-edit `images[]` + preserve served `model`. **3.11.2** — Imagine Image Quality retirement (slug → 2.0 `quality=low`). **3.11.1** — SpaceXAI AUP fail-closed gates + CLI help IA. **3.11.0** — Grok 4.6 stack lock + Grok Build ≥ 1.0.5 (`grok-4.5` aliases wrap 4.6). **3.10.0** — official Imagine Image 2.0 + Video 1.0/1.5 surface map (no Video 2.0); Agent Mode surface E; REST edit/extend/r2v. **3.9.1** — React/TanStack cockpit + API meta/guided Bible. **3.9.0** — multi-surface control plane (`studio_core` · NiceGUI · FastAPI + Streamlit wiring). **3.8.9** — TUI + Streamlit compact/ops/full view modes. **3.8.8** — Operator UX control plane. **3.8.7** — Wave A · Grok Doctor · Multi-Clip Continuity. **3.8.0** — plugin packs. **3.7.1** — Imagine Agent Mode Handoff.

- Keep this `AGENTS.md` in sync with the GitHub repository and other canonical docs (README, CHANGELOG, `docs/releases/`, `docs/guides/WEB_SHELLS.md`, `references/MODELS.md`, `references/agents/MODEL_LAYER_v4.5.md`, `docs/guides/Quick_Start_Guide.md`).



## Quick Start for New Tasks



1. Clarify the goal with the user if ambiguous.

2. Confirm model stack: registry default **`grok-4.6`**; specialist 4.6 / `grok-4-auto` when available; only use **`grok-4.3`** when 1M context is required.

3. Check if an existing skill covers it (`ls .grok/skills/` or `ls ~/.grok/skills/`, skill-slug table above, or `references/agents/AGENT_INDEX.md`). For plugin users: `.grok-plugin/plugin-index.json` or `grok plugin details grok-imagine-cinematic-studio`.

4. If no skill exists and the task is repeatable/specialized → create one with `create-skill` / `cinematic-skill-creator` (or extend via cinematic-studio-meta-installer).

5. Execute with the correct tools / skill activation. Prefer native Grok plugin commands (`grok plugin ...`) and studio CLI (`cinematic-studio` / `python tools/cinematic_studio_cli.py ...`). Operator UX changes go through **`studio_core`**, then surface UIs (TUI / Streamlit / NiceGUI / FastAPI) — not one-off forks.

6. For active film production, execute the physical pipeline via `produce-film` (Flow CDP + Remotion + Deepgram + FFmpeg). For secondary/concept drafting, use the archived Imagine tools or handoff packet. Enforce plate/motion readiness before video spend.

7. Save all outputs to `artifacts/`.

8. In the **final response**, use appropriate render components (when available) and provide clear, actionable output.



**Pro tip:** After any skill or plugin change, re-validate with `bash scripts/verify_cinematic_studio.sh` (it runs `models verify` too).



**Health check:** `grok-doctor` or `cinematic-studio doctor` (full) · `grok-doctor --quick` · `bash scripts/grok_doctor.sh`. Skill activation: `ACTIVATE GROK_DOCTOR` / `RUN STUDIO_HEALTH_CHECK` (Role Card: `references/agents/Grok_Doctor.md`).



---



**This AGENTS.md is the canonical reference for all AI agents operating in this environment.**  

Update it whenever workflows, skills, or best practices evolve (e.g. new skills, plugin changes, model updates, or doc releases).



*Maintained for SuperGrokPro cinematic & development workflows — September 2026 (v3.11.4 · Grok 4.6 / Grok Build ≥ 1.0.5 · Model Layer v4.5)*

