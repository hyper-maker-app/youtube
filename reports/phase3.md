# Phase 3: Long-Form Architecture Extension (Item A)

## Diff Summary
- Introduced a new isolated module `core/narrative_longform.py` featuring `LongformEngine`.
- Modified `main.py` by adding the `--format` CLI flag (with `short` and `longform` choices).
- Updated `RunContext` in `pipeline.py` to track the `format`.
- Modified `phase1_script` within `pipeline.py` to route requests dynamically to `LongformEngine` when `format` is `longform`, ensuring 100% bypass of the `script_engine.py` (which expects strict 5-beat pacing).

## Architectural Notes
- Zero regressions to the Shorts pipeline: `script_engine.py` and Shorts logic remain completely intact.
- The `LongformEngine` returns a compatible `Script` object featuring 4+ episodes / 25+ beats.
- Validation logic (`validate_script`) is safely skipped for longform requests, allowing complex narrative formats to flow into the video pipeline seamlessly.
