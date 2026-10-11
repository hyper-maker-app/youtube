---
name: fact-check
description: Verify factual YouTube Shorts claims against the project research manifest before changing or approving narration.
---

# Fact check

Use this skill for factual Shorts, especially medical, biological, safety, historical, and engineering claims. Do not use it to frame folklore or fiction as factual.

- Read the run's `research.json` before writing or approving factual narration.
- Keep only claims marked `approved`; do not turn a `review` claim into fact by stronger wording.
- For medically sensitive content, require a primary, peer-reviewed, or institutional source. A Wikipedia summary is context, not sufficient evidence.
- Replace absolutes such as "never", "always", and "cannot" only when the source explicitly supports them; otherwise use the manifest's approved wording or request review.
- Preserve source URL, title, type, evidence, confidence, risk, and approved wording in each claim record.
