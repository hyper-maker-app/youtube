# VIRAL SECOND-PERSON RETENTION & FOLEY PRODUCTION PROTOCOL v4.0
**Canonical Architecture Standard for Grok Imagine Cinematic Studio v4.0**
*Effective: October 2026 | Authority: Studio Director & Physical Production Engine*

---

## 1. Executive Summary & Core Invariant

This protocol encodes the narrative, auditory, and visual architecture responsible for top-decile YouTube retention in cinematic AI storytelling (calibrated against viral survival formats exceeding 2.7M+ views).

> [!IMPORTANT]
> **%100 ENGLISH PRODUCTION INVARIANT (Zero-Turkish Invariant):**  
> Every script beat, spoken voiceover, subtitle caption, prompt instruction, and forced alignment dictionary must run exclusively in **100% English (`en` / `en-US`)**. Turkish generation in cinematic narrative outputs is strictly prohibited.

---

## 2. Narrative Reform: "Beanie Survives" 2nd-Person POV

### 2.1 Forbidden Conventions
- **Zero 3rd-Person Passive Narration:** Never use "Elias runs...", "Dr. Kane discovers...", or "The protagonist navigates...".
- **Zero Metadata / Directive Leaks:** No "Act 1:", "Scene 01:", `[Sound of sirens]`, or `(whispering)` within narration text. Every string entering TTS must pass through `engine/services/text_sanitizer.py`.

### 2.2 Mandatory Invariants
1. **2nd-Person Singular ("You / Your"):**
   Direct, intimate, second-person engagement. The viewer *is* the survivor:
   - *"Your breath fogs the inside of your gas mask."*
   - *"You tighten the padlock bolt. Forty-two decibels outside."*
2. **In Media Res (First 3 Seconds Hook):**
   No establishing city flyovers or slow fade-ins. The story opens at the point of acute danger:
   - Second 0-3: A locked door shudders under violent impact, breathing inside a mask, immediate stakes.
3. **Micro-Survival Mathematics:**
   Audience investment relies on concrete, tangible stakes rather than abstract danger:
   - **Water/Hydration:** Exact milliliters remaining (*"Seven hundred milliliters left in your canteen."*).
   - **Sound & Decibels:** Tangible decibel meter thresholds (*"The sensor pulses at 64 decibels. Sixty-five brings the horde."*).
   - **Battery & Tech:** Precise percentage gauges (*"Emergency battery pack at 14%."*).
   - **Barricade Physics:** Countable physical barriers (*"Three layers of cross-hatched heavy duct tape."*).

---

## 3. Visual & Framing Discipline (Zero Facial Hallucination)

Generative video models (Veo, Imagen 3, Kling, Wan) degrade when forced into close-up talking heads. The v4.0 standard solves this by framing for **situational tension and atmospheric perspective**:

1. **Peephole POV:** Scratched brass peepholes, frosted glass, reinforced slit viewports showing distorted motion outside.
2. **Macro Tactile Details:** Gloved hands stretching duct tape, tightening vice grips, striking magnesium flares, canteen angles.
3. **LED & Sensor Readouts:** Low-angle focus on glowing digital battery numbers, pulsating amber decibel meters.
4. **Backlit Silhouettes & Weather:** High-contrast chiaroscuro shadows, silhouettes framed against driving rain, industrial fog, flickering sodium flares. Zero face close-ups.

---

## 4. Dynamic Editorial Tempo

Fixed 8.0s blocks deaden viewer attention. The editorial rhythm is dynamically selected based on scene dramaturgy:
- **4.0s (Shock / Impact):** Sudden door breach, falling ceiling grate, quick tool grab.
- **6.0s (Calculated Traversal):** Ascending vertical ladder, duct taping door seam, low-angle boot crawl.
- **8.0s (Tension Hold / Observation):** Peephole surveillance, counting decibel spikes, evaluating corridor.
- **10.0s (Atmospheric Climax / Payoff):** Rooftop storm emergence, striking emergency flare into gale.

---

## 5. Dual-Stage SFX & Procedural Foley Engine

Sound design constitutes 60% of perceived cinematic immersion:

1. **Primary: Hugging Face Gradio Space (`engine/providers/sfx/gradio_space.py`):**
   - Direct connection to `fffiloni/audiogen` and `declare-lab/TangoFlux`.
   - 20s network timeout with automated fallback.
2. **Fallback / Offline: FFmpeg Lavfi Synthesizer (`engine/providers/sfx/ffmpeg_lavfi.py`):**
   - Instant (< 80ms), zero-cost, Windows-compatible procedural synthesis.
   - 4 Archetypes:
     - `whoosh`: Bandpass-filtered pink noise sweep.
     - `sub_bass_thud`: Low 58Hz sine burst with steep exponential decay.
     - `tension_heartbeat`: 52Hz double-pulse rhythmic dread heartbeat.
     - `wind_drone`: 260Hz brownian atmospheric low-frequency drone.
3. **Assembly Mixing:**
   - Stereo Haas delay widening, highpass at 75Hz, -14 LUFS broadcast normalization.

---

## 6. Filmstrip Grid "Transition Boundary Triplet" QA

To eliminate discontinuous jump-cuts and costume/lighting shifts between video blocks:

1. **In-Memory OpenCV Assembly:**
   Horizontally stacks:
   `[Hero DNA Plate] | [Block N Exit Frame (t=T-0.04s)] | [Block N+1 Entry Frame (t=0.04s)]`
   Single composite JPEG (~16-25 KB, ~258 tokens).
2. **Gemini 2.5 Flash Structured Validation:**
   Evaluates 6 continuity rules:
   - Wardrobe match
   - Held items / props
   - Lighting vector & palette
   - Spatial axis & camera perspective
   - Physical damage persistence
   - Temporal logic
3. **Fail-Soft Enforcement:**
   - If continuity score < 0.85: Injects `corrective_prompt` and triggers 1x re-roll.
   - If second attempt remains under 0.85: Logs advisory warning and proceeds without stalling production.

---

## 7. Voiceover & Forced Alignment Standard

- **Voice Providers:** Pluggable `deepgram` (Aura-2), `voyslity`, or `elevenlabs` (Daniel, Adam, Rachel, Antoni).
- **Format:** Converted to 48kHz mono PCM WAV via FFmpeg.
- **Alignment:** Deepgram Nova-3 English STT forced alignment + `difflib.SequenceMatcher` to project timestamps back onto fully punctuated manuscript tokens.
