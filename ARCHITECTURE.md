# Provider-native architecture

```text
main.py / CLI
  -> explicit Vertex or Flow production bundle + RunContext + persisted TimelinePlan
  -> pipeline.py (script, keyframes/voice, blocks, FFmpeg edit)
  -> providers.factory -> selected LLM / Image / Video / Voice adapter
  -> services (topic selection, screenplay model, validation, prompt compilation)
  -> editor.py (FFmpeg only)
```

Services contain no credential, HTTP/SDK, endpoint, or provider-selection code. Provider
adapters own selected transport, authentication, sanitizer, polling, and provider errors.
The factory resolves one adapter; it never silently changes provider.

## Timeline and persisted state

A normal new run starts with an eight-shot screenplay outline, produces narration, and
then derives `N = ceil((voice_duration - 1.5) / 4.0)` clamped to 6–13 (adding one native
block only when tail-inside-final accounting would otherwise overrun). The resulting N x
4.0-second blocks, N+1 sequential Match-Cut keyframes, measured voice duration,
`footage_duration`, `content_duration`, `target_duration`, and 1.5-second
`tpad=stop_mode=clone` tail are locked atomically in `script.json` before any keyframe request.
The tail is inside `target_duration=max(voice_duration+0.4, footage_duration)`; the final
provider block is trimmed before `tpad`, so a render never appends an accidental extra hold.
`--test-blocks N` is a separate 1–8 block smoke run that writes `test_final.mp4` and
cannot combine with `--resume`. A resume uses the stored `script.json.timeline`
unchanged, including legacy deserialization compatibility.

The atomic BOM-free JSON artifacts are `script.json`, `state.json`, `prompt_manifest.json`,
`refs.json`, `topic_selection.json`, handoff/preflight/quality reports, and release report.
Exact `kfNN` identities and prompt hashes make stale aliases insufficient; only affected
dependencies are eligible for regeneration. `kf01` is the opening anchor. Every normal `kf02+`
endpoint is generated with the immediately previous accepted `kfNN` as an image reference,
as well as the authored endpoint contract. Sequential filenames or repeated continuity words
alone never count as a Match-Cut chain. On Vertex, each generated keyframe is then admitted
by the configured Vertex vision route before Veo sees it: it checks the authored state/proof,
pair continuity, 9:16 framing, and no-text/no-watermark contract. Review unavailability is
recorded explicitly; a reviewed rejection stops before a paid video block is submitted.
Before it stops, the rejected endpoint is moved to `rejected/keyframes/` and regenerated up
to the configured small admission budget with the reviewer’s concrete failure reasons. The
accepted predecessor and all other accepted assets remain untouched.

`presentation_mode` records `contextual_opening_anchor`, `opening_anchor`, `mechanism`,
or an optional terminal payoff. A contextual anchor records the viewer-facing person,
animal, object, vehicle, structure, organ exterior, science subject, or environment separately
from the technical `mechanism_anchor_id`. It persists its roster identity, appearance contract,
prompt hash, and sheets. `return_to_opening_anchor_payoff` remains legacy-compatible.
`return_to_contextual_anchor_payoff` is permitted only on the final block with a causal
`payoff_reason`, same contextual roster identity, `first_only` endpoint, and a readable
physical proof. It is an independent hard-cut Veo block, not a morph. Its persisted
`frame_plan` uses final `kfN+1` as `start_frame_id`, `end_frame_id: null`, and
`contextual_anchor_roster_only`, so Nano Banana Pro sees contextual roster references and
Terminal contextual payoff and its 1.5-second cloned tail receive no punch or shake.
The cut into the terminal payoff applies an organic 0.5-second pull-out zoom decay
(1.08 -> 1.0) in FFmpeg so returning from an internal organ to the human character feels
like a smooth outward camera reveal rather than a jarring jump.

## Production routes, concurrency, and failure behavior

The normal user-facing choices are deliberately only:

1. Vertex AI: Nano Banana Pro (`nano_banana_pro`) for every keyframe and Veo 3.1 (`vertex_veo`) for every video block.
   Vertex Veo video block generation is executed sequentially with
   `VERTEX_VEO_MAX_CONCURRENT_BLOCKS=1` (ADR-008). Vertex AI Veo enforces strict per-project
   concurrency quotas; concurrent block requests result in silent payload drops (`operation.done=True`
   without generated video bytes). Concurrency is only valid for still-image reference generation,
   never for Veo video blocks.
2. Flow Agent: `flow_agent` video paired with `flow_agent` keyframes via the configured CLI/bridge.
3. Playwright Flow (Zero-Focus Background Factory, ADR-042): `playwright_flow` video paired with
   `playwright_flow` keyframes via `services/playwright_flow_client.py`. Bridges a background/minimized
   Chrome CDP session on port 9223 (`FlowCDPProfile`) to `flow-windows.exe bridge` on `ws://127.0.0.1:9222`.
   Mints genuine browser reCAPTCHA Enterprise tokens directly from `flow.google.com` origin and extracts
   session cookies (`__Secure-1PSID`, `OSID`, `WIZ_global_data`), enabling 100% background video generation
   without OS mouse movement or foreground window focus stealing.

## Dual Format Architecture (ADR-040 & Shorts)

The pipeline supports two first-class production formats:

- **Format A: 16:9 Longform Documentary Mode** (`--format longform`, `LONGFORM_MODE=true`):
  * Widescreen 1920x1080 / 1280x720 canvas (`FAL_ASPECT_RATIO=16:9`).
  * Anchor Character: 28-year-old female archaeologist/explorer "Nova" in khaki safari jacket, hazel eyes, freckles, lav mic (`services/character.py`).
  * Narrative Structure: 3 A-Roll talking scenes (10–15% of runtime) with lip-sync; 85–90% B-Roll showcasing underground ancient relics, flooded labyrinths, and architectural mysteries.
  * Audio Bed: 40 Hz deep bass cinematic drone bed (`epic_curiosity` in `services/audio_bed.py`), 1st-person English narration.
- **Format B: 9:16 Shorts Mode** (`--format shorts`, default):
  * Vertical 1080x1920 canvas (`FAL_ASPECT_RATIO=9:16`).
  * Zack D. Films style: 6–13 provider-native 4.0s blocks (24–52s) + 1.5s cloned tail. Characters never speak (no lip-sync). Caption-safe lower-middle zone.

The resolved bundle is persisted in run state. A mismatched image override is rejected,
not patched with another provider. Developer-only local/manual/Fal paths can remain CLI
overrides but are not normal choices. Flow CLI, session, or bridge failure raises
`HandoffPending`, writes a token-free `handoff.md`, and stops; it never falls through to
Vertex, Fal, or local.

All model names, credentials, and transport locations are configuration data read at the
selected provider boundary from `.env`; `.env.example` declares each lookup. The code
does not print values from `.env`.

## Autonomous topic and screenplay quality

If a real new run has no `--video`, interactive CLI asks exactly:

`Hangi video üretim yöntemini kullanalım? [1] Vertex AI (resmî API) / [2] Flow Agent (GitHub repo/CLI)`

Noninteractive CLI emits precisely that one-line state. After a route is explicit,
missing topic invokes provider-neutral automatic selection and writes
`topic_selection.json` with candidates, component scores, source URLs, timestamp,
selection/fallback reason, and duplicate policy. No live trend result is fabricated:
without injected verified live signals it uses cited evergreen candidates with
`trend_status: unavailable`. Only completed/published/publishable run-history entries
and the explicit preserved completed allowlist block duplicates; handoffs do not.

Every shot records scale, `visual_domain`, journey phase, transition kind, persisted 2–4
coverage beats, detail/material requirements, continuity anchor, states, proof, optional marker,
and quality-critical structure. A run-local `asset_roster.json` supplies 2:3 character,
1:1 subject, and 9:16 empty-plate sheets; `kf01` sees roster references and later frames
also see their accepted predecessor. The canonical compiler binds identical glossy stylized
3D mannequin/medical-animation, dark-void, warm-gold/cyan-rim keyframe and diegetic-motion
requirements. Coverage beats create 1.0–1.6-second FFmpeg hard reframes without asking a
video provider for camera movement. The validator rejects wrong timing, unsafe scale/domain pairs,
large scale jumps, multi-location/fragile mechanical requests, state contradictions,
unjustified `first_only`, and invalid marker/caption-safe quadrant use. A phase controls
narrative restraint, never decorative VFX injection.

The persisted `editorial_plan` owns boundary impact. Every cut defaults to `hard` plus
`impact_level: none`; word emphasis and subject changes never create a camera effect.
An explicitly selected `subtle` impact may add at most a 1.2% local reframing pulse;
`strong` is a single diegetic action generated in the source clip, never a crash zoom or
shake. The editor uses hard cuts only—never xfade/cross-dissolve—while retaining
half-open windows and live crop clamps. Terminal opening-anchor payoffs accept no impact.

## Optional licensed SFX

SFX is opt-in through one explicitly selected `BaseSfxProvider`. The included
`local_manifest` adapter resolves only already-cached assets with a source URL, creator,
CC0 or commercially usable CC-BY license URL, explicit commercial permission, SHA-256,
local file, semantic tags, and CC-BY attribution. `sfx_cue_sheet.json` records at most two
event-linked cues per block; a caption emphasis cannot create one. Unknown, NC, incomplete,
or hash-mismatched assets fail closed and never enter a mix. Used CC-BY records produce
`ATTRIBUTIONS.txt`. There is intentionally no generic web scraping or hidden SFX fallback.

## Immutable FFmpeg and release rules

Do not alter the half-open `gte(time,t0)*lt(time,t1)` ownership gate or live
`clip(...,0,dim-(dim/zoom))` clamp in `editor.py`. They prevent shared boundary frames
and exposed black edges. Render geometry remains 9:16 for Shorts mode, or 16:9 widescreen
for Longform mode (`LONGFORM_MODE=true`). Captions are ASS/FFmpeg only,
use active `&H00D7FF`, emphasis scale 112, outline 7, `WrapStyle 0`, and roughly three
words/22 characters. Final polish is `unsharp=5:5:0.7`, `noise=alls=8:allf=t+u`,
`eq=contrast=1.06:saturation=1.05`, and `vignette=PI/5`.

One clip has one physical state change. Quality/review retries must be surgical and
reuse accepted assets; missing/empty paths are never treated as a workspace directory.
`release_report.json` can mark a run publishable only when every technical, caption,
continuity, quality, and factual-evidence gate passes.

## Verification

```powershell
python scripts/audit_and_sync.py
python -m pytest -q
python main.py --topic "Why does glass shatter?" --dry-run --no-captions
python main.py --topic "Why does glass shatter?" --test-blocks 1 --dry-run --no-captions
```
