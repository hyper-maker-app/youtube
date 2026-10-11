---
name: shorts-script-editor
description: Edit this repository's provider-native factual, folklore, or fiction Shorts scripts while preserving evidence, timing, and visual contracts.
---

# Shorts script editor

Use this skill when editing narration, beats, prompts, or upload metadata for this project.

- Keep the five-beat arc: hook, twist, mechanism A, mechanism B, kicker; preserve the configured word budget for the selected language.
- For factual work, use only approved claims in `research.json`; retain the content type and truth frame in `script.json`.
- Every beat must have a visible, physically renderable subject/action. Remove abstract promises, dialogue, screen text, UI, and visual claims that cannot be shown by the associated shot.
- Preserve the `timeline` stored in `script.json` when editing an existing run. New runs derive shot/keyframe counts and narration budgets from their provider-native `TimelinePlan`; do not impose a global duration or shot count.
