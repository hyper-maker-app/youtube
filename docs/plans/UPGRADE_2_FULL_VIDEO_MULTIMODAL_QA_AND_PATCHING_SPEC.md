# UPGRADE 2: TECHNICAL ARCHITECTURE & DESIGN SPECIFICATION

> **Current implementation notice (5 November 2026):** The design below is
> historical and is not evidence that full-video or audio multimodal review is
> implemented. The current opt-in `--video-qa` path sends three extracted still
> frames per block (25%, 50%, 75%) through `sampled_video_audit.py`. A passing
> result applies only to those sampled images; it does not establish motion,
> audio, A/V synchronization, or unseen-frame quality. The command defaults
> to off. When enabled, an uncertain or failed audit blocks final assembly.
> One selective patch pass is the supported maximum; a patched candidate must
> pass a subsequent audit before it replaces the original input. The boundary
> inspector and local media checks supply separate, limited evidence. Provider
> capacity, native full-video submission and the cost or savings estimates in
> the historical proposal remain unverified. Live operation must not be
> inferred from fixture tests. See the current master implementation plan for
> outstanding acceptance criteria.
> Final assembled A/V stream timing is checked separately when QA is enabled;
> this checks timestamps and duration, not semantic audio synchronization.
> Local media validation requires `ffprobe` or PyAV; if neither is available,
> the validation gate fails closed. Provider image batch capacity remains unverified.
> The still-frame adapter groups complete blocks into requests capped locally
> by `--video-qa-batch-size` (default 12 images, at least 3). This is an
> operator-configurable local ceiling, not a verified provider limit. At most
> 100 requests are permitted per audit. Missing or invalid batches fail closed;
> batch coverage and sample timestamps are recorded in the audit report.
## "Full-Video Native Multimodal Post-Audit & Selective Patching Engine"

**Version:** 4.5.0-ARCH  
**Author:** Video Multimodal QA & Selective Patching Specialist  
**Target Platform:** Grok Imagine Cinematic Studio / Google Flow CDP Physical Production Pipeline  
**Department:** Video Engineering & Multimodal Quality Assurance  
**Status:** Approved for Implementation  
**Specification Path:** `docs/plans/UPGRADE_2_FULL_VIDEO_MULTIMODAL_QA_AND_PATCHING_SPEC.md`  

---

## 1. Executive Summary & Problem Diagnosis

### 1.1 The Legacy Problem: "Static Triplet" Blind Spots & 90% Quota Waste
In the current Grok Imagine Cinematic Studio production pipeline (`engine/flow_bridge.py`), visual verification is performed strictly via **Transition Boundary Triplet QA** (`engine/services/boundary_inspector.py`). That system checks cross-block continuity across consecutive frames:
$$[ \text{Hero DNA Plate} ] \;\parallel\; [ \text{Block } N \text{ Exit Frame } (t = T - 0.04\text{s}) ] \;\parallel\; [ \text{Block } N+1 \text{ Entry Frame } (t = 0.04\text{s}) ]$$

While this boundary check successfully detects jump cuts, lighting leaps, and wardrobe shifts at cut points, it suffers from three critical architectural blind spots:
1. **Intra-Clip AI Glitches & Hallucinations:** Generative video engines (e.g., Google Veo / Flow, Wan 2.1, Kling, Grok Imagine Video) frequently establish pristine start and end frames while hallucinating in the temporal interior of the shot. Examples include: melting knuckles or six fingers at $t = 3.5\text{s}$, hands fusing into steering wheels, tools dissolving into clothing, and facial tearing during fast motion.
2. **Dynamic Camera Warping & Spatial Tearing:** During rapid camera moves (pans, tilts, whip pans), generative video models often exhibit severe fisheye distortions, rubbery stretching of backgrounds, and collapsing geometric perspective.
3. **Pacing Drag & Audio-Visual Desync:** Even with word-timed TTS, on-screen visual impacts (e.g., a vault door slamming shut, a weapon cocking, a flashlight dying) frequently occur $0.5\text{s} - 1.5\text{s}$ before or after the corresponding sound effect or spoken narration cue.
4. **The Catastrophic Re-Render Quota Penalty:** If an operator or automated review detects an intra-clip glitch in Scene 14 of an assembled 38-scene master, existing studio workflows require re-rendering the entire 300-second film. This burns **90%+ of unnecessary GPU compute, Google Flow CDP quota, and operator turnaround time**.

### 1.2 The Solution: Full-Video Multimodal Audit & Surgical Patching
This specification details **Upgrade 2: Full-Video Native Multimodal Post-Audit & Selective Patching Engine**, which establishes a two-stage closed-loop verification and surgical repair architecture:

```
+----------------------------------------------------------------------------------------------------+
|                Full-Video Native Multimodal Post-Audit & Selective Patching Engine                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   [ Rendered 38 Video Blocks ] + [ Master Audio Bed ] + [ Libass Subtitles ]                       |
|            |                                                                                       |
|            v                                                                                       |
|   +-------------------------------------------------------------+                                  |
|   | 1. Master Timeline Assembly (editor.py / flow_bridge.py)    |  --> 1080p Master Video (~200MB)  |
|   +-------------------------------------------------------------+                                  |
|            |                                                                                       |
|            v                                                                                       |
|   +-------------------------------------------------------------+                                  |
|   | 2. Lightweight Proxy & HUD Generator (proxy_generator.py)   |                                  |
|   |    - Downscales to 480p / 24fps libx264 (20-30 MB envelope) |                                  |
|   |    - Burns Scene ID HUD: Top [SCENE 14/38 | ID: sc14_power] |                                  |
|   |    - Burns SMPTE Timecode HUD: Bottom [01:14:12:08]         |                                  |
|   +-------------------------------------------------------------+                                  |
|            |                                                                                       |
|            v                                                                                       |
|   +--------------------------------------------------------------------------------------------+  |
|   | 3. Dual-Rail Multimodal Transport Gateway (multimodal_audit.py)                            |  |
|   |    - Rail 1 (Direct API): Google GenAI File API (Gemini 2.5 Flash / 3.1 Pro)               |  |
|   |    - Rail 2 (Chrome CDP 9223): gemini-web2api Local Daemon (Port 8085, Auto-Cookie Sync)    |  |
|   |    - Evaluates full 300s master video with Lead VFX Supervisor & Post-Director Persona    |  |
|   +--------------------------------------------------------------------------------------------+  |
|            |                                                                                       |
|            v Structured JSON Output (ClipDefect Schema)                                            |
|   +-------------------------------------------------------------+                                  |
|   | 4. Directive Triage & Decision Gate                         |                                  |
|   |    - PASS: Production sealed & finalized                    |                                  |
|   |    - RE_TIMING_ONLY: Micro-slip audio/video (0 render spend)|                                  |
|   |    - RE_RENDER_CLIP: Selective Patch Trigger                |                                  |
|   +-------------------------------------------------------------+                                  |
|            |                                                                                       |
|            v (If Critical Intra-Clip Defects Detected)                                             |
|   +--------------------------------------------------------------------------------------------+  |
|   | 5. Non-Destructive Selective Patch & Splice Engine (surgical_patcher.py)                   |  |
|   |    - Invalidates ONLY defective block cache (e.g. block_013.mp4 & block_013.mp4.cache.json)|  |
|   |    - Appends prompt_fix_instruction to scene prompt (Preserves 36 healthy scenes)          |  |
|   |    - Renders ONLY flagged scenes via Google Flow CDP (94.7% Quota Saved!)                  |  |
|   |    - Surgically splices new block into master timeline via FFmpeg Concat/Filtergraph      |  |
|   |    - Zero re-timing needed: Master Audio Bed & Libass Subtitles remain 100% sample-aligned |  |
|   |    - Circuit Breaker Guard: Max 1 or 2 patch passes (prevents infinite loops)              |  |
|   +--------------------------------------------------------------------------------------------+  |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Component 1: Lightweight Proxy Generation Pipeline (`proxy_generator.py`)

### 2.1 Bandwidth & Token Economics
Gemini multimodal video ingestion operates at approximately **258 tokens per second** of video.
- For a 300-second film: $300 \times 258 \approx 77,400\text{ tokens}$.
- Both the Google GenAI File API and Chrome CDP web sidecars require fast file upload. Sending an uncompressed 1080p master ($250 - 600\text{ MB}$) introduces network latency, upload timeouts, and high token serialization overhead.
- **Target Proxy Envelope:** **$20 - 30\text{ MB}$** for a full 300-second continuous assembly.

### 2.2 Transcode Envelope & Compression Parameters
To compress a 300-second 1080p video into $20 - 30\text{ MB}$ while preserving critical visual details (e.g. hand fingers, facial skin texture, edge artifacts, text HUD legibility):
- **Container:** MP4 (ISO/IEC 14496-14) with `+faststart` (places `moov` atom at the file beginning).
- **Video Stream:** `libx264`, 8-bit YUV420P.
- **Resolution:**
  - Landscape (16:9): $854 \times 480$ (Standard 480p).
  - Portrait (9:16 Shorts): $480 \times 854$.
- **Framerate:** 24.0 fps constant (eliminates variable framerate drift).
- **Target Video Bitrate:** $550\text{ kbps}$ average, $800\text{ kbps}$ peak.
- **Constant Rate Factor (CRF):** 28 with `-preset veryfast`.
- **GOP Structure:** `-g 48 -keyint_min 24 -bf 2` (keyframe every 2 seconds for optimal temporal seeking by Gemini).
- **Audio Stream:** AAC, $64\text{ kbps}$, Mono, $44,100\text{ Hz}$ (sufficient fidelity to evaluate narration alignment and SFX sync).
- **Mathematical File Size Check:**
  $$\text{Bitrate} = (550 + 64)\text{ kbps} = 614\text{ kbps} = 76.75\text{ KB/s}$$
  $$\text{File Size (300s)} = 76.75\text{ KB/s} \times 300\text{s} = 23,025\text{ KB} \approx 22.48\text{ MB}$$
  *Result:* Fits precisely within the $20 - 30\text{ MB}$ target envelope.

### 2.3 Dynamic Burned-In Scene HUD & Timecode Overlay
To ensure Gemini references defects unambiguously to the exact scene index and project scene ID, every frame in the proxy is branded with a non-intrusive dual-HUD:
1. **Top HUD (Scene Index & Identity):**
   `SCENE 14/38 [ID: sc14_power_grid] | DURATION: 6.0s`
2. **Bottom HUD (SMPTE Timecode):**
   `00:01:14:18 (24 FPS SMPTE)`

#### Why Subtitle-Based ASS Overlay is Mandatory Over `drawtext` Chains
Chaining 38 separate `drawtext` filters with `enable='between(t, t0, t1)'` creates a 5,000+ character filtergraph string. On Windows workstations, this causes:
- Command-line buffer overflow in `cmd.exe` / `subprocess`.
- Catastrophic escaping errors with non-ASCII directory paths.
- Severe CPU slowdown during FFmpeg graph initialization.

Instead, `proxy_generator.py` compiles an in-memory Advanced SubStation Alpha (`.ass`) file containing styled dialogue events that switch scene metadata instantaneously at exact scene boundaries.

#### Subtitle HUD Generator Implementation
```python
def generate_proxy_hud_ass(
    scenes: list[dict[str, Any]],
    output_ass: Path,
    aspect_ratio: str = "16:9",
) -> Path:
    """Generate high-contrast, low-token HUD overlay for Gemini Multimodal inspection."""
    is_landscape = (aspect_ratio == "16:9")
    res_x = 854 if is_landscape else 480
    res_y = 480 if is_landscape else 854
    font_size = 14 if is_landscape else 16

    header = f"""[Script Info]
Title: Multimodal QA Proxy HUD
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopHUD,Courier New,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,3,1,0,7,12,12,8,1
Style: BottomTC,Courier New,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,3,1,0,1,12,12,8,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    curr_t = 0.0

    for idx, sc in enumerate(scenes):
        dur = float(sc.get("veo_duration") or sc.get("duration", 6.0))
        t0 = float(sc.get("audio_t0", curr_t))
        t1 = float(sc.get("audio_t1", curr_t + dur))
        sc_id = str(sc.get("scene_id") or sc.get("id") or f"scene_{idx+1:02d}")

        t0_str = _format_ass_timestamp(t0)
        t1_str = _format_ass_timestamp(t1)

        hud_line = (
            f"{{\\b1}}SCENE {idx+1:02d}/{len(scenes):02d} [ID: {sc_id}]{{\\b0}} "
            f"| VEO_DUR: {dur:.1f}s | RANGE: {t0_str[:5]}-{t1_str[:5]}"
        )
        events.append(f"Dialogue: 0,{t0_str},{t1_str},TopHUD,,0,0,0,,{hud_line}")
        curr_t = t1

    output_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_ass
```

### 2.4 FFmpeg Proxy Execution Contract
```bash
ffmpeg -y -hide_banner \
  -i "out/project_omega/final_film.mp4" \
  -filter_complex "[0:v]scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,subtitles='proxy_hud.ass',drawtext=font='Courier New':timecode='00\:00\:00\:00':rate=24:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6:x=12:y=h-th-8[v_out];[0:a]aformat=channel_layouts=mono:sample_rates=44100[a_out]" \
  -map "[v_out]" -map "[a_out]" \
  -c:v libx264 -preset veryfast -crf 28 -g 48 -bf 2 \
  -c:a aac -b:a 64k \
  -movflags +faststart \
  "out/project_omega/final_film_proxy_480p.mp4"
```

---

## 3. Component 2: Multimodal Video Ingestion & Submission Engine (`multimodal_audit.py`)

### 3.1 Dual-Rail Transport Protocol Architecture
The engine provides transparent, automated transport selection with self-healing recovery across two transport rails:

```
[Start Video Multimodal Audit]
              │
              ▼
   ┌──────────────────────────────────────────────┐
   │ Check Authentication & Environment           │
   │ Is GEMINI_API_KEY / GOOGLE_API_KEY set?      │
   └──────────────────────┬───────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼ YES                       ▼ NO
   ┌─────────────────────────┐ ┌──────────────────────────────────────┐
   │ Rail 1: Google GenAI    │ │ Rail 2: Chrome CDP Sidecar           │
   │ Official File API       │ │ gemini-web2api on port 8085          │
   │ (Gemini 2.5 Flash / 3.1)│ │ (Extracts cookies via CDP port 9223) │
   └────────────┬────────────┘ └──────────────────┬───────────────────┘
                │                                 │
                ▼                                 ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │ Ingest MP4 -> Await 'ACTIVE' state -> Dispatch Multimodal Prompt │
   └──────────────────────────────────────────────────────────────────┘
```

#### Rail 1: Direct Google GenAI SDK (File API)
1. **Async File Upload:**
   ```python
   client = genai.Client(api_key=api_key)
   video_file = client.files.upload(file=proxy_path, mime_type="video/mp4")
   ```
2. **State Transition Loop:**
   Polls `client.files.get(name=video_file.name)` every 2 seconds until `state == "ACTIVE"` (state transitions: `PROCESSING` $\to$ `ACTIVE`). Fails with timeout if processing exceeds 60 seconds.
3. **Structured Content Generation:**
   Calls `client.models.generate_content(...)` with:
   - `model = "gemini-2.5-flash"` (or `gemini-3.1-pro` when available)
   - `contents = [video_file, system_directive_prompt]`
   - `config = types.GenerateContentConfig(response_mime_type="application/json")`
4. **Guaranteed Cloud Storage Cleanup:**
   An explicit `finally` block issues `client.files.delete(name=video_file.name)` to prevent file accumulation on Google Cloud.

#### Rail 2: Local Chrome CDP Sidecar (`gemini-web2api`)
1. **Zero-API-Key Operation:**
   Leverages the user's active Google Pro/Advanced subscription logged in Chrome on CDP port 9223.
2. **Automated Daemon Health Check:**
   Queries `http://127.0.0.1:8085/v1/models`. If port 8085 is closed or refused:
   - Auto-launches Chrome daemon on port 9223 via `keep_chrome_alive.py`.
   - Extracts active `https://gemini.google.com` session cookies via Playwright CDP.
   - Launches `gemini-web2api.exe` on port 8085.
3. **Chunked Video Dispatch:**
   Transfers the proxy file to the local endpoint via multipart form POST or streaming base64 chunks, receiving streaming SSE response parsed into the final JSON payload.

### 3.2 Lead VFX Supervisor & Post-Production Director Persona
The multimodal model is initialized with a specialized system prompt enforcing uncompromising visual standards.

```text
You are the Lead Visual Effects (VFX) Supervisor & Post-Production Quality Director for Grok Imagine Cinematic Studio.
You are conducting a strict, comprehensive post-audit of the fully assembled continuous master film.

CRITICAL TIMELINE INSTRUCTIONS:
1. You must watch the entire timeline from second 00:00 to the end.
2. The video has a burned HUD:
   - TOP HUD: "SCENE [idx]/[total] [ID: scene_id] | VEO_DUR: [sec]s | RANGE: [t0]-[t1]"
   - BOTTOM HUD: SMPTE Timecode "HH:MM:SS:FF"
3. Reference scenes STRICTLY by the exact burned Scene ID and Scene Index.

EVALUATION CRITERIA (INTRA-CLIP ANOMALIES):
You are hunting for temporal defects that occur INSIDE clips:
1. AI VISUAL GLITCHES & ANATOMY COLLAPSE:
   - Fingers melting, hands warping into steering wheels, tools dissolving into garments.
   - Flesh tearing, asymmetric pupil movement, vanishing limbs, or floating phantom objects.
2. CAMERA WARPING & PERSPECTIVE TEARING:
   - Rubber-band stretching of background walls during pans.
   - Unnatural warping or fisheye distortion of rigid straight edges (door frames, steel beams).
3. AUDIO-VISUAL & ACTION ASYNCHRONY:
   - Spoken narration or sound effect occurs >0.5 seconds before/after the visual event (e.g. door slam, breath gasp, tool strike).
4. TEMPORAL TEARING & STAGNATION:
   - Frozen video frames lasting >1.5 seconds during intended action.
   - Jittery frame-rate cadence drops.

DECISION PROTOCOL:
- If a clip has critical visual deformation, mark action_directive="RE_RENDER_CLIP".
- Provide an actionable "prompt_fix_instruction" detailing EXACTLY what prompt keywords to add (e.g., "enforce static rigid grip on metal handle, high shutter speed, zero anatomical deformation").
- If the entire film is clean, mark overall_verdict="PASS" and defects=[].

OUTPUT FORMAT:
Return ONLY valid JSON strictly adhering to the FullVideoAuditReport schema.
```

---

## 4. Component 3: Structured Defect Schema & Action Directives

### 4.1 Complete JSON Data Contract
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FullVideoAuditReport",
  "type": "object",
  "required": [
    "audit_id",
    "project_title",
    "total_scenes_inspected",
    "master_quality_score",
    "overall_verdict",
    "defects_detected",
    "defects",
    "patch_plan_summary"
  ],
  "properties": {
    "audit_id": { "type": "string" },
    "project_title": { "type": "string" },
    "total_scenes_inspected": { "type": "integer", "minimum": 1 },
    "master_quality_score": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "overall_verdict": {
      "type": "string",
      "enum": ["PASS", "CONDITIONAL_PATCH_REQUIRED", "FAIL_CRITICAL"]
    },
    "defects_detected": { "type": "integer", "minimum": 0 },
    "defects": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "scene_index",
          "scene_id",
          "timestamp_range",
          "defect_type",
          "severity",
          "action_directive",
          "defect_description",
          "prompt_fix_instruction"
        ],
        "properties": {
          "scene_index": { "type": "integer", "description": "1-based index matching burned HUD" },
          "scene_id": { "type": "string", "description": "Exact scene ID from burned HUD" },
          "timestamp_range": {
            "type": "string",
            "pattern": "^\\d{2}:\\d{2}\\.\\d{3}\\s*-\\s*\\d{2}:\\d{2}\\.\\d{3}$",
            "example": "01:14.200 - 01:18.500"
          },
          "defect_type": {
            "type": "string",
            "enum": [
              "ai_visual_glitch",
              "anatomy_mutation",
              "camera_warping",
              "prop_dissolve",
              "audio_video_desync",
              "pacing_drag",
              "temporal_tearing"
            ]
          },
          "severity": {
            "type": "string",
            "enum": ["critical", "moderate", "advisory"]
          },
          "action_directive": {
            "type": "string",
            "enum": ["RE_RENDER_CLIP", "RE_TIMING_ONLY", "PASS"]
          },
          "defect_description": {
            "type": "string",
            "description": "Exacting description of the visual failure"
          },
          "prompt_fix_instruction": {
            "type": "string",
            "description": "Actionable prompt engineering fix for re-render"
          }
        }
      }
    },
    "patch_plan_summary": {
      "type": "object",
      "required": ["total_clips_to_rerender", "scenes_to_patch", "estimated_quota_savings_pct"],
      "properties": {
        "total_clips_to_rerender": { "type": "integer" },
        "scenes_to_patch": { "type": "array", "items": { "type": "string" } },
        "estimated_quota_savings_pct": { "type": "number" }
      }
    }
  }
}
```

### 4.2 Severity Routing Matrix & Action Triggers

| Severity Level | Defect Characteristics | Action Directive | Engine Execution |
| :--- | :--- | :--- | :--- |
| **`critical`** | Melting hand, 6 fingers, facial collapse, structural tearing, disappearing weapon | `RE_RENDER_CLIP` | **Mandatory re-render.** Invalidates block cache, mutates prompt, dispatches Google Flow CDP re-render. |
| **`moderate`** | Subtle hand-cloth blending, slight camera jitter, minor shadow pop | `RE_RENDER_CLIP` (if budget allows) / `PASS` | Re-renders if flagged clips $\le 2$; otherwise logged to report without halting pipeline. |
| **`moderate`** | Sound effect triggers $0.6\text{s}$ before door visual impact | `RE_TIMING_ONLY` | Zero GPU cost. Dispatches FFmpeg audio pad/trim adjustment without re-rendering video. |
| **`advisory`** | Mild grain inconsistency, slight lighting shift across cut | `PASS` | Logged into `audit_report.json` as editorial note; zero corrective action taken. |

---

## 5. Component 4: Non-Destructive Selective Re-Render & Surgical Splicing (`surgical_patcher.py`)

### 5.1 The 90%+ Quota Savings Mathematical Proof
Consider a standard 300-second cinematic film consisting of 38 scenes:
- Total scenes: $N = 38$
- Defective scenes identified by multimodal audit: $K = 2$ (e.g. Scene 10 and Scene 24)
- Untouched healthy scenes: $N - K = 36$
- Quota and Compute Savings:
  $$\text{Quota Savings} = \frac{N - K}{N} = \frac{38 - 2}{38} = \frac{36}{38} \approx 94.74\%$$
  $$\text{Time Savings} = 38 \times 45\text{s} \to 2 \times 45\text{s} = 28.5\text{ min} \to 1.5\text{ min} \;(94.7\%\text{ reduction})$$

### 5.2 Targeted Cache Invalidation & Prompt Mutation
When `surgical_patcher.py` receives a defect report targeting Scene 10 (`block_009.mp4`):
1. **Targeted Invalidation:**
   The engine deletes **only**:
   - `out_dir/blocks/block_009.mp4`
   - `out_dir/blocks/block_009.mp4.cache.json`
   All other 37 blocks retain their verified cache fingerprints.
2. **Prompt Mutation Gateway:**
   The engine reads `aligned_scenes[9]` and reinforces the prompt with `prompt_fix_instruction`:
   ```python
   def mutate_scene_prompt(scene: dict[str, Any], fix_instruction: str) -> dict[str, Any]:
       patched = dict(scene)
       original_prompt = patched.get("visual_prompt", "")
       # Surgical prompt reinforcement
       patched["visual_prompt"] = f"{original_prompt}, {fix_instruction}, anatomical stability, rigid hands"
       patched["prompt_patched_at"] = time.time()
       return patched
   ```
3. **Selective Flow Re-Render:**
   Dispatches `generate_single_block(...)` on Google Flow CDP for index 9 only.

### 5.3 FFmpeg Non-Destructive Surgical Splicing
Because each block's duration in Google Flow CDP is strictly locked to the voiceover timeline (`veo_duration = audio_t1 - audio_t0`), the replacement clip possesses the **exact same temporal duration** as the defective clip it replaces.

#### Audio and Subtitle Invariance Guarantee
- **Broadcast Audio Bed (`master_audio_3layer.wav`):** TTS voiceover, background music ducking, and procedural SFX foley are rendered against the continuous timeline. Because duration $(t_1 - t_0)$ does not change, **audio is untouched**.
- **Libass Karaoke Subtitles (`captions.ass`):** Word-level subtitle timestamps are absolute. Because scene boundaries do not shift, **subtitles remain 100% synchronized**.

#### FFmpeg Concat & Multiplex Splicing Algorithm
```python
def surgically_splice_timeline(
    master_video_path: Path,
    replacement_blocks: dict[int, Path],  # {scene_index_0based: new_block_path}
    all_block_paths: list[Path],
    output_path: Path,
    master_audio_path: Path,
    captions_path: Path | None = None,
) -> Path:
    """Reassemble master video with replaced blocks without re-rendering healthy scenes."""
    updated_blocks = list(all_block_paths)
    for idx, new_path in replacement_blocks.items():
        if not new_path.is_file():
            raise FileNotFoundError(f"Replacement block missing: {new_path}")
        updated_blocks[idx] = new_path

    # Build concat demuxer manifest
    concat_list = output_path.parent / "splice_concat_list.txt"
    manifest_lines = [f"file '{b.resolve().as_posix()}'" for b in updated_blocks]
    concat_list.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    ffmpeg_bin = config.resolve_ffmpeg()
    cmd = [
        ffmpeg_bin, "-y", "-hide_banner",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(master_audio_path),
    ]

    filter_complex = ["[0:v]fps=30,format=yuv420p[v_base]"]
    current_v = "[v_base]"

    if captions_path and captions_path.is_file():
        clean_ass = captions_path.resolve().as_posix().replace(":", "\\:")
        filter_complex.append(f"{current_v}subtitles='{clean_ass}'[v_sub]")
        current_v = "[v_sub]"

    cmd.extend([
        "-filter_complex", ";".join(filter_complex),
        "-map", current_v,
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart",
        str(output_path),
    ])

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg surgical splicing failed:\n{proc.stderr}")

    return output_path
```

### 5.4 Loop Bounds & Circuit Breaker Guard
To prevent infinite rendering loops and runaway API costs:
- **`MAX_PATCH_PASSES = 1` (Configurable to 2 max):**
  If a re-rendered clip still fails post-audit on Pass 2, the circuit breaker engages:
  1. The engine logs `[CIRCUIT_BREAKER] Scene {id} failed 2 corrective passes.`
  2. Fallback Option A (Automated): Replaces the failing block with a dynamic Ken Burns pan/zoom on the corresponding high-resolution Hero Plate (`render_ken_burns_block`).
  3. Fallback Option B (Human Waiver): Issues an alert and passes the film with `audit_status="CONDITIONAL_PASS"`.

---

## 6. Component 5: Zero-Hardcode & Architecture Safety (ADR-090 Compliance)

### 6.1 Zero-Hardcode Invariant Enforcement
In strict compliance with ADR-090 and repository rules:
1. **Zero Narrative Strings in Code:** No character names, dialogue snippets, scene plotlines, or genre descriptions may exist in `proxy_generator.py`, `multimodal_audit.py`, or `surgical_patcher.py`.
2. **Dynamic Invariants:** All visual parameters, thresholds, and prompts are injected dynamically from:
   - Input handoff JSON (`sequences/*_handoff.json`).
   - Markdown skill directives (`.grok/skills/*.md`).
   - Configuration dataclasses (`FullVideoAuditConfig`).

### 6.2 Configuration Contract (`engine/config.py`)
```python
@dataclass
class FullVideoAuditConfig:
    enabled: bool = True
    target_proxy_resolution: str = "854x480"
    proxy_crf: int = 28
    proxy_video_bitrate_kbps: int = 550
    proxy_audio_bitrate_kbps: int = 64
    max_patch_passes: int = 1
    fail_mode: str = "warn_and_pass"  # "warn_and_pass" | "fail_closed"
    gemini_model: str = "gemini-2.5-flash"
    timeout_seconds: float = 120.0
    cdp_port: int = 9223
    web2api_port: int = 8085
```

### 6.3 Clean Failure Mode Handling
- **`warn_and_pass` (Default Production Mode):**
  If network connectivity drops or the Gemini API times out:
  - The engine does not abort the production.
  - Falls back to local OpenCV structural freeze-frame and black-frame detection (`verify_block_quality`).
  - Writes `audit_report.json` with `overall_verdict: "PASS_UNAUDITED_OFFLINE"`.
- **`fail_closed` (Broadcast Strict Mode):**
  - Activated via `--strict-audit`.
  - Halts the pipeline with an explicit exit code if full multimodal audit cannot be verified.

---

## 7. File Layout & Integration Roadmap

```
engine/
├── services/
│   ├── proxy_generator.py      # [NEW] 480p proxy downscaling & ASS HUD generation
│   ├── multimodal_audit.py     # [NEW] Dual-rail Gemini submission & JSON defect parser
│   ├── surgical_patcher.py     # [NEW] Targeted cache invalidation & FFmpeg splicing
│   ├── boundary_inspector.py   # [EXISTING] Step 2 Transition Boundary Triplet QA
│   └── editor.py               # [EXISTING] Master assembly & audio mixing
├── providers/
│   └── gemini_webapi.py        # [EXISTING] Chrome CDP 9223 & port 8085 daemon
└── flow_bridge.py              # [INTEGRATION] Calls proxy + audit + surgical patcher
```

### 7.1 Integration Hook in `flow_bridge.py`
Immediately following Step 3 (`editor.render`), the engine executes Step 3.5:
```python
# Step 3.5: Full-Video Multimodal Post-Audit & Selective Patching
if audit_config.enabled and not dry_run:
    logger.info("[3.5] Initiating Full-Video Multimodal Post-Audit (Proxy & Gemini 2.5 Flash)...")
    proxy_path = await generate_audit_proxy(final_mp4, aligned_scenes, out_dir)
    audit_report = await audit_master_video(proxy_path, project_title, aligned_scenes)
    
    if audit_report.overall_verdict == OverallVerdict.CONDITIONAL_PATCH_REQUIRED:
        logger.warning(f"Audit flagged {len(audit_report.defects)} defect(s). Commencing surgical patch...")
        final_mp4 = await execute_surgical_patch_loop(
            master_video_path=final_mp4,
            audit_report=audit_report,
            aligned_scenes=aligned_scenes,
            out_dir=out_dir,
            max_passes=audit_config.max_patch_passes,
        )
```

---

## 8. Verification & Test Plan

1. **Unit Test (`tests/test_proxy_generator.py`):**
   - Asserts proxy file size $\le 30.0\text{ MB}$ for a 300s source video.
   - Asserts `proxy_hud.ass` contains exactly 38 dialogue lines matching scene durations.
2. **Integration Test (`tests/test_surgical_patcher.py`):**
   - Injects a simulated defect into `block_002.mp4`.
   - Replaces `block_002.mp4` with a corrected block.
   - Asserts resulting spliced video matches original length $\pm 0.04\text{s}$ and audio bed is byte-identical.
3. **Zero-Hardcode Lint (`scripts/lint_zero_hardcode.py`):**
   - Scans all new modules to ensure zero hardcoded creative narrative strings exist.

---

## 9. Conclusion

Upgrade 2 transforms Grok Imagine Cinematic Studio from a local boundary-checking pipeline into a true **closed-loop Hollywood-grade VFX post-production facility**. By auditing the complete temporal timeline and executing surgical re-renders, the studio delivers flawless visual consistency while saving **over 94% of generative render quota and turn time**.
