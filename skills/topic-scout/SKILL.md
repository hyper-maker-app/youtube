---
name: topic-scout
description: Research high-curiosity scientific, medical, and everyday mystery topics tailored for 3D causal animation.
---

# Topic scout

Use this skill when picking or evaluating new topics for `--auto-topic`.

- Verify duplicate prevention using `youtube-pipeline-db.topic_exists` before approving a topic.
- A topic must depict a physical, irreversible mechanism (e.g. why bones mend, how venom coagulates, why lighthouses use fresnel lenses). Purely abstract philosophical or conversational topics are forbidden.
- For medical/biological claims, require peer-reviewed or institutional evidence via `youtube-research` MCP; Wikipedia is only background context.
