# Models registry (canonical alias)

Full model selection guide for **Grok 4.6** (cinematic + Build default; `grok-4.5` aliases wrap 4.6), optional **4.6** routing surfaces, optional **Grok 4.3** 1M, and Imagine Video/Image:

→ **Primary agent embed:** [`agents/MODEL_LAYER_v4.5.md`](agents/MODEL_LAYER_v4.5.md)  
→ **Prior stack table:** [`agents/MODEL_LAYER_v3.7.1.md`](agents/MODEL_LAYER_v3.7.1.md)  
→ **Long-form guide:** [`MODELS_v3.6.md`](MODELS_v3.6.md) (filename historical; content tracks studio **v3.8.6**)

Code registry (single source of truth): `tools/models.py` · `STUDIO_COMPATIBILITY_VERSION = 3.11.4`.  
**Imagine surface map:** [`agents/IMAGINE_SURFACES.md`](agents/IMAGINE_SURFACES.md) (Image 1.0 / **2.0** + Video 1.0 / 1.5 — **no video 2.0**. Quality slug retires 2026-11-02).

```bash
python tools/cinematic_studio_cli.py models list
python tools/cinematic_studio_cli.py models verify
python tools/cinematic_studio_cli.py stack
```

| Layer | Default slug | Notes |
|-------|--------------|-------|
| Orchestration / cinematic chat | `grok-4.6` | Production Bibles, multi-agent (`grok-4.5` aliases wrap 4.6) |
| Opt-in multi / expert | `grok-4.6` (Chat **Heavy**) · `grok-4.6` (Chat **Expert**) | Skill Model Layer routing; Build pickers wrap 4.6 |
| Fast routing | `grok-4-auto` | Routine specialist hops (same install script) |
| Long-context | `grok-4.3` | 1M memory banks only |
| Grok Build CLI | `grok-4.6` · fork `grok-build` or `grok-4.6` | ≥ **1.0.5** binary |
| Imagine Video | `grok-imagine-video` (1.0 cost / edit / extend) / `1.5` native audio + r2v | Dual path — **no video 2.0** |
| Imagine Image | `grok-imagine-image` (draft) · **`grok-imagine-image-2.0` (hero / Quality Mode)** · `quality` slug retired 2026-11-02 → 2.0 `quality=low` | Stills |

## Google Flow CDP Video & Image Models (v4.6 Production Stack)

| Model Slug | Display Name | Quality / Durations | Role & Lifecycle |
|---|---|---|---|
| `gemini_omni_flash_1_2` | **Gemini Omni 1.2 Flash** | 720p / 360p (4s, 6s, 8s, 10s) | **Tier 3 Flagship Video Engine** (Nov 2026). Enhanced character and physics coherence. |
| `gemini_omni_flash_1_1` | **Omni 1.1 Flash** | 360p / 720p (4s, 6s, 8s, 10s) | **Tier 2 Test Engine** (4 credits / 4s). Active through **2026-12-05** retirement. |
| `veo_3_1_lite` | **Veo 3.1 - Lite** | 360p / 720p (4s, 6s, 8s, 10s) | **Tier 2 Fall-through Engine** (10 credits). Active after **2026-12-05**. |
| `nano_banana_2_1` | **🍌 Nano Banana 2.1** | Native aspect (16:9, 9:16) | **0-Credit Hero Frame Engine**. Free text-to-image plates for `first_frame` anchor. |
