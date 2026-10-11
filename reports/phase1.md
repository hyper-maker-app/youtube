# Phase 1: Contextual Anchors & Mode Profiles

## Diff Summary
- Introduced `ModeProfile` with `ANATOMICAL` and `INCIDENT` modes.
- Refactored `script_engine.py` to route logic based on mode instead of hardcoded rules.
- Expanded `Shot` and `Script` dataclasses to support `secondary_subject_ids` and `mode`.

## Architectural Notes
- The addition of `ModeProfile` enables flexible pipeline expansions without breaking the core engine.
- Validation checks are now context-aware and mode-dependent.
- Implemented robust anti-text and domain-bleed shields.
