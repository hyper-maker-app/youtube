# EPISODE RUNTIME STANDARD & CLIFFHANGER ELASTICITY POLICY
**Studio:** Grok Imagine Cinematic Studio v3.11.4  
**Applies To:** All Episodic Productions (Global Micro-Series & Web Formats)  
**Authorizing Agents:** Studio Director, Sequence Director, Narrative Arc Pacing Strategist, Workflow Quota Optimizer  

---

## 1. Universal Baseline Runtime Rule

```yaml
episode_duration_policy:
  baseline_target_seconds: 150 # 2 minutes 30 seconds (02:30)
  elasticity_seconds: [-10, 10] # Dynamic range: 140s to 160s (02:20 - 02:40)
  target_clip_length: "8-12s preferred"
  nominal_clip_count: 14-16 # Per episode
  status: SYSTEM_WIDE_DEFAULT
```

* **Standard Duration:** **2.5 Minutes (150 Seconds)** per episode.
* **Scope:** Locked as the system-wide baseline for all episodic productions unless explicitly overridden by a feature-length directive.

---

## 2. Dynamic Cliffhanger Elasticity Protocol (±5s to 10s)

To maximize emotional tension, viral retention, and dramatic cliffhangers, the runtime is **elastic**:

### A. Positive Extension (+5s to +10s | Max: 160s / 02:40)
* **Trigger:** When a dramatic cliffhanger requires:
  * A sustained slow pull-out or crane shot revealing an oncoming swarm or scale.
  * A lingering silence, character eye tremor, or delayed gunshot fade.
  * An audio build-up (sub-bass drone or orchestral riser) that needs 5–10 extra seconds to peak.

### B. Negative Compression (-5s to -10s | Min: 140s / 02:20)
* **Trigger:** When a scene calls for an abrupt **Smash Cut to Black**:
  * An unexpected jump-scare attack or breach.
  * A sudden blackout, explosion, or mid-sentence cut.
  * Holding any further would drain the shock value and pacing momentum.

---

## 3. Sequence Director & Quota Optimizer Integration

When calculating clip batches and video extend chains:
1. **Target:** 150 seconds $\approx$ 15 clips of 10s.
2. **Elasticity Buffer:** Clip 15 can be trimmed to 5s (smash cut) or extended with a 16th clip (up to 160s) solely based on the `CLIFFHANGER_HOOK_VECTOR`.
3. **No Padding:** Never fill time with dead air; if the dramatic arc concludes cleanly at 02:22, cut immediately.
