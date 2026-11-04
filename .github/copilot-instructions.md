# GitHub Copilot Instructions — Grok Imagine Cinematic Studio v3.11.4

**Project Identity:** Grok Imagine Cinematic Studio v3.11.4  
**Project Affiliation:** Independent community project (not affiliated with, endorsed by, or connected to xAI).  
**Primary References:** `AGENTS.md` and `references/agents/AGENT_INDEX.md`.

---

## 1. Skill Bridge & Domain Delegation
Always inspect and refer to existing domain skills before writing new logic, scripts, or narrative generation pipelines:
- **Skill Location:** `.grok/skills/` (64 specialized production skills)
- **Role Cards & Agent Definitions:** `references/agents/AGENT_INDEX.md` and `references/agents/*.md`
- **Key Department Skills:**
  - `studio-director`: Master production direction & multi-agent orchestration
  - `mega-production-architect`: Full cinematic project architecture
  - `director-of-photography`: Lighting, optics, lens packages, and camera movement
  - `post-production-color-grading-supervisor`: Film stocks, LUTs, and color spaces
  - `character-dna-extractor`: Consistent character seed extraction
  - `identity-lock-specialist`: Visual identity preservation across shots
  - `sonic-architect-native-audio-virtuoso`: Sound design, mixing, and acoustic envelopes
  - `foley-sound-design-specialist`: Physical foley, footsteps, impacts, and textures
  - `quality-assurance-guardian`: Cross-block continuity and transition inspection
  - `cinematic-ffmpeg`: Multi-track AV assembly and rendering

---

## 2. Strict Prohibition: Zero Ad-Hoc Probing
- **Strictly Forbidden:** Writing ad-hoc scratch scripts (`test_*.py`, `check_server.py`, `probe_ports.py`, socket listeners) to inspect background servers, cookies, Chrome CDP (port 9223), or local proxy (port 8085).
- **Mandatory Direct CLI Invocation:** Always interact with and execute production using the unified CLI:
  ```bash
  # Plan-only generation (Zero-cost screenplay & shotlist):
  python tools/cinematic_studio_cli.py produce-film "Title" --genre "Sci-Fi Survival" --duration 60 --plan-only

  # Full Physical Render (Google Flow CDP + Voice Synthesis + FFmpeg):
  python tools/cinematic_studio_cli.py produce-film "Title" --genre "Sci-Fi Survival" --duration 60 --voice-provider deepgram

  # Dry-run execution:
  python tools/cinematic_studio_cli.py produce-film "Title" --genre "Sci-Fi Survival" --duration 60 --dry-run
  ```
- All connection lifecycles, health checks, and browser automation are internally encapsulated in `engine/flow_bridge.py`.

---

## 3. Pure Engine & Skill Architecture (Zero Hardcode)
- **Python Engines (`engine/`, `tools/`):** Pure execution pipelines only. Never hardcode story scripts, dialogue lines, visual prompts, camera directives, or word replacement maps inside Python codebase.
- **Skill Markdown (`.grok/skills/*.md`):** Must consist solely of universal directing principles, physical/environmental constraints, and structural rules. Never hardcode specific scene dialogue, static narratives, or literal CTA strings.
- **UI Components (`web_ui/`, `web_react/`, `web_nicegui/`):** 100% parametric. Components must take dynamic JSON payloads and props; zero hardcoded content strings.

---

## 4. Viral Second-Person & Foley Standard (Protocol v4.0)
All scriptwriting, audio, and visual generation must adhere to `references/agents/VIRAL_SECOND_PERSON_RETENTION_FOLEY_PROTOCOL_v4.0.md`:
1. **100% English Invariant:** Screenplays, voiceovers, subtitle captions, prompt directions, and alignment dictionaries must strictly be in English (`en` / `en-US`). Zero Turkish text in production pipelines.
2. **2nd-Person POV ("You / Your"):** Direct singular perspective. No 3rd-person narrator ("Elias walked...", "He saw...").
3. **In Media Res Crisis Hook (First 3 Seconds):** Immediate sensory danger and acute stakes from second zero. No slow fade-ins or establishing flyovers.
4. **Micro-Survival Mathematics:** Concrete tangible resource tracking (water milliliters, decibel alarm thresholds, emergency battery percentages, physical tape/barricade layer counts).
5. **Spoken Text Sanitizer Gateway:** All narration strings must pass through `engine/services/text_sanitizer.py` to remove scene markers ("Act 1:", "Scene 01:") and bracketed directives (`[Sound of breathing]`, `(whispering)`).
6. **Atmospheric / Situational Visuals:** Focus on door peephole POV, macro tool grips, sensor LED readouts, and backlit rain silhouettes to eliminate AI facial uncanny-valley defects.
7. **Dual-Stage SFX & Procedural Foley:** Primary Hugging Face Space (`fffiloni/audiogen`, `declare-lab/TangoFlux`) with automatic fallback to local FFmpeg Lavfi synthetic foley.
8. **Transition Continuity Triplet QA:** Automated cross-block continuity checks using Gemini 2.5 Flash / OpenCV on `[Hero DNA] | [Block N Exit] | [Block N+1 Entry]` with a 1x corrective re-roll on score < 0.85.

---

## 5. Model Stack & Flow Factory Definition
- **Default Models:** Locked to `grok-4.6` in `tools/models.py`. Long-context bank uses `grok-4.3`. Video defaults: `grok-imagine-video` (1.0 default) / `grok-imagine-video-1.5` (native audio / physics). Image hero: `grok-imagine-image-2.0`.
- **Flow Engine Definition:** In this workspace, "Flow" exclusively denotes the Google Flow CDP factory (Port 9223) + Deepgram Aura-2 / Voyslity / ElevenLabs + FFmpeg pipeline (`engine/flow_bridge.py`). Never confuse with generic ComfyUI or standalone web chat prompts.
- **Hero Plates & State:** Save hero character reference plates to `characters/<character_slug>_hero.jpg` and link them in `sequences/<project>_handoff.json`.

---

## 6. Verification & Test Commands
When running tests or verifying workspace integrity:
```bash
# Environment & dependency doctor:
python tools/cinematic_studio_cli.py doctor

# Model registry verification:
python tools/cinematic_studio_cli.py models verify

# Smoke test all control plane surfaces:
python scripts/smoke_studio_surfaces.py

# Run unit and integration tests:
pytest tests/
```
