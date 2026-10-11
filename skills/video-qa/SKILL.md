---
name: video-qa
description: Review this project's rendered Shorts release artifacts and classify them as pass, review, or fail without publishing media.
---

# Video QA

Use this skill after a render or when diagnosing publishing readiness.

- Read `quality_report.json`, `release_report.json`, `research.json`, `captions.ass`, and the contact sheet when present.
- Treat missing audio, wrong 1080x1920 geometry, wrong 30 fps, duration outside tolerance, and rejected blocks as failures.
- Treat missing captions or unapproved factual claims as review blockers, not silent passes.
- Separate deterministic technical evidence from subjective visual observations such as anatomy drift, continuity errors, unreadable captions, or narrative/visual mismatch.
- `review` and `fail` are not permission to upload or publish. Return the specific artifact and condition that must be resolved.
