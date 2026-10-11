---
name: audio-mastering-qa
description: Evaluate audio mix and Foley sound design for YouTube Shorts broadcast standards (-14 LUFS, -1.5 dBTP, -10 dBFS tactile Foley, zero vocal pumping, psychoacoustic Haas stereo balance).
---

# Audio Mastering QA

Use this skill when inspecting audio tracks, diagnosing loudness issues, or verifying voice-foley balance for Zack D. Films Shorts.

## Core Loudness & Dynamic Invariants (ADR-029)
1. **Integrated Loudness**: Must measure between -13.0 and -16.0 LUFS (optimal target: -14.0 LUFS via ebur128).
2. **True Peak**: Must never exceed -1.5 dBTP (LOUDNORM_TP = -1.5) to prevent digital clipping across mobile decoders.
3. **Foley Gain Staging**: Diegetic Foley micro-hits must be gain-staged to -10.0 dBFS (SFX_DEFAULT_GAIN_DB = -10.0), sitting gracefully behind narration voiceover.
4. **Anti-Pumping Protection**: Voiceover must NEVER be artificially dipped or sidechain-ducked for SFX (ADR-017). Background bed volume is fixed at MUSIC_VOLUME = 0.19 (-14.4 dBFS).
5. **ASMR Foley Frequency Contour**:
   - High-pass: 75 Hz (clean sub-rumble cut)
   - Mud cut: -2.0 dB @ 250 Hz (Q=1.5, vocal fundamental clearance)
   - ASMR presence: +2.0 dB @ 4.0 kHz (Q=1.8, crisp transient clarity)
   - Stereo imaging: Phase-controlled Haas widening (left_delay=2.05:right_delay=2.12 ms, side_gain=1.25) with middle_source=mid for mono compatibility.
6. **Decay Envelope**: Natural 0.55s-0.75s exponential decay (curve=exp) with 15ms quarter-sine attack (curve=qsin).

## Diagnostic Commands
- Run MCP measure_audio_loudness(audio_path) to measure integrated LUFS and True Peak.
- Run MCP analyze_audio_spectrum(audio_path) to verify dynamic range, RMS levels, and confirm clipping_detected is False.
