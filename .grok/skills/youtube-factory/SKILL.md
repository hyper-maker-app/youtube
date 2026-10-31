---
name: youtube-factory
description: Orchestrates end-to-end automated YouTube video factory pipelines with 300-second longform narratives, three-layer broadcast audio, automated boundary inspection QA, and thumbnail packaging. Activate when running autonomous multi-phase video generation, channel batch production, or end-to-end release builds.
---

# YouTube Factory v4.5 (Grok 4.6 · Autonomous Video Production Engine)

**Activate when orchestrating end-to-end automated YouTube video factory operations.** You coordinate narrative synthesis, voiceover alignment, procedural video generation via Google Flow CDP, multi-track audio mixing, visual QA gates, and delivery packaging.

**Department:** Executive Production / Automated Channel Pipeline  
**Specialty:** 300-second (4.5m+) video pipelines, 3-layer broadcast audio mixes, autonomous continuity QA, thumbnail integration.

## Model Layer (Grok 4.6)

| Task type | Preferred model | Reasoning |
|-----------|-----------------|-----------|
| Multi-agent orchestration / handoff synthesis | `grok-4.6` (Chat **Heavy**) | high |
| Specialist deep craft / QA / identity-critical | `grok-4.6` (Chat **Expert**) | high |
| Routine status / draft passes | `grok-4-auto` | medium |

**Stack default:** cinematic+Build API/chat **`grok-4.6`** (CLI ≥ 1.0.5 · fork `grok-build` or `grok-4.6`; `grok-4.5` aliases wrap 4.6). Opt-in 1M: `grok-4.3`.  
**Registry:** `tools/models.py` · `references/agents/MODEL_LAYER_v4.5.md` · `models verify`

```yaml
model_compatibility:
  - grok-4.6
preferred_model: grok-4.6
```

## When to Activate

- Running the complete YouTube video pipeline from single title prompt to published package.
- Producing 300-second (4.5-minute+) longform catastrophe and explainer content.
- Managing 3-layer broadcast audio: TTS Voiceover + ducked -14 LUFS music bed + procedural SFX foley.
- Verifying cross-block visual continuity with Transition Boundary Triplet QA (threshold 0.80).
- User says: `ACTIVATE YOUTUBE_FACTORY`, `PRODUCE FILM [title]`, `RUN YOUTUBE PIPELINE`, `FACTORY_BUILD`.

Begin: **"Initiating YouTube Factory Protocol v4.5 (Grok 4.6)…"**

## Production Engine Pipeline (6 Core Phases)

1. **Phase 1: Longform Screenplay Synthesis (300 Seconds / 34–38 Scenes)**
   - Invokes `generate_universal_scenes()` or `generate_catastrophe_scenes()`.
   - Adheres to the 5-act retention curve: hook (0–4s), buildup (4–40s), escalation (40–200s), climax (200–270s), resolution/subscribe hook (270–300s).
   - Generates ~38 distinct scene blocks (6–8s each) with strict 2nd-person singular perspective.

2. **Phase 2: Voiceover & Alignment Generation**
   - Renders 100% English speech via selected voice provider (Deepgram, Azure Neural TTS, Voyslity, ElevenLabs).
   - Extracts millisecond-accurate word boundaries into `words.json`.
   - Calculates exact target audio clock for video duration packing.

3. **Phase 3: Physical Video Render (Google Flow CDP)**
   - Uses `engine.flow_bridge.execute_grok_flow_production()`.
   - Snaps scene durations to supported Veo tiers (`[4.0, 6.0, 8.0, 10.0]` seconds).
   - Renders video blocks with prompt compilation, hero DNA plates, and camera vectors.

4. **Phase 4: Transition Boundary Triplet QA (Threshold: 0.80)**
   - Inspects consecutive video junctions: `[Hero Plate] + [Block N Exit] + [Block N+1 Entry]`.
   - Continuity score gate calibrated to `0.80` (lowered from 0.85 to eliminate false-positive HEAL rerolls).
   - Logs visual evaluations and defects into `out/<project>/qa_report.json`.

5. **Phase 5: 3-Layer Audio Mixing & SFX Foley Bed**
   - **Layer 1 (TTS Voiceover):** Broadcast-normalized speech track with word sync.
   - **Layer 2 (Music Bed):** Procedural or licensed background bed normalized to -14 LUFS with dynamic sidechain ducking.
   - **Layer 3 (Procedural SFX Foley):** Auto-categorized sound cues extracted from scene descriptions (explosions, waves, alarms, earthquakes, whooshes).

6. **Phase 6: Thumbnail & Delivery Packaging**
   - Auto-extracts peak climax keyframe (~72% timeline position).
   - Composites 4-layer 1280×720 thumbnail with red-orange gradient and bold title text.
   - Seals continuity state, karaoke subtitles (`captions.ass`), and release manifest.

## Primary CLI Commands

```bash
# Planning Only (Zero-cost screenplay verification)
python tools/cinematic_studio_cli.py produce-film "Title" --genre catastrophe --duration 300 --plan-only

# Full Dry-Run Pipeline Validation
python tools/cinematic_studio_cli.py produce-film "Title" --genre catastrophe --duration 300 --dry-run

# Production Render with Specific Voice Provider
python tools/cinematic_studio_cli.py produce-film "Title" --genre catastrophe --duration 300 --voice-provider azure
```
