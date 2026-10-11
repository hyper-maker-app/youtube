# YouTube Shorts Automation — LLM Context & Analysis Guide

This document is provided specifically for AI language models (Claude, ChatGPT, Gemini, etc.) to understand this codebase, its architectural constraints, and the specific production run included in this bundle.

---

## 1. Project Overview & Benchmark Reference

- **Goal**: Autonomous production of Zack D. Films-style 3D vertical documentary YouTube Shorts (9:16 aspect ratio, 1080x1920, 45–58s sweet spot).
- **Sole Benchmark Reference**: [Zack D. Films (@zackdfilms)](https://www.youtube.com/@zackdfilms) (30M+ subscribers).
- **Production Paradigm**: Sourced real-world medical, physical, anatomical, or incident scenarios broken down with hyper-focused scientific visualization, continuous scale progression, and synchronized diegetic sound design.

---

## 2. Core Architectural Invariants (Non-Negotiables)

1. **Visual Style (Zack D. DNA)**:
   - Glossy stylized 3D mannequins (Glossy Claymation, subsurface scattering SSS), mineralized cortical bone, translucent internal organs, viscous non-Newtonian fluids.
   - **No Mannequin Contamination**: Mannequin tokens (e.g. clay head/shoulders) are strictly forbidden inside internal organ, cellular, or mechanical cutaway scenes (ADR-024).
2. **Character & Dialogue Rules**:
   - Characters **NEVER speak or lip-sync** (ADR-002). Mouths must be explicitly closed or neutral in all image/video prompts.
   - Dialogue is strictly prohibited. Narration is third/second-person voiceover.
   - Captions are rendered exclusively via FFmpeg/ASS subtitles with broadcast-accurate word-level timing (from Deepgram Hermes).
3. **Camera & Framing**:
   - Aspect ratio is strictly **9:16 vertical** (1080x1920) across all keyframes and video blocks.
   - Scale flow: wide <-> medium <-> close <-> macro <-> micro <-> nano.
   - Continuous camera flight (continuous_camera_flight) with center framing lock on scale transitions (scale_transition).
   - Lower-middle zone (y=1350–1750) is reserved for captions. Visual focus and markers must remain in the upper or mid-frame.
4. **Evidence-Based Markers**:
   - Markers (e.g., neon-green arrows, pressure vectors, red trajectory lines) are generated **ONLY** when proof_on_screen explicitly authors them. Decorative or random overlays are forbidden (ADR-003).
5. **Acoustic Design**:
   - **No Acoustic Void**: Silence behind voiceover is forbidden. A mood-matched audio bed (synthesized via FFmpeg lavfi or generated) is always present (ADR-025).
   - **Voiceover Priority**: Voiceover is never artificially ducked or pumped. Sidechain ducking on BGM uses MUSIC_VOLUME = 0.19 (-14.4 dBFS) (ADR-017).
   - **ASMR Foley Hits**: Natural decay envelope of 0.55–0.75s, high-pass at 75 Hz, +2.0 dB boost at 4.0 kHz for crisp ASMR presence, synchronized to visual peak impact moments (ADR-029).
   - **Broadcast Standard**: Target integrated loudness is -14.0 LUFS (±1 LUFS) with -1.5 dBTP true peak.
6. **Tri-Modality Priority**:
   - incident > mechanical > anatomical (ADR-026). The script engine dynamically applies visual anchors, color grading, and SFX profiles based on detected modality.
7. **Narration Ceiling & Pacing**:
   - Maximum **120 words** narration ceiling (safe_target = min(120, target) in config.py).
   - 6 to 13 blocks x 4.0s (or 5-8s for native Veo/H3) + 1.5s cloned tail.
   - Deepgram Hermes (ura-2-hermes-en), 1.12x speed, ~2.75 words per second (165 WPM) staccato rhythm.

---

## 3. The Included Production Run: 112826

- **Directory**: out/the-pilot-who-got-sucked-out-of-the-cockpit-wind_20260912_112826/
- **Topic**: The 1990 British Airways Flight 5390 incident where Captain Tim Lancaster was sucked out of the cockpit window at 17,000 feet after a windshield blowout and held by his ankles by flight attendant Nigel Ogden until emergency landing.
- **Modality**: incident
- **Key Artifacts in this Run**:
  - script.json: 12-block narrative screenplay with exact duration, camera movement, visual continuity anchors, proof instructions, and character notes.
  - prompt_manifest.json: Complete Nano Banana Pro (Gemini 3 Pro Image) keyframe prompts and Vertex Veo 3.1 video motion prompts for each block.
  - sset_roster.json: Consistent character and environmental design anchors (Captain, Copilot, Crew, BAC 1-11 Cockpit, Aircraft Exterior, Decompression Cloud).
  - keyframe_reviews/: Admission audit files (kf01.json through kf13.json) containing visual inspection scores, prompt adherence checks, and fallback/repair logs.
  - captions.ass: Full Advanced SubStation Alpha caption styling with word-level highlight animations.
  - words.json: Exact Deepgram Hermes word timestamps.
  - sfx_cue_sheet.json: Foley sound effect cue sheet with peak-transient synchronization timestamps.
  - udio_bed_tension_pulse.wav: The incident-mode audio bed with low-end rumble and tension pulses.
  - 
un_output.txt: Full console output log of the generation pipeline.
  - state.json & 
un_manifest.json: Execution metadata and hash states.

---

## 4. Codebase Architecture

- **main.py**: CLI entry point with commands --auto-topic, --topic, --dry-run, --resume, --video, --image, --llm, --voice, --sfx.
- **pipeline.py**: The core production pipeline executing in sequential stages:
  1. Topic selection / Sourcing (TopicSelectionService)
  2. Narration script generation (ScriptEngineService)
  3. Voice synthesis & word-level timing (VoiceProvider)
  4. Dynamic timeline planning (uild_editorial_plan)
  5. Asset roster generation & character locking (AssetRosterService)
  6. Keyframe generation & admission audit (ImageProvider + review loops)
  7. Video generation via image-to-video / storyboard interpolation (VideoProvider)
  8. Foley sound effects & audio bed assembly (SFXService + AudioBedService)
  9. Final FFmpeg assembly, caption burning, and broadcast mastering (editor.py)
  10. Release packaging and media quality inspection (
elease.py)
- **config.py**: Central configuration, models, audio volume levels, retry policies, and thresholds.
- **editor.py**: FFmpeg filtergraph compiler. Enforces gte(time,t0)*lt(time,t1) gates and clip() clamps to prevent black-edge exposure or frame collisions.
- **
arrative.py**: LLM prompts for screenplay writing, prompt compilation, and visual refinement.
- **providers/**:
  - llm/: ertex_gemini.py, gemini_flash.py
  - image/: 
ano_banana_pro.py, low_agent_banana.py
  - ideo/: ertex_veo.py, low_agent_veo.py, al_video.py, motion_engine.py
  - oice/: deepgram_aura.py, elevenlabs.py, edge_tts.py
  - sfx/: elevenlabs.py, mmaudio.py, local_manifest.py
- **services/**:
  - sset_roster.py: Generates visual continuity reference cards.
  - mode_profile.py: Selects Incident, Mechanical, or Anatomical profiles.
  - script_engine.py: Directs narrative structure according to dynamic block bands.
  - sfx_dictionary.py & sfx.py: Foley catalog lookup and transient alignment.
  - udio_bed.py: Mood-matched synthetic audio bed generator.
- **DECISIONS.md**: Architecture Decision Record (ADR) history tracking all accepted, rejected, and abandoned pipeline experiments.
