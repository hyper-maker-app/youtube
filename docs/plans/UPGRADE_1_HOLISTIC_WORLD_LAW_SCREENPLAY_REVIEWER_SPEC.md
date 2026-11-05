# UPGRADE 1: TECHNICAL ARCHITECTURE & DESIGN SPECIFICATION

> **Implementation status (5 November 2026):** The following is a historical
> design, not evidence of live provider verification. `--screenplay-mode holistic`
> is opt-in and requires two valid judges and passing hard checks. The default
> `strict-checklist` is partial review and cannot certify a production screenplay.
> Structured world rules currently ship for catastrophe; other genres without a
> matching director and rule set fail closed. Skill and rule provenance is recorded
> in the review context. Offline fixtures do not establish provider reliability,
> dramatic quality, or audience retention.
## "Holistic World-Law & System-First Screenplay Reviewer and Healer"

**Version:** 4.5.0-ARCH  
**Author:** Screenplay Architecture Specialist  
**Target Platform:** Grok Imagine Cinematic Studio / Google Flow CDP Production Pipeline  
**Department:** Screenplay Engineering & Adversarial Quality Assurance  
**Status:** Approved for Implementation  

---

## 1. Executive Summary & Problem Diagnosis

### 1.1 The Legacy Problem: Checklist "Tunnel Vision"
The legacy screenplay evaluation pipeline in `engine/services/screenplay_reviewer.py` evaluates screenplays against a rigid 6-item deterministic checklist:
1. CTA Isolation (15 pts)
2. Veo Negative Guardrails (25 pts)
3. Thermodynamics & Physics (20 pts)
4. Chronological Progression (15 pts)
5. Causality & Photon Delay (15 pts)
6. 2nd-Person POV Invariant (10 pts)

While highly effective at catching mechanical defects (e.g. premature CTAs, prompt text mentioning mirror faces, or non-English/third-person narrator syntax), this narrow checklist introduces severe **"tunnel vision"**:
- **Dramatic Tempo Drops:** A screenplay can pass all 6 checks while being dramatically dead, emotionally flat, or devoid of rising tension.
- **Character Motivation & Agency Leaps:** The audience ("You") can make nonsensical survival decisions with zero causal or psychological justification, yet receive a perfect 100/100 score.
- **Narrative Monotony & Rhythm:** Monotonous sentence structures, lack of breath/dialogue cadence, or clunky voiceover pacing go undetected.
- **Hardcoded Science in Code:** Physics rules (nitrogen liquefaction at -196°C, oxygen liquefaction at -183°C, 8.3-minute photon delay) were previously hardcoded directly inside Python regexes in `screenplay_reviewer.py`, violating the project's **Zero-Hardcode Invariant**.
- **Context Blindness in Scene Healing:** In previous iterations, scene repairs evaluated or regenerated scenes in near-isolation, risking local fixes that broke global chronological arcs or caused tonal disconnects.

### 1.2 The Solution: Hybrid World-Law & Holistic Directing Architecture
This upgrade establishes a **Dual-Layer Evaluation and Healing Architecture**:
```
+----------------------------------------------------------------------------------------------------+
|                         Screenplay Reviewer & Healer Architecture v4.5                            |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|   [ .grok/skills/*.md ] + [ Scenario Title & Genre ]                                               |
|            |                                                                                       |
|            v                                                                                       |
|   +------------------------------------+                                                           |
|   |   Dynamic World-Law Extractor      |  --> Extracts scenario-specific physics, thermodynamic    |
|   |   & Directive Assembler            |      thresholds, escalation stages & micro-math bounds    |
|   +------------------------------------+                                                           |
|            |                                                                                       |
|            v                                                                                       |
|   +--------------------------------------------------------------------------------------------+  |
|   | Dual-Mode Adversarial Judge Engine (Grok 4.6 / 4.20 + Gemini 3.1 Pro via CDP Port 9223)    |  |
|   |                                                                                            |  |
|   |  [ LAYER A: Holistic Directing & Narrative Logic (50 Pts) ]                                |  |
|   |    - Dramatic Pacing & Tension Escalation (15 pts)                                         |  |
|   |    - Character Agency & Survival Motivation (10 pts)                                       |  |
|   |    - Retention Hooks & Pattern Interrupts (10 pts)                                         |  |
|   |    - Sensory Breath & Narration Rhythm (10 pts)                                            |  |
|   |    - World-Law Plausibility Cohesion (5 pts)                                               |  |
|   |                                                                                            |  |
|   |  [ LAYER B: Hard Guardrail Anchors (50 Pts) ]                                              |  |
|   |    - Veo Video Safety Invariants (20 pts)                                                  |  |
|   |    - Terminal CTA Isolation in Scene 38 (15 pts)                                           |  |
|   |    - 2nd-Person Invariant & 100% English (15 pts)                                          |  |
|   +--------------------------------------------------------------------------------------------+  |
|            |                                                                                       |
|            v Pessimistic Scoring Gate (min(Grok, Gemini))                                          |
|   +------------------------------------+                                                           |
|   | Enriched Scorecard & Defect Schema |  --> Structured taxonomy: scene_id, category, severity,   |
|   +------------------------------------+      responsible_skill, issue, fix_instruction, rule     |
|            |                                                                                       |
|            v (If Score < 90 or Critical Defect Present)                                            |
|   +--------------------------------------------------------------------------------------------+  |
|   | Context-Aware Screenplay Healer (All 38 Scenes Passed as Context)                          |  |
|   |   - Preserves unbroken causal arc across whole script                                      |  |
|   |   - Rewrites only defective scenes                                                         |  |
|   |   - Closed-loop SkillReinforcementService updates SKILL.md under < 500 lines               |  |
|   +--------------------------------------------------------------------------------------------+  |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Component 1: World-Law & System Principles Injection

### 2.1 Dynamic World-Law Principles
To preserve the **Pure Engine Invariant (Zero Hardcode)**, Python engines (`screenplay_reviewer.py`, `screenplay_healer.py`) must contain **zero hardcoded scientific facts or scene narrative texts**. 

All scenario-specific physics and world laws must be dynamically assembled from:
1. **Genre and Specialized Director Skills (`.grok/skills/<slug>/SKILL.md`):**
   - `catastrophe-director`: PDC flow speeds (100–700 km/h), temperatures (800°C–1000°C), decibel thresholds (> 180 dB), volcanic winter cooling curves (-15°C drop), acid rain pH (2.0–3.0).
   - `planetary-catastrophe-director`: Speed-of-light photon delay (8 min 20 sec), orbital decay mechanics, atmospheric stripping, solar CME plasma density.
   - `deepsea-survival-director`: Hydrostatic pressure (+1 atm per 10m / ~1000 atm hadal depth), bioluminescent wavelengths, nitrogen narcosis, decompression schedules.
   - `micro-survival-director`: Caloric burn rates, dehydration progression (3 days water limit), body core hypothermia curves (< 35°C), air filtration micron ratings.
   - `urban-infiltration-director`: SCADA grid failure cascaded latency, backup generator diesel burn hours, electromagnetic pulse (EMP) line impedance.
2. **Universal Directing Directives:**
   - `director-of-photography`: Lens choice, camera motion vectors, lighting contrast, zero-mirror face invariants.
   - `viral-retention-director`: In-media-res hook within first 3 seconds, dynamic 4–10s block pacing, smart ending CTA isolation.
   - `foley-sound-design-specialist`: Dual-stage SFX, synthetic foley fallback, decibel sanity.
   - `continuity-consistency-guardian`: Hero visual DNA, lighting vector matching, seamless block transitions.

### 2.2 The Dynamic Injection Engine (`WorldLawExtractor`)
We introduce a clean, decoupled service: `WorldLawExtractor` (in `engine/services/world_law_extractor.py`), orchestrated by `SkillLoader`.

```python
class WorldLawContext:
    """Encapsulates extracted scenario physics, narrative scales, and directing laws."""
    genre: str
    scenario_title: str
    active_skills: list[str]
    physical_invariants: list[str]
    escalation_stages: list[dict[str, str]]
    micro_math_constraints: list[str]
    negative_visual_guardrails: list[str]
```

#### Extraction Mechanism:
1. **Semantic Topic & Skill Matching:**
   Given `title` and `genre`, `WorldLawExtractor` selects the primary director skill (`catastrophe-director`, `planetary-catastrophe-director`, `deepsea-survival-director`, etc.) and supporting specialist skills.
2. **Markdown Section Parsing:**
   The extractor scans the Markdown AST of the selected `SKILL.md` files:
   - Sections labeled `## 5-Stage Geological Escalation Engine` or `## Narrative Escalation` provide stage-by-stage chronological benchmarks.
   - Sections labeled `## Physics Bounds` or `## Thermodynamic Laws` provide numeric and physical constraints.
   - Sections labeled `## Micro-Mathematics` extract the mandatory survival metrics.
   - Sections labeled `## Negative Visual Guardrails` extract prompt negatives.
3. **Prompt Injection Payload:**
   The extracted world laws are formatted into a clean markdown block titled:
   `=== [WORLD-LAW & SYSTEM PRINCIPLES CONTEXT (ENFORCED)] ===`
   and injected directly into the LLM dual-judge evaluation prompt.

---

## 3. Component 2: Dual-Mode Evaluation Prompt & Rubric Design

The reviewer operates on a balanced **100-Point Dual-Layer Rubric** divided equally into:
- **Layer A: Holistic Directing & Narrative Logic (50 Points)**
- **Layer B: Hard Guardrail Anchors (50 Points)**

### 3.1 Rubric Specification

```
+---------------------------------------------------------------------------------------+
| LAYER A: HOLISTIC DIRECTING & NARRATIVE LOGIC (50 POINTS)                            |
+---------------------------------------------------------------------------------------+
| 1. Dramatic Pacing & Tension Escalation (15 pts):                                     |
|    - Dynamic escalation from initial crisis hook to existential climax.              |
|    - Absence of narrative flatlines, redundant exposition beats, or tempo stalling.   |
|                                                                                       |
| 2. Character Agency & Micro-Survival Motivation (10 pts):                             |
|    - The 2nd-person protagonist ("You") exhibits realistic survival psychology.       |
|    - Actions are motivated by tangible constraints rather than plot armor.            |
|                                                                                       |
| 3. Retention Hooks & Pattern Interrupts (10 pts):                                     |
|    - In-media-res crisis hook established within the first 3 seconds (Scene 1).       |
|    - Micro-cliffhangers, sensory shocks, and rhythmic pattern interrupts every 30-45s.|
|                                                                                       |
| 4. Sensory Breath & Narration Rhythm (10 pts):                                        |
|    - Sentence cadence mimics physiological stress (short gasping clauses in panic,     |
|      measured observational beats during shelter/silence).                            |
|    - 100% natural spoken English, clean syntax, zero metadata or bracket leakage.     |
|                                                                                       |
| 5. World-Law & Plausibility Cohesion (5 pts):                                         |
|    - Adherence to the specific physical laws and escalation bounds of the scenario.   |
+---------------------------------------------------------------------------------------+
| LAYER B: HARD GUARDRAIL ANCHORS (50 POINTS)                                          |
+---------------------------------------------------------------------------------------+
| 1. Veo Video Safety Invariants (20 pts):                                              |
|    - ZERO mirror face reflections or requests for rendered human faces.               |
|    - ZERO readable digital UI numbers or clock screens on props.                      |
|    - ZERO baked-in typography, lower-third titles, or watermark text in visual prompt.|
|                                                                                       |
| 2. Terminal CTA Isolation in Scene 38 (15 pts):                                       |
|    - Channel subscribe / notification CTA is STRICTLY confined to the final sentence  |
|      of Scene 38 (the very last scene).                                               |
|    - Zero premature mentions of "subscribe", "channel", or "follow" in Scenes 1-37.   |
|                                                                                       |
| 3. 2nd-Person Invariant & 100% English Standard (15 pts):                             |
|    - 100% of scenes start with "You " or "Your ".                                     |
|    - 100% English language invariant throughout narration, visual, and sound design. |
+---------------------------------------------------------------------------------------+
```

### 3.2 Dual-Judge Execution Model
1. **Judge 1 (xAI Grok):**
   - High-reasoning model: `grok-4.6` (Chat Heavy/Expert) or cost-effective `grok-4.20-0309-non-reasoning`.
   - Focus: Deep causal consistency, thermodynamic sanity, dramatic pacing, micro-math integrity.
2. **Judge 2 (Google Gemini via CDP Port 9223):**
   - Model: `gemini-3.1-pro` (fallback to `gemini-2.5-flash`).
   - Focus: Visual framing suitability for Google Flow CDP, camera vector continuity, prompt safety, retention psychology.
3. **Pessimistic Scoring Gate:**
   $$\text{Final Score} = \min(\text{Grok Score}, \text{Gemini Score})$$
   $$\text{Passed} \iff \text{Final Score} \ge 90 \land \text{Critical Defects} = 0$$
4. **Fail-Closed Gate:**
   If `gemini_webapi` is unreachable, never silently fake or bypass review unless the user explicitly sets `--allow-deepmind-fallback`.

---

## 4. Component 3: Structured JSON Schema & Defect Taxonomy

### 4.1 Judge Output JSON Schema
Judges must return strictly conformant JSON with zero conversational preamble.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ScreenplayAdversarialReview",
  "type": "object",
  "properties": {
    "screenplay_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "description": "Computed final score after mathematical deductions from 100."
    },
    "grade": {
      "type": "string",
      "enum": ["Grade A+", "Grade A", "Grade B", "Grade C", "Grade F"]
    },
    "layer_scores": {
      "type": "object",
      "properties": {
        "holistic_directing": {
          "type": "object",
          "properties": {
            "dramatic_pacing": { "type": "integer", "minimum": 0, "maximum": 15 },
            "character_agency": { "type": "integer", "minimum": 0, "maximum": 10 },
            "retention_hooks": { "type": "integer", "minimum": 0, "maximum": 10 },
            "sensory_rhythm": { "type": "integer", "minimum": 0, "maximum": 10 },
            "world_law_cohesion": { "type": "integer", "minimum": 0, "maximum": 5 }
          },
          "required": ["dramatic_pacing", "character_agency", "retention_hooks", "sensory_rhythm", "world_law_cohesion"]
        },
        "hard_guardrails": {
          "type": "object",
          "properties": {
            "veo_safety": { "type": "integer", "minimum": 0, "maximum": 20 },
            "cta_isolation": { "type": "integer", "minimum": 0, "maximum": 15 },
            "pov_english_invariant": { "type": "integer", "minimum": 0, "maximum": 15 }
          },
          "required": ["veo_safety", "cta_isolation", "pov_english_invariant"]
        }
      },
      "required": ["holistic_directing", "hard_guardrails"]
    },
    "critique_text": {
      "type": "string",
      "description": "Adversarial executive summary of screenplay strengths, pacing analysis, and core defect synthesis."
    },
    "defects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "scene_id": {
            "type": ["integer", "string"],
            "description": "Target scene number (1-based index) or 'all'."
          },
          "category": {
            "type": "string",
            "enum": [
              "dramatic_pacing",
              "character_agency",
              "retention_hook",
              "sensory_rhythm",
              "world_law_physics",
              "veo_safety",
              "cta_isolation",
              "pov_invariant",
              "schema_contract"
            ]
          },
          "severity": {
            "type": "string",
            "enum": ["critical", "major", "minor"]
          },
          "responsible_skill": {
            "type": "string",
            "description": "Slug of the skill directory in .grok/skills/ that should learn this rule."
          },
          "issue": {
            "type": "string",
            "description": "Concrete technical explanation of why this beat violates the directing law or guardrail."
          },
          "fix_instruction": {
            "type": "string",
            "description": "Direct, actionable directive explaining how the Healer must repair the narration or visual prompt."
          },
          "rule_to_learn": {
            "type": "string",
            "description": "A single-sentence universal invariant to persist in the responsible skill's SKILL.md."
          }
        },
        "required": ["scene_id", "category", "severity", "responsible_skill", "issue", "fix_instruction", "rule_to_learn"]
      }
    }
  },
  "required": ["screenplay_score", "grade", "layer_scores", "critique_text", "defects"]
}
```

### 4.2 Defect Severity Definitions
- **Critical (Automatic Score Blocker):**
  - Premature CTA in Scenes 1–37.
  - Mirror face or explicit human face rendering request in prompt.
  - Readable typography or numerical digital UI requests.
  - Non-English narration or non-2nd-person POV.
  - Flagging a Critical defect caps the score at 89 maximum (cannot certify Grade A+).
- **Major (-5 to -8 pts):**
  - Physical/thermodynamic law violation (e.g. nitrogen snow at -120°C).
  - Pacing dead zone (> 30s of passive exposition without crisis escalation).
  - Character agency breakdown (unmotivated teleportation or nonsensical decision).
- **Minor (-1 to -3 pts):**
  - Clunky sentence rhythm or breath pacing.
  - Micro-math unit ambiguity (e.g. stating "some water" instead of "450 ml").
  - Mild camera angle redundancy across adjacent scenes.

---

## 5. Component 4: Closed-Loop Context-Aware Healing Integration

### 5.1 Full-Screenplay Context-Aware Architecture
The key architectural flaw of traditional code healers is *local myopia*: rewriting Scene 14 without seeing Scenes 1–13 and 15–38 leads to timeline contradictions, duplicated items, or broken cause-and-effect chains.

`ScreenplayHealer` implements an **Unbroken 38-Scene Context-Aware Pipeline**:
1. **Full Context Injection:**
   The entire screenplay is formatted into a compact, token-efficient JSON payload containing all 38 scenes:
   ```json
   [
     { "scene_id": 1, "duration": 8.0, "narration": "...", "visual_prompt": "...", "micro_math": "..." },
     ...
     { "scene_id": 38, "duration": 8.0, "narration": "...", "visual_prompt": "...", "micro_math": "..." }
   ]
   ```
2. **Targeted Healing Directive:**
   The healer prompt explicitly specifies:
   - The full 38-scene continuity flow.
   - The exact list of defective `target_scene_ids` to rewrite.
   - The specific `fix_instruction` and `issue` for each defective scene.
   - The rule: *Only output repaired scenes in `repaired_scenes` array; keep all other scenes untouched while ensuring the repaired scenes fit seamlessly into the timeline.*
3. **Multi-Field Reconstruction:**
   When a scene is repaired, all synchronized cinematic fields are updated:
   - `narration`: rewritten with 2nd-person invariant, sensory urgency, and spoken text sanitization.
   - `visual_prompt`: rewritten with Veo 3.1 framing (macro grips, silhouettes, zero face/UI).
   - `camera`: dynamic motion vector matching downstream flow.
   - `micro_math`: concrete physical numbers (ml, dB, % battery, minutes).
   - `sfx`: dual-stage audio prompt.

### 5.2 Deterministic Safety Polishing
Following LLM healing, scenes pass through `engine/services/screenplay_linter.py`:
- Strips any accidental speaker prefixes (`"You: "`, `"Narrator: "`).
- Ensures terminal sentence CTA isolation in Scene 38.
- Validates clean spoken English.

### 5.3 Skill Reinforcement Service (< 500-Line Health Guard)
Each healing cycle takes the `rule_to_learn` from structured defects and updates `.grok/skills/<responsible_skill>/SKILL.md`:
1. **Skill Slug Resolution:**
   `SkillResolver` resolves the responsible skill name against all 64 active skills in `.grok/skills/`.
2. **Semantic & Lexical Deduplication:**
   Rules are compared against existing guidelines using token overlap and similarity checks. Duplicates are discarded.
3. **Strict Line Health Bound (< 500 Lines):**
   - If `SKILL.md` is under 450 lines: The new invariant is appended under `### Learned Production Invariants & World-Laws`.
   - If `SKILL.md` approaches the 480-line ceiling: The service applies an LRU/relevance rolling window to condense or prune older learned rules, strictly preserving the < 500-line invariant from `AGENTS.md`.
4. **Hot-Reload:**
   Calls `get_skill_loader(force_reload=True)` to instantly invalidate memory caches so the subsequent generation or healing round operates on the updated intelligence.

---

## 6. Component 5: Zero-Hardcode & Backward Compatibility

### 6.1 Zero-Hardcode Compliance Invariants
1. **No Creative Story Text in Python:**
   No python file in `engine/services/` or `tools/` may contain scenario text, story premises, or character actions.
2. **No Hardcoded Scientific Dictionaries:**
   Hardcoded thermodynamic dictionaries (e.g. nitrogen boiling points) are removed from Python regexes and migrated into `.grok/skills/catastrophe-director/SKILL.md` and related skill files.
3. **Generic AST/Regex Pattern Matching:**
   Python linting regexes only match structural invariants (e.g. CTA words like "subscribe", or 2nd-person "You/Your"), never scenario-specific narratives.

### 6.2 Backward Compatibility with `Scorecard`
The existing `Scorecard` dataclass in `engine/services/screenplay_reviewer.py` is safely extended with default values:

```python
@dataclass
class Scorecard:
    total_score: int
    category_scores: dict[str, int]
    defects: list[str] = field(default_factory=list)
    structured_defects: list[dict[str, Any]] = field(default_factory=list)
    passed: bool = False
    grade: str = "Grade F"
    ai_critique: str | None = None
    grok_score: int | None = None
    gemini_score: int | None = None
    raw_grok_response: str | None = None
    raw_gemini_response: str | None = None
    raw_prompt: str | None = None
    
    # UPGRADE 1: Backward-compatible holistic fields
    layer_scores: dict[str, Any] = field(default_factory=dict)
    world_laws_applied: list[str] = field(default_factory=list)
```

- `to_dict()` retains all previous keys (`total_score`, `category_scores`, `defects`, `structured_defects`, `passed`, `grade`, `grok_score`, `gemini_score`) while adding optional `layer_scores`.
- `format_report()` maintains existing human-readable ASCII layout while adding the new Holistic Directing breakdown.
- Downstream CLI commands (`tools/cinematic_studio_cli.py produce-film`), handoff generators, and unit tests continue functioning without breaking changes.

---

## 7. Implementation Blueprint & Module Roadmap

| Step | Target Module | Core Changes |
|------|---------------|--------------|
| **1** | `engine/services/world_law_extractor.py` | Create dynamic extraction service to parse world laws, physics limits, and escalation stages from `.grok/skills/*.md`. |
| **2** | `engine/services/screenplay_reviewer.py` | Upgrade Grok and Gemini judge prompt generators to use the Dual-Layer Rubric (Layer A: Holistic Directing, Layer B: Hard Guardrails). Implement JSON schema validation. |
| **3** | `engine/services/screenplay_healer.py` | Wire enriched defect taxonomy into the 38-scene full-context Grok healer. Prioritize critical and major defects. |
| **4** | `engine/services/skill_reinforcement.py` | Enhance `SkillReinforcementService` with LRU rule compaction to guarantee SKILL.md never breaches 500 lines. |
| **5** | `.grok/skills/*.md` | Verify and enrich `catastrophe-director`, `planetary-catastrophe-director`, and `deepsea-survival-director` with clear World-Law and Physics sections. |
| **6** | `tests/test_screenplay_contracts.py` | Add unit tests for Dual-Layer scoring, world-law injection, fail-closed handling, and backward compatibility. |

---

## 8. Verification & Acceptance Criteria

1. **Deterministic & AI Judge Parity:**
   Screenplays missing dramatic escalation or character agency receive appropriate deductions in Layer A, even if all Layer B guardrails pass.
2. **Zero-Hardcode Verification:**
   `grep` verification confirms zero hardcoded story prose or scenario physics numbers in `engine/services/screenplay_reviewer.py`.
3. **Fail-Closed Gate:**
   Attempting AI review without an authorized Gemini endpoint raises `GeminiWebAPIUnavailableError` unless `--allow-deepmind-fallback` is set.
4. **Skill Health Bound:**
   Running continuous healing cycles across multiple screenplays never expands any `SKILL.md` beyond 500 lines.
5. **Full Test Suite Clean Pass:**
   All existing tests in `tests/test_screenplay_contracts.py` and `tests/test_screenplay_linter.py` pass with 100% success rate.
