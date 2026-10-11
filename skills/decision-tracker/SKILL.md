---
name: decision-tracker
description: Consult past architecture decisions and record abandoned or accepted experiments before changing code or prompts.
---

# Decision tracker

Use this skill whenever:
1. The user asks for a new style, feature, timing, animation, or workflow change.
2. An experiment or test is completed, fails, or is cancelled by the user.

- Query `DECISIONS.md` (or call `youtube-decision-memory` MCP / `python scripts/decision.py search "<keyword>"`) BEFORE implementing any architectural or artistic change.
- If an idea was previously marked `ABANDONED` or `REJECTED`, warn the user with the date and reasoning from the ADR record, explaining why it was bad.
- If a new change is rejected, produces bad visual results, or the user says "iptal ettik / geri alalım", immediately record the decision with status `ABANDONED`, documenting what was requested, what was done, why it failed, and the lesson learned.
