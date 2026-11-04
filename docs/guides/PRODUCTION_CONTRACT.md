# Production authoring and validation contract

Live `produce-film` authoring requires `XAI_API_KEY` or a previously authored handoff. Missing credentials, incomplete authoring responses, and authoring failures stop production; the engine never substitutes a fixed story. `--plan-only` saves the authoring and audit artifacts without physical rendering, but may still call the authoring model and judges.

Use `--dry-run` for offline simulation. This loads explicitly marked fixtures from `examples/fixtures/narrative_simulation.json`. Simulation scenes remain uncertified, including when their deterministic audit score is high. A simulation handoff is not eligible for live rendering, including with `--force-render`.

Creative repairs belong to the skill-guided authoring model. The linter reports POV, visual and CTA violations without replacing narration, visual direction, or scientific values. Missing text remains an error. The healer reports unresolved defects when no authoring provider is available.

Production certification requires a score of at least 90 and no critical deterministic defects. Each configured AI judge must return a finite numeric score between 0 and 100. Invalid or missing scores fail closed. A lower-scoring screenplay is not labelled Grade A+.

The named Grok judge defaults to `grok-4.20-0309-non-reasoning` (alias `grok-4.20-non-reasoning`); a generic model environment variable cannot replace an explicit judge selection. The named Gemini judge defaults to `gemini-3.1-pro`. Gemini chat only tries alternative models when its caller supplies an explicit `fallback_models` allowlist. The CLI does not supply such an allowlist. The separate heuristic fallback still requires the existing explicit consent option.

A data B-roll scene uses these canonical fields:

- `is_data_broll`: boolean routing flag; `[DATA_BROLL]` in `visual_prompt` is also recognized.
- `template_name`: `GeospatialStormMap`, `TelemetryCurve`, or `VolcanoSeismicMap`.
- `data_payload`: a complete object with scenario-specific values.

The shared field contract is `engine/motion_graphics/payload_schema.json`. Both authoring and rendering validate it. Missing values do not inherit unrelated demonstration data. Authoring receives this schema together with the loaded directing skills. Map centers use `[latitude, longitude]`. Demonstration fixtures are explicit simulation inputs, never production defaults.
