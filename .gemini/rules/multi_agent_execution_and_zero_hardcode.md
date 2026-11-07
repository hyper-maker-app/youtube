# Multi-Agent Subagent Delegation & Zero-Hardcode Invariant Protocol

## 1. Mandatory Multi-Agent Subagent Delegation Workflow

When executing any engineering, feature integration, or multi-step implementation plan:

1. **Decomposition into Focused Work Streams:**
   - The Main Lead Agent must decompose the plan into independent or logically ordered modular tasks.
   - Each distinct task/module MUST be assigned to an isolated, specialized subagent using `invoke_subagent`.
   - Never execute a complex multi-part plan in a single monolithic context where details degrade.

2. **Parallel & Specialized Execution:**
   - Subagents work concurrently or sequentially in their domain of expertise (e.g. Skill Specialist, Engine/API Specialist, Frontend/Remotion Specialist, Video Pipeline Specialist).
   - Each subagent executes its scoped changes, writes its unit tests, and verifies its local output.

3. **Dedicated Auditor / QA Subagent Review (Mandatory):**
   - After all implementation subagents complete their tasks, an independent **Auditor / QA Reviewer Subagent** MUST be invoked.
   - The Auditor Subagent inspects all changed files, checks for code regressions, verifies zero hardcode, runs the automated test suite (`pytest`, `npm test`, CLI tests), and actively fixes any detected defects.

4. **Mandatory Multi-IDE & Governance Synchronization (CRITICAL):**
   - Coding agents MUST NEVER stop at Python engines and unit tests.
   - Every architectural, pipeline, model, or CLI change MUST synchronously update all agent governance files:
     * `.gemini/rules/` (Antigravity / Gemini guidelines)
     * `.cursor/rules/` (Cursor IDE rules)
     * `.grok/skills/` (Grok Build skills)
     * `AGENTS.md`, `README.md`, and `references/MODELS.md`
   - The Auditor Subagent MUST verify that all IDE rule directories reflect the latest changes before giving final sign-off.

5. **Main Lead Agent Final Verification & User Presentation:**
   - Once the Auditor Subagent reports full pass, the Main Lead Agent conducts a final end-to-end sanity verification.
   - The Main Lead Agent compiles and presents the final summary, test evidence, and walkthrough to the user.

---

## 2. Absolute Zero-Hardcode Invariant (Zero Hardcode Policy)

1. **Python Engines (`engine/`, `tools/`):**
   - Absolutely ZERO hardcoded narrative text, creative dialogues, scene sentences, or word substitution dictionaries (e.g. `{"needle": "sensor"}`, `"pressure valve housing"`).
   - Python code must remain a **Pure Pipeline**: schema validation, I/O handling, external LLM/API communication, and FFmpeg/Remotion command execution.

2. **Skill Definitions (`.grok/skills/*.md`):**
   - Absolutely ZERO fixed scene lines, artificial dialogues, or hardcoded Call-to-Action (CTA) sentences (e.g. literal *"You must subscribe to the channel now..."*).
   - Skills must ONLY contain **universal directing principles, thermodynamic/physical laws, and structural/formal storytelling constraints**.
   - CTA rules must be specified strictly as structural criteria (e.g. 2nd-person POV, isolated terminal sentence of final scene, model-generated per scenario).

3. **Render Templates & Motion Graphics (Remotion / React):**
   - Absolutely ZERO hardcoded text, city coordinates, telemetry values, or labels in React components.
   - All components must be 100% parametric (`props`), driven dynamically from JSON payloads generated during the screenplay and handoff phase.
