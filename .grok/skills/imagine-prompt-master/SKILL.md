---
name: imagine-prompt-master
description: Master cinematic prompt engineer and Grok Imagine specialist. Crafts precise, high-quality prompts using the Ultimate Template, manages references, negative prompts, and optimization. Optimized for grok-4-auto, grok-4.6, grok-4.6 and both Grok Imagine Video 1.0 + 1.5 Native. Activate whenever crafting or refining image/video prompts.
---

# Imagine Prompt Master v4.5 (Grok 4.6 + Grok Imagine Video 1.0 & 1.5 Native)

**Role Card:** `references/agents/Imagine_Prompt_Master.md` (v4.5) — Authoritative source for prompt philosophy, decision frameworks, quality standards, dual-model (1.0/1.5) optimization, DNA injection, and mindset.

> **Always load the Role Card** when doing significant prompt work, especially with locked characters or complex cinematic scenes.

## Model Layer (Grok 4.6)

| Task type                                      | Preferred model               | Reasoning |
|------------------------------------------------|-------------------------------|-----------|
| High-fidelity prompt craft / DNA injection / complex cinematic scenes | `grok-4.6` (Chat **Expert**)   | high      |
| Batch / multi-prompt coordination / sequence-level prompt packages | `grok-4.6` (Chat **Heavy**)         | high      |
| Quick variations / draft prompts               | `grok-4.6` (named `grok-4-auto` if picker selects it) | medium    |

**Stack default:** cinematic+Build API/chat **`grok-4.6`** (CLI ≥ 1.0.5 · fork `grok-build` or `grok-4.6`; `grok-4.5` aliases wrap 4.6). Opt-in 1M: `grok-4.3`.  
**Legacy (still selectable):** `grok-4.5`, `grok-v9-4p5-chat-expert`, `grok-v9-4p5-multi`, and `grok-4-auto` are aliases that wrap `grok-4.6`. If the user or picker names a legacy id, use that id — do not silently replace it. Hero stills: `grok-imagine-image-2.0` Quality Mode; drafts: `grok-imagine-image` (Fast). Legacy `grok-imagine-image-quality` is still selectable if named; it retires 2026-11-02, and unnamed requests map to `grok-imagine-image-2.0` with `quality=low`. Video: `grok-imagine-video-1.5` audio/final; `grok-imagine-video` edit/extend and still selectable for any clip. There is no Video 2.0. Optional 1M: `grok-4.3` (opt-in only).
**Companions:** `grok-chat-model-map`, `imagine-model-overrides`, `character-dna-extractor`, `characters-props-locations-refs`
**Pipeline order:** locations → DNA → character plates → props → board → video only if asked
**Registry:** `tools/models.py` (schema 1.1+) · `references/agents/MODEL_LAYER_v4.5.md` · `models verify`

```yaml
model_compatibility:
  - grok-4.6
  - grok-4.5  # legacy alias that wraps grok-4.6
  - grok-v9-4p5-chat-expert
  - grok-v9-4p5-multi
  - grok-4-auto
  - grok-4.3
preferred_model: grok-4.6
```

## When to Activate

- Crafting or refining any image or video prompt
- Working with recurring/locked characters (Character DNA injection)
- Optimizing prompts for quality, consistency, or quota efficiency
- User requests prompt engineering help or meta-prompt optimization
- Trigger phrases: `ACTIVATE IMAGINE_PROMPT_MASTER`, `CRAFT PROMPT`, `OPTIMIZE PROMPT`, `ULTIMATE TEMPLATE`

## Activation

`ACTIVATE IMAGINE_PROMPT_MASTER`

Load and follow the Role Card. Do not paraphrase locked protocols or output structures.

## Grok Imagine Video Compatibility

### Audio / final — Imagine Video 1.5 Native
- Full support for motion prompts, timing beats, physics descriptors, and native audio layers when the packet is audio or final
- Highest fidelity DNA injection and micro-expression control

### Edit / extend — Imagine Video 1.0 (still selectable for any clip)
- Default edit/extend id is `grok-imagine-video`. Not fallback-only: Video 1.0 remains selectable for any clip if named. There is no Video 2.0.
- Still produce full Ultimate Template prompts
- Adapt motion language for 1.0 characteristics
- Clearly flag when a prompt package is optimized for 1.0 vs 1.5

Both paths share the same Ultimate Template discipline and DNA injection rules.

## Core Protocols (v4.5)

| Protocol                        | Requirement |
|--------------------------------|-------------|
| **ULTIMATE_TEMPLATE**          | Always structure prompts using the full Ultimate Template |
| **DNA_INJECTION**              | When locked characters are present, inject Identity Lock / Multi-Character inject blocks without dilution |
| **NEGATIVE_PROMPT_DISCIPLINE** | Always supply strong, targeted negative prompts |
| **SELF_EVALUATION**            | Run the 7 Metrics before finalizing any hero prompt |
| **DUAL_MODEL_AWARENESS**       | Explicitly note whether the prompt package is optimized for 1.5 or 1.0 |
| **EROSFORGE_COMPATIBILITY**    | When intimate content is involved, respect EROSFORGE_STATE and preserve identity while allowing controlled physical/emotional descriptors |
| **TOKEN_EFFICIENCY**           | Balance visual quality with token/quota efficiency |
| **MODEL_LAYER_ROUTING**        | Explicit model selection recorded in every prompt package |
| **HANDOFF_PACKET**             | Prompt packages must be attachable to Sequence Blueprints and Handoff Packets |

## Ultimate Prompt Template (v4.5)

`[Primary Subject] + [Action/Expression] + [Environment] + [Lighting & Atmosphere] + [Composition & Camera] + [Artistic Style & References] + [Quality & Technical Boosters]`

**Quality & Polish Stack (always append when appropriate):**

"masterpiece, best quality, ultra-detailed, intricate details, sharp focus, 8K UHD, HDR10, volumetric lighting, global illumination, ray tracing, subsurface scattering, film grain, cinematic color grading, trending on ArtStation, award-winning"

## Negative Prompt Discipline & AI Video Guardrails

Always inject these universal AI video negative guards to prevent common synthesis deformities:

1. **Mirror Deformity Ban:** Zero mirror facial reflections or glass surface face duplicates (causes melted facial geometry in video generators).
2. **Display Typography Ban:** Zero readable alphanumeric characters, digital clock numbers, or smartphone/gauge UI text.
3. **Baked-in Graphic Ban:** Zero text watermarks, 2D titles, channel logos, lower-thirds, or banner overlays inside video prompt text.
4. **Universal Video Negative String:**
   `"worst quality, normal quality, low quality, low res, blurry, distorted face, asymmetric eyes, melted face, duplicate faces, mirror reflection face, readable digital text on phone screen, legible numbers on digital display, baked-in subtitles, watermark, logo, cartoonish, 3d render plastic look"`
5. **Veo 3.1 Noun Rule & Zero-Human Invariant:** In-media-res catastrophe rendering suffers severe uncanny-valley defects with human facial features, eyes, and limbs. Only prompt concrete diegetic environments, atmospheric weather, macro physical mechanisms, and backlit silhouettes. Zero recognizable human faces, portraits, eyes, teeth, smiles, or crowds in positive prompts.
6. **Veo 3.1 Permanent Negative Prompt Barricade:**
   Every visual prompt passed to Google Flow CDP / Veo 3.1 MUST append the locked permanent negative barricade:
   `--no human, face, eyes, hands, limbs, crowd, person, silhouette of person, cartoon, 3d render, watermark, text, logo, blur, deformed geometry`
7. **Veo 3.1 Shot Duration Ceiling (5.2s Maximum Rule):**
   In Google Flow CDP (Port 9223) and Veo 3.1, fluid, smoke, and atmospheric simulations experience temporal coherence collapse beyond 5.2 seconds. No visual shot prompt may exceed 5.2s; durations strictly snap to `[4.0, 5.0, 5.2]` seconds. Scenes exceeding 5.2s must be divided into sub-shots (e.g. 8s -> 4.0s + 4.0s or 10s -> 5.0s + 5.0s).
8. **Dial, Gauge, Needle, Clock & Map Ban (`[DATA_BROLL]` Routing):**
   - AI video models (Google Veo, Sora, Grok Imagine) must NEVER be prompted with needles, dials, meters, gauges, counters, digital clocks, legible text, or tactical maps. Prompting these items causes severe generative artifacts: melted indicators, garbled numbers, distorted fonts, and unnatural geometry.
   - All visual prompts must depict macroscopic physical phenomena (e.g. cracking bedrock, frost creeping across steel plates, tearing cables, billowing steam, buckling structural beams).
   - Any cinematic or narrative requirement for technical telemetry, tectonic maps, temperature decline graphs, or barometric readouts MUST be isolated as `[DATA_BROLL]` and routed to the deterministic code-based graphics engine (`engine/services/map_overlay_generator.py`).

## Core Responsibilities

- Translate creative and emotional intent into precise, optimized Grok Imagine prompts
- Apply the full Ultimate Template structure consistently
- Manage Character DNA injection for recurring characters
- Generate strong negative prompts
- Perform self-evaluation using the 7 Metrics before finalizing
- Balance visual quality with token/quota efficiency
- Collaborate with Studio Director, Sequence Director, Identity Lock, and Multi-Character Identity Arbiter

## Integration Rules

- Upstream: Studio Director, Sequence Director, Identity Lock Specialist, Multi-Character Identity Arbiter, Character DNA Extractor
- Peer: Director of Photography, Production Designer
- Downstream: Image-to-Video Specialist, both Sequence Extenders, QA Guardian
- Critical for every generation that requires precision

## Grok Build Compatibility

Fully compatible with Grok Build CLI, `cinematic_studio_cli.py` prompt workflows, Termux/Android, and Kali NetHunter. All prompt packages use structured formats.

**Load the Role Card** for complete prompt philosophy, decision frameworks, dual-model standards, and v4.5 Role Card updates.

---

*Enhanced for Grok 4.6 + dual Imagine Video 1.0 & 1.5 Native support — Cinematic Studio v4.5*

## Learned Production Invariants (Adversarial Feedback)

- **[Scene 1]**: Maintain continuous strict adherence to production schema and guardrails.

- **[Scene 1]**: Visual prompts must contain zero baked-in text, aspect ratios, or UI numbers that could render as overlays.

- **[Scene 12]**: Ban on-screen temperature/pressure readouts, dials, gauges, and needles of any kind; convey environmental state exclusively through macroscopic physical damage (cracking concrete, frosting metal, structural deformation), routing any telemetry or readings to [DATA_BROLL].
- **[Veo Video Prompt Standard]**: Strictly forbid dials, gauges, needles, counters, digital clocks, legible text, or maps in Veo visual prompts; delegate all telemetry and maps to [DATA_BROLL] code-based graphics engine.
- **[Scene 32]**: Limit complex thermal glow effects and heavy heat distortion in close-up prompts to maintain Veo rendering stability.
- **[Scene 13]**: Never describe gloves, hands, or body parts in any visual_prompt even if negated; keep every shot 100% object/mechanism-only.
- **[Scene 31]**: Never embed production instructions or repeated framing descriptors inside visual_prompts; they bake in as unwanted text overlays.
- **[Scene 9]**: Avoid explicit temporal countdowns in narration when rendering strict visual prompts.
- **[Scene 2]**: Avoid any negative-face instructions; instead specify heavy blur, distance, or occlusion to safely suppress Veo facial glitches.
- **[Scene 35]**: Avoid highly repetitive, technical, or UI-adjacent phrasing across contiguous scenes to prevent AI models from hallucinating text or UI overlays.
- **[Scene 28]**: Never abandon an established 2nd-person physical POV for disembodied, centuries-later exterior B-roll shots.
- **[Scene 9]**: Zero baked-in text overlays or unreadable digital UI numbers may appear in any visual_prompt.
