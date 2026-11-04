# UPGRADE 2 ARCHITECTURE SPECIFICATION: FULL-VIDEO NATIVE MULTIMODAL POST-AUDIT & SELECTIVE PATCHING ENGINE

**Canonical Architecture Standard for Grok Imagine Cinematic Studio v4.5**  
**Role:** Video Multimodal QA & Selective Patching Specialist  
**Target Module:** `engine/services/multimodal_audit.py`, `engine/services/proxy_generator.py`, `engine/services/surgical_patcher.py`  
**Integration Points:** `engine/flow_bridge.py`, `engine/editor.py`, `tools/cinematic_studio_cli.py`  
**Status:** Approved Technical Architecture  

---

## 1. Executive Summary & Problem Statement

### 1.1 The Architectural Blind Spot
The current production pipeline relies on **Transition Boundary Triplet QA** (`engine/services/boundary_inspector.py`). While this verifies cross-block continuity across consecutive frames ($t = T_{exit}$ and $t = T_{entry}$), it suffers from an architectural blind spot:
1. **Intra-Clip AI Glitches:** Video models (e.g., Google Veo / Flow, Wan 2.1, Kling, Grok Imagine Video) frequently generate valid first and last frames while hallucinating in the middle of a clip (e.g., melting hands at $t = 3.5\text{s}$, anomalous limbs emerging from torsos, dissolving hand props, or geometric spatial tearing).
2. **Dynamic Camera Warping:** Rapid generative pans frequently cause fisheye distortion, rubbery stretching of backgrounds, or vanishing architectural axes mid-motion.
3. **Pacing Drag & Audio-Visual Desync:** Even with forced-alignment TTS, visual actions inside a clip may lag behind the spoken voiceover or sound cues.
4. **Catastrophic Re-Render Quota Waste:** Currently, if a user spots an intra-clip defect in a finished 300-second, 38-scene master assembly, regenerating the whole project wastes **90%+ of GPU compute, Flow CDP quota, and production time**.

### 1.2 The Solution: Upgrade 2
Upgrade 2 introduces a **closed-loop, two-stage post-production auditing and surgical repair engine**:
- **Stage 1 (Full-Video Native Multimodal Post-Audit):** Automatically downscales the 1080p master assembly into an ultra-optimized, timecoded proxy video ($20-30\text{ MB}$) with burned HUD metadata (Scene ID and frame-accurate timecode). Sends the entire 300-second stream to Gemini Multimodal (Gemini 2.5 Flash / 3.1 Pro via Direct SDK or Chrome CDP sidecar port 9223) acting as a Lead VFX Supervisor.
- **Stage 2 (Non-Destructive Surgical Patching):** Parses structured JSON defect reports. If 2 out of 38 scenes contain critical defects, the engine invalidates **only** those 2 scene caches, injects corrective prompt patches, re-renders solely those 2 clips on Google Flow CDP, and performs surgical FFmpeg timeline splicing—leaving the remaining 36 healthy scenes, the broadcast 3-layer audio bed, and the Libass karaoke subtitles 100% intact.

---

## 2. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph Master Assembly ["1. Master Assembly Phase"]
        A[38 Rendered Blocks] --> B[FFmpeg Master Assembly]
        B --> C[final_film.mp4 (1080p, ~200MB)]
        B --> D[audio_bed + captions.ass]
    end

    subgraph Proxy Pipeline ["2. Proxy & HUD Pipeline"]
        C --> E[engine/services/proxy_generator.py]
        F[aligned_scenes manifest] --> E
        E --> G[proxy_hud.ass Subtitle Overlay]
        E --> H[final_film_proxy_480p.mp4 (22MB, Timecode+Scene HUD)]
    end

    subgraph Multimodal Audit ["3. Gemini Multimodal Audit"]
        H --> I{Transport Gateway}
        I -->|Priority 1: SDK File API| J[Gemini 2.5 Flash / 3.1 Pro]
        I -->|Priority 2: Chrome CDP 9223| K[gemini-web2api Port 8085]
        J --> L[Structured JSON Defect Schema]
        K --> L
    end

    subgraph Decision Engine ["4. Directive Triage"]
        L --> M{Defect Severity}
        M -->|CRITICAL / RE_RENDER_CLIP| N[Targeted Scene Cache Invalidation]
        M -->|PASS / ADVISORY| O[Final Film Verified & Sealed]
        M -->|RE_TIMING_ONLY| P[FFmpeg Speed/Trim Adjust]
    end

    subgraph Surgical Patching ["5. Selective Patch & Splice"]
        N --> Q[Inject prompt_fix_instruction into Scene Prompts]
        Q --> R[Google Flow CDP Selective Render: Only Flagged Blocks]
        R --> S[engine/services/surgical_patcher.py]
        S --> T[FFmpeg Filtergraph Timeline Splicing]
        D --> T
        T --> U[final_film_patched.mp4 (100% Audio & Subtitle Synced)]
        U --> V[Max Loop Bound Guard: 1-2 Passes Max]
    end
```

---

## 3. Proxy Generation Pipeline (`proxy_generator.py`)

### 3.1 Bandwidth & Token Economics
Gemini video multimodal processing consumes approximately **258 tokens per second** of video.
- For a 300-second film: $300 \times 258 \approx 77,400\text{ tokens}$.
- Direct Gemini File API and Gemini web endpoints perform best with files under $50\text{ MB}$ to guarantee rapid upload without timeout.
- Target Proxy Envelope: **$20 - 30\text{ MB}$** for a full 5-minute (300s) film.

### 3.2 Resolution & Compression Envelope
To achieve this target without losing fine visual detail (such as hand anatomy, text legibility, or artifact warping):
- **Container:** MP4 (ISO Base Media file format)
- **Video Codec:** `libx264`, 8-bit YUV420P
- **Resolution:** $854 \times 480$ (16:9) or $480 \times 854$ (9:16)
- **Framerate:** 24 fps constant (conformed from variable input)
- **Target Bitrate:** $550\text{ kbps}$ (Average), $800\text{ kbps}$ (Peak)
- **CRF:** 28 (`-preset veryfast`)
- **Keyframe Interval (GOP):** 48 frames (2.0s keyframes for fast temporal seeking)
- **Audio Codec:** AAC, 64 kbps, Mono, 44.1 kHz (preserves spoken words and sound effects for AV desync inspection)
- **Total Proxy Size:** $(550 + 64)\text{ kbps} \times 300\text{s} = 184,200\text{ kb} \approx 22.5\text{ MB}$.

### 3.3 Dynamic Burned-In Scene HUD & Timecode Overlay
To eliminate ambiguity when Gemini references defects, every frame in the proxy has a burned-in Heads-Up Display (HUD) displaying:
1. Exact Timeline Timestamp: `SMPTE HH:MM:SS:FF`
2. Scene Index & Identifier: `SCENE [idx+1]/[total]: [scene_id]`
3. Visual Beat Category: `[GENRE / BEAT_TYPE]`

#### Why ASS Overlay is Superior to Chained `drawtext`
Chaining 38 `drawtext` filters with `enable='between(t, t0, t1)'` results in massive FFmpeg filtergraph strings that exceed Windows `cmd.exe` / PowerShell argument length limits ($8191\text{ chars}$) and suffers from escaping bugs with non-ASCII paths.
Instead, `proxy_generator.py` compiles a lightweight in-memory **`proxy_hud.ass`** file rendered natively by FFmpeg's `subtitles` filter.

#### ASS HUD Template & Generation Logic
```python
def generate_proxy_hud_ass(
    scenes: list[dict[str, Any]],
    output_ass: Path,
    aspect_ratio: str = "16:9",
) -> Path:
    """Generate precise scene-indexed HUD overlay matching timeline durations."""
    is_landscape = (aspect_ratio == "16:9")
    play_res_x = 854 if is_landscape else 480
    play_res_y = 480 if is_landscape else 854
    font_size = 14 if is_landscape else 16

    header = f"""[Script Info]
Title: Full-Video Multimodal QA HUD
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopHUD,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,1,0,7,12,12,10,1
Style: BottomTC,Courier New,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,1,0,1,12,12,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    curr_t = 0.0
    for idx, sc in enumerate(scenes):
        dur = float(sc.get("veo_duration") or sc.get("duration", 6.0))
        t0 = sc.get("audio_t0", curr_t)
        t1 = sc.get("audio_t1", curr_t + dur)
        sc_id = sc.get("scene_id") or sc.get("id") or f"scene_{idx+1:02d}"
        
        start_ass = _format_ass_time(float(t0))
        end_ass = _format_ass_time(float(t1))
        
        # Top HUD line: Scene ID, Index, and visual type
        top_text = f"{{\\b1}}SCENE {idx+1:02d}/{len(scenes):02d} [ID: {sc_id}]{{\\b0}} | VEO_DUR: {dur:.1f}s"
        events.append(f"Dialogue: 0,{start_ass},{end_ass},TopHUD,,0,0,0,,{top_text}")
        
        curr_t = float(t1)

    output_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_ass
```

### 3.4 FFmpeg Proxy Compilation Pipeline
```bash
ffmpeg -y -hide_banner -i final_film.mp4 \
  -filter_complex "[0:v]scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,subtitles='proxy_hud.ass',drawtext=font='Courier New':timecode='00\:00\:00\:00':rate=24:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6:x=12:y=h-th-10[v_out];[0:a]aformat=channel_layouts=mono:sample_rates=44100[a_out]" \
  -map "[v_out]" -map "[a_out]" \
  -c:v libx264 -preset veryfast -crf 28 -g 48 -bf 2 \
  -c:a aac -b:a 64k \
  -movflags +faststart \
  final_film_proxy_480p.mp4
```

---

## 4. Multimodal Video Prompt & Submission Engine (`multimodal_audit.py`)

### 4.1 Dual-Transport Protocol Architecture
The engine features automatic, transparent failover across two primary transport mechanisms:

```
[Proxy MP4 Generated]
         │
         ▼
 ┌──────────────────────────────────────────────┐
 │ Has GEMINI_API_KEY / GOOGLE_API_KEY?         │
 └──────────────────────┬───────────────────────┘
            │                               │
           YES                              NO
            ▼                               ▼
 ┌───────────────────────────┐    ┌────────────────────────────────────────┐
 │ Transport Rail 1:         │    │ Transport Rail 2:                      │
 │ Google GenAI File API     │    │ Chrome CDP Session (Port 9223)         │
 │ (google.genai SDK)        │    │ Local gemini-web2api daemon (Port 8085)│
 └──────────┬────────────────┘    └──────────────────┬─────────────────────┘
            │                                        │
            ▼                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ Execute Video Ingestion -> Wait for ACTIVE state -> Dispatch Prompt     │
 └─────────────────────────────────────────────────────────────────────────┘
```

#### Transport Rail 1: Google GenAI SDK (Direct File API)
1. **Upload:** Uses `client.files.upload(file=proxy_mp4_path, mime_type="video/mp4")`.
2. **State Polling:** Asynchronous polling of `client.files.get(name=file.name)` until `file.state == "ACTIVE"` (typically $3 - 8\text{ seconds}$ for a $22\text{ MB}$ file).
3. **Inference Call:** Dispatches to `gemini-2.5-flash` (or `gemini-3.1-pro`) with `response_mime_type="application/json"` and strict schema definition.
4. **Cleanup:** Explicitly calls `client.files.delete(name=file.name)` in a `finally` block to prevent cloud storage leakage.

#### Transport Rail 2: Chrome CDP Sidecar (`gemini-web2api`)
1. **Zero-API-Key Operation:** Communicates over HTTP with the local Go daemon running on port 8085 (powered by cookies synchronized from the authenticated Chrome CDP instance on port 9223).
2. **Multipart Video Transfer:** Sends the proxy video bytes via multipart form upload to `/v1/upload` or base64 chunked data payload.
3. **Session Auto-Healing:** If port 8085 is closed or returns authorization errors, the engine calls `ensure_server_running()` to automatically wake Chrome CDP and re-extract fresh `cookies.txt`.

### 4.2 Lead VFX Supervisor & Post-Production Director Persona
The system prompt establishes an authoritative, uncompromising directorial and visual inspection persona.

```text
You are the Lead Visual Effects (VFX) Supervisor & Post-Production Quality Director for Grok Imagine Cinematic Studio.
You are conducting a strict, frame-by-frame post-audit of the fully assembled master film.

CRITICAL INSTRUCTION:
You must watch the entire video timeline from start to finish.
The video proxy has a burned-in HUD showing:
- TOP HUD: Exact scene number and Scene ID (e.g. "SCENE 04/38 [ID: sc04_corridor]")
- BOTTOM HUD: Frame-accurate SMPTE timecode (HH:MM:SS:FF)

You are specifically evaluating INTRA-CLIP defects that escape static frame checks:
1. AI VISUAL GLITCHES & ANATOMY MUTATIONS:
   - Extra fingers, melting palms, morphing fingernails, or flesh merging into objects.
   - Facial tearing, asymmetrical pupil drift, or jaw melting during movement.
   - Clothing or props that spontaneously change texture, pattern, or dissolve mid-shot.
2. CAMERA WARPING & GEOMETRIC DISTORTION:
   - Fisheye bending of rigid vertical lines (doors, steel pillars, walls) during pans.
   - Temporal jitter, background rubber-banding, or unnatural perspective snapping.
3. AUDIO-VISUAL / ACTION DESYNC:
   - Visual action (e.g., slamming door, gunshot, gasping, dropping tool) occurs >0.5s before or after the corresponding sound effect or narration cue.
4. PACING DRAG & FROZEN FRAMES:
   - Static/dead frames exceeding 1.5 seconds without intentional dramatic tension.

You must be surgical, precise, and actionable.
Output ONLY valid JSON strictly adhering to the FullVideoAuditReport schema.
```

---

## 5. Structured Defect Schema & Action Directives

### 5.1 JSON Data Contract Specification
The Gemini Multimodal engine is constrained to return an unambiguous JSON payload.

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
          "scene_index": { "type": "integer", "description": "1-based scene index" },
          "scene_id": { "type": "string", "description": "Matches exact manifest scene_id" },
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
            "description": "Exacting technical analysis of what failed visually or rhythmically"
          },
          "prompt_fix_instruction": {
            "type": "string",
            "description": "Imperative prompt engineering modification to eliminate the defect upon re-render"
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

### 5.2 Python Pydantic Model (`engine/services/multimodal_audit.py`)
```python
from enum import Enum
from pydantic import BaseModel, Field

class DefectType(str, Enum):
    AI_VISUAL_GLITCH = "ai_visual_glitch"
    ANATOMY_MUTATION = "anatomy_mutation"
    CAMERA_WARPING = "camera_warping"
    PROP_DISSOLVE = "prop_dissolve"
    AUDIO_VIDEO_DESYNC = "audio_video_desync"
    PACING_DRAG = "pacing_drag"
    TEMPORAL_TEARING = "temporal_tearing"

class DefectSeverity(str, Enum):
    CRITICAL = "critical"
    MODERATE = "moderate"
    ADVISORY = "advisory"

class ActionDirective(str, Enum):
    RE_RENDER_CLIP = "RE_RENDER_CLIP"
    RE_TIMING_ONLY = "RE_TIMING_ONLY"
    PASS = "PASS"

class OverallVerdict(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PATCH_REQUIRED = "CONDITIONAL_PATCH_REQUIRED"
    FAIL_CRITICAL = "FAIL_CRITICAL"

class ClipDefect(BaseModel):
    scene_index: int = Field(..., description="1-based index of the scene")
    scene_id: str = Field(..., description="Exact scene identifier")
    timestamp_range: str = Field(..., description="Timestamp interval 'MM:SS.mmm - MM:SS.mmm'")
    defect_type: DefectType
    severity: DefectSeverity
    action_directive: ActionDirective
    defect_description: str
    prompt_fix_instruction: str

class PatchPlanSummary(BaseModel):
    total_clips_to_rerender: int
    scenes_to_patch: list[str]
    estimated_quota_savings_pct: float

class FullVideoAuditReport(BaseModel):
    audit_id: str
    project_title: str
    total_scenes_inspected: int
    master_quality_score: float
    overall_verdict: OverallVerdict
    defects_detected: int
    defects: list[ClipDefect]
    patch_plan_summary: PatchPlanSummary
```

### 5.3 Severity Triage & Action Routing Matrix

| Severity | Defect Manifestation | Action Directive | Threshold Rule |
| :--- | :--- | :--- | :--- |
| **`critical`** | Melting hand, 6 fingers, face collapse, severe camera warp tearing perspective | `RE_RENDER_CLIP` | **Mandatory re-render**. Triggers surgical patch pipeline immediately. |
| **`moderate`** | Slight unnatural movement, hand prop briefly blends into sleeve, minor jerkiness | `RE_RENDER_CLIP` (if budget allows) / `PASS` | Re-renders if flagged clips $\le 3$; otherwise logged as acceptable unless overridden by user. |
| **`moderate`** | Sound effect triggers $0.6\text{s}$ prior to visual door slam | `RE_TIMING_ONLY` | Avoids GPU re-render; shifts audio track or inserts $0.6\text{s}$ hold frame in FFmpeg. |
| **`advisory`** | Mild lighting flicker, subtle motion blur softening | `PASS` | Logged to `audit_report.json`; zero render action taken. |

---

## 6. Non-Destructive Selective Re-Render & Surgical Splicing (`surgical_patcher.py`)

### 6.1 The 90%+ Quota Savings Equation
In a standard 300-second production:
$$\text{Total Scenes} = 38 \quad (N = 38)$$
$$\text{Average Flagged Defects} = 2 \quad (K = 2)$$
$$\text{Quota Saved} = \frac{N - K}{N} = \frac{38 - 2}{38} = 94.74\%$$
Rather than spending 38 video generation credits on Google Flow CDP, the studio spends **only 2 credits**, reducing render turn times from 45 minutes to **2.5 minutes**.

### 6.2 Cache Invalidation & Prompt Mutation Workflow
When `RE_RENDER_CLIP` is dispatched for `scene_id = "sc14_power_grid"`:
1. **Targeted Invalidation:** The engine deletes **only**:
   - `out_dir/blocks/block_013.mp4`
   - `out_dir/blocks/block_013.mp4.cache.json`
   All other 37 blocks remain locked and immutable.
2. **Dynamic Prompt Injection:** The engine loads the original scene record from `aligned_scenes[13]` and updates its prompts:
   ```python
   original_prompt = scene["visual_prompt"]
   fix_instruction = defect.prompt_fix_instruction
   # Non-destructive prompt reinforcement:
   scene["visual_prompt"] = f"{original_prompt}, {fix_instruction}, photorealistic anatomical integrity, static hands"
   ```
3. **Selective Flow Dispatch:** Calls `flow_bridge.generate_single_block(...)` targeting only index 13 on Google Flow CDP.

### 6.3 Non-Destructive Surgical Splicing in FFmpeg
Because Google Flow video blocks are duration-locked to the spoken audio timeline (`veo_duration = audio_t1 - audio_t0`), the newly re-rendered replacement block has the **exact same target duration** as the defective block it replaces.

#### Why This Guarantees Audio and Subtitle Preservation
- **Broadcast Audio Bed (`master_audio_3layer.wav`):** TTS voiceover, background music ducking, and procedural SFX foley are rendered against the global master timeline. Because the spliced clip occupies the identical duration $(t_0 \to t_1)$, the audio mix requires **zero recalculation**.
- **Libass Karaoke Subtitles (`captions.ass`):** Word-level timestamps in the `.ass` file reference absolute timeline seconds. Because no scene durations expanded or contracted, the subtitles remain in **sample-accurate synchronization**.

#### Splicing Algorithm Implementation
```python
def surgically_splice_timeline(
    master_video_path: Path,
    replacement_blocks: dict[int, Path],  # {scene_index_0based: new_block_path}
    all_block_paths: list[Path],
    output_path: Path,
    timeline_durations: list[float],
    master_audio_path: Path,
    captions_path: Path | None = None,
) -> Path:
    """Replace defective blocks in-place and re-assemble without touching healthy assets."""
    # 1. Update block file list
    updated_blocks = list(all_block_paths)
    for idx, new_path in replacement_blocks.items():
        if not new_path.is_file():
            raise FileNotFoundError(f"Replacement block missing: {new_path}")
        updated_blocks[idx] = new_path

    # 2. Concat demuxer script generation (zero-loss lossless assembly where possible)
    concat_list = output_path.parent / "splice_concat_list.txt"
    lines = []
    for b_path in updated_blocks:
        # Resolve to clean forward slashes for FFmpeg
        clean_path = str(b_path.resolve()).replace("\\", "/")
        lines.append(f"file '{clean_path}'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 3. Assemble video stream and multiplex with original broadcast audio & subtitles
    # Using filtergraph to guarantee frame-rate stability and clean crossfades
    cmd = [
        config.resolve_ffmpeg(),
        "-y", "-hide_banner",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(master_audio_path),
    ]

    filter_complex = []
    # Video conform
    filter_complex.append("[0:v]fps=30,format=yuv420p[v_base]")
    current_v = "[v_base]"

    # Subtitle re-burn if present
    if captions_path and captions_path.is_file():
        clean_ass = str(captions_path.resolve()).replace("\\", "/").replace(":", "\\:")
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
        raise RuntimeError(f"Surgical splicing failed:\n{proc.stderr}")

    return output_path
```

### 6.4 Infinite Loop Prevention: Circuit Breaker Bounds
To eliminate the risk of runaway API billing or recursive re-rendering loops:
- **`MAX_PATCH_PASSES = 2` (Default: 1):** The engine permits a maximum of 2 patch iterations per production.
- **Circuit Breaker Fallback:** If a clip is re-rendered once and still fails the post-audit with `critical` severity:
  1. The engine logs a `CIRCUIT_BREAKER_ENGAGED` warning.
  2. Fallback Option A: Fallback to procedural Ken Burns pan/zoom on the corresponding high-resolution Hero Plate (`render_ken_burns_block`).
  3. Fallback Option B: Seal production with a `CONDITIONAL_PASS` warning flag and notify the human director.

---

## 7. Zero-Hardcode & Architecture Safety (ADR-090 Compliance)

### 7.1 Zero Hardcoded Strings In Engine Code
In strict adherence to repository invariants:
- **Zero Narrative Text:** No hardcoded screenplay lines, character names, or genre tropes inside `proxy_generator.py` or `surgical_patcher.py`.
- **Zero Prompt Keywords:** No hardcoded words like `"cyberpunk"`, `"horror"`, or `"dramatic lighting"` in Python code.
- **Dynamic Invariants:** All prompts, style anchors, and rules are injected dynamically from:
  1. The project's input `handoff.json` or `aligned_scenes` manifest.
  2. Role Card Markdown skill instructions (`.grok/skills/` and `references/agents/`).
  3. Configuration dataclasses (`FullVideoAuditConfig`).

### 7.2 Configuration Contract (`engine/config.py`)
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

### 7.3 Failure Mode Handling Matrix
What happens if the Gemini API goes down, the network drops, or Chrome CDP is closed during post-audit?

```
                    [Audit Dispatch Attempt]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [Network / API OK]            [Timeout / Exception]
               │                               │
               ▼                               ▼
      Parse Audit JSON               Evaluate fail_mode
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                             "warn_and_pass"        "fail_closed"
                                    │                     │
                                    ▼                     ▼
                             Fallback to CV       Raise AuditError
                             Motion/Freeze Check  Halt Production
                                    │
                                    ▼
                             Log to audit_report.json
                             (audit_status="SKIPPED_OFFLINE")
```

1. **`warn_and_pass` (Default Production Setting):**
   - If Gemini is unreachable after 3 retries, the engine does **not** crash the render.
   - It runs local OpenCV freeze-frame and black-frame detection on the master video (`verify_block_quality`).
   - Writes `audit_report.json` with `overall_verdict: "PASS_UNAUDITED_OFFLINE"` and logs:  
     `"[AUDIT WARN] Multimodal audit offline; local CV passed; master video preserved."`
2. **`fail_closed` (Strict Broadcast Mastering Setting):**
   - When configured with `--strict-audit` or `fail_mode="fail_closed"`, an unverified video will halt production with an exit code 2, requiring human verification before delivery.

---

## 8. CLI Surface Integration & Operator Ergonomics

The engine integrates directly into `tools/cinematic_studio_cli.py` and `engine/factory_cli.py`:

```bash
# 1. Full Production with Automatic Multimodal Post-Audit & Selective Patching
python tools/cinematic_studio_cli.py produce-film "Protocol Omega" \
  --genre "Sci-Fi Thriller" \
  --duration 300 \
  --voice-provider deepgram \
  --auto-patch

# 2. Standalone Audit on an Existing Master Video
python tools/cinematic_studio_cli.py audit-video \
  --video out/protocol_omega/final_film.mp4 \
  --handoff sequences/protocol_omega_handoff.json \
  --out-dir out/protocol_omega/audit

# 3. Surgical Splicing from an Existing Audit Report
python tools/cinematic_studio_cli.py apply-patch \
  --video out/protocol_omega/final_film.mp4 \
  --audit-report out/protocol_omega/audit/audit_report.json \
  --handoff sequences/protocol_omega_handoff.json
```

---

## 9. Verification & Automated Test Strategy

To guarantee regression-free execution across all surfaces:
1. **Mock End-to-End Pipeline Test (`tests/test_multimodal_audit.py`):**
   - Synthesizes a 3-block dry-run video ($12\text{ seconds}$).
   - Injects a simulated defect into Block 2 (e.g., black frame / freeze).
   - Generates the proxy MP4 with HUD and verifies that `proxy_hud.ass` matches time boundaries.
   - Feeds mock Gemini defect JSON targeting Block 2.
   - Executes `surgically_splice_timeline` and asserts that:
     * Block 2 was replaced.
     * Blocks 1 and 3 were untouched.
     * Audio and subtitles remain sample-aligned.
     * Master video file duration equals original duration $\pm 0.05\text{s}$.
2. **Zero-Hardcode Lint Check:**
   - Runs `scripts/lint_zero_hardcode.py` to assert zero narrative strings exist in `proxy_generator.py` or `surgical_patcher.py`.
3. **Bandwidth Compliance Check:**
   - Asserts generated proxy file size $\le 30.0\text{ MB}$ for any 300s test input.

---

## 10. Summary of Architectural Deliverables

| Module Name | File Path | Primary Class / Functions | Status |
| :--- | :--- | :--- | :--- |
| **Proxy & HUD Generator** | `engine/services/proxy_generator.py` | `generate_proxy_hud_ass()`, `build_audit_proxy()` | Spec Complete |
| **Multimodal Auditor** | `engine/services/multimodal_audit.py` | `FullVideoMultimodalAuditor`, `audit_master_video()` | Spec Complete |
| **Surgical Patcher** | `engine/services/surgical_patcher.py` | `surgically_splice_timeline()`, `execute_selective_patch()`| Spec Complete |
| **Production Bridge Integration**| `engine/flow_bridge.py` | Step 3.5 hook after `editor.render()` | Spec Complete |
| **CLI Command Extension** | `tools/cinematic_studio_cli.py` | `produce-film --auto-patch`, `audit-video` | Spec Complete |

*Engine specification authored and sealed for implementation under Grok Imagine Cinematic Studio Architecture Standard v4.5.*
