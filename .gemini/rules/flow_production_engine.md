# Flow Production Engine Invariant

## CRITICAL: "Flow" Definition & Mandatory Production Workflow

1. **What "Flow" Means in This Workspace:**
   - In this repository, **"Flow" ALWAYS refers to Google Flow CDP (Port 9223) + Deepgram Aura-2 + FFmpeg Broadcast Editor** located in `engine/` and bridged via `engine/flow_bridge.py`.
   - It does NOT mean generic ComfyUI, Grok Sequence Runner, or conceptual workflow diagrams.

2. **Unified Production Command:**
   - All film and series production is driven by:
     `python tools/cinematic_studio_cli.py produce-film "<Title>" --genre "<Genre>" --duration <Seconds> [--plan-only] [--dry-run]`
   - **`--plan-only`**: Creates the Production Bible, seals the 3-Act scenes with `[MOMENTUM_VECTOR]`, locks Character DNA, and outputs `sequences/<slug>_handoff.json` without rendering any video or spending quota.
   - **Full Run (Without `--plan-only`)**: Connects to Chrome CDP Port 9223 (`engine/chrome_flow.bat`), generates Veo/Imagen video blocks, calls Deepgram for `vo.wav`, generates tension audio bed, burns Libass karaoke subtitles, and renders `out/<slug>/final_film.mp4`.

3. **No Orphan Image Generations:**
   - If an agent generates Character Hero Plates (e.g. using `image-generator` or Imagine 2.0), it MUST:
     a) Save them into the `characters/` folder (e.g. `characters/captain_cole_vance_hero.jpg`).
     b) Link them as reference plates in the project's handoff packet (`sequences/<slug>_handoff.json`).
     c) Feed them directly into `produce-film` so they become the visual anchor for Google Flow video generation.
   - Never generate images and leave them abandoned in the chat artifact directory without connecting them to the video production pipeline.

4. **Chrome CDP (Port 9223) & Gemini WebAPI (Port 8085) Execution Protocol:**
   - For dual-judge adversarial review (Grok xAI + live Google Gemini) and physical Veo rendering, Chrome CDP must run on port `9223` with isolated profile `%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile`.
   - **How to Keep Chrome Alive (Preventing Windows Job Object Kill):**
     When running via agent command tool, ALWAYS execute `python scripts/keep_chrome_alive.py` with `IsDaemon=true` and `WaitMsBeforeAsync=500`. This holds `proc.wait()` so Windows process tree cleaners do not terminate Chrome.
   - **WebAPI Daemon (Port 8085):** Call `gemini_webapi.sync_cookies_sync(cdp_port=9223)` followed by `gemini_webapi.ensure_server_running(force_refresh=True)`. Verify connection before running production. Full guide: `docs/guides/CHROME_CDP_AND_GEMINI_WEBAPI_GUIDE.md`.
