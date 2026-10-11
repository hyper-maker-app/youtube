---
name: run-review
description: Record and inspect YouTube Shorts pipeline outcomes for duplicate prevention and quality learning without accessing YouTube publishing controls.
---

# Run review

Use this skill after a completed pipeline run or when selecting a new topic.

- Query the local pipeline history through the parameterised pipeline-db MCP tools; never use arbitrary SQL.
- Compare normalized topic wording before choosing a new topic and flag exact duplicates.
- Record the run's topic, content type, source/fallback route, final duration, release status, and quality blockers after completion.
- Keep future YouTube Analytics integration read-only until the user explicitly authorizes a separate upload or publishing workflow.
