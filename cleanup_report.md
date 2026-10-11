# Cleanup audit

Manifest hash: `f8704c75adb26b40887d85214baf36803208ba5cd608353191630528901815bf`

| Path | Classification | Size | Recommended action |
| --- | --- | ---: | --- |
| `.claude` | required_state | 2833 | keep or manually review |
| `.codex` | manual_review | 74 | keep or manually review |
| `.cursorrules` | required_state | 1321 | keep or manually review |
| `.env` | required_state | 1833 | keep or manually review |
| `__pycache__` | generated_rebuildable | 386730 | quarantine |
| `_flow_bones.txt` | historical_diagnostic | 17941 | keep or manually review |
| `_gen_log.txt` | historical_diagnostic | 469 | keep or manually review |
| `_gen_scripts.py` | manual_review | 1774 | keep or manually review |
| `_one_run.txt` | historical_diagnostic | 1699 | keep or manually review |
| `_pipeline_mcp.py` | active | 1658 | keep or manually review |
| `_prompt_study.py` | manual_review | 4009 | keep or manually review |
| `_resume_log.txt` | historical_diagnostic | 2194 | keep or manually review |
| `_stream.txt` | historical_diagnostic | 124 | keep or manually review |
| `_study_llm` | historical_diagnostic | 185198 | keep or manually review |
| `_t_q` | historical_diagnostic | 3378055 | keep or manually review |
| `_timing.txt` | historical_diagnostic | 1105 | keep or manually review |
| `_timing2.txt` | historical_diagnostic | 174 | keep or manually review |
| `_verify.txt` | historical_diagnostic | 454 | keep or manually review |
| `_voice_samples` | historical_diagnostic | 1155344 | keep or manually review |
| `AGENTS.md` | required_state | 1321 | keep or manually review |
| `assets` | required_state | 23179 | keep or manually review |
| `assets.py` | active | 8194 | keep or manually review |
| `captions.py` | active | 8149 | keep or manually review |
| `chat.py` | manual_review | 3436 | keep or manually review |
| `CLAUDE.md` | required_state | 1319 | keep or manually review |
| `cleanup.py` | active | 13271 | keep or manually review |
| `config.py` | active | 39749 | keep or manually review |
| `DURUM.md` | active | 18991 | keep or manually review |
| `editor.py` | active | 35765 | keep or manually review |
| `generator.py` | active | 148290 | keep or manually review |
| `main.py` | active | 14194 | keep or manually review |
| `metadata.py` | active | 3962 | keep or manually review |
| `out` | required_state | 274332188 | keep or manually review |
| `pipeline.py` | active | 45551 | keep or manually review |
| `pipeline_stats.db` | required_state | 8192 | keep or manually review |
| `requirements.txt` | manual_review | 205 | keep or manually review |
| `scripts_data.py` | manual_review | 24865 | keep or manually review |
| `tests` | required_state | 30823 | keep or manually review |
| `voices_resp.json` | historical_diagnostic | 102976 | keep or manually review |
| `out/why-airplane-windows-have-a-tiny-hole_20260901_163237` | manual_review | 0 | manual review |
| `out/why-airplane-windows-have-a-tiny-hole_20260902_123301` | manual_review | 0 | manual review |
| `out/why-deep-sea-fish-explode-when-pulled-to-the-sur_20260902_094455` | manual_review | 0 | manual review |
| `out/why-scuba-divers-can-explode-from-the-inside_20260902_094403` | manual_review | 0 | manual review |
| `out/why-your-heart-never-gets-cancer_20260901_165210` | manual_review | 0 | manual review |
| `out/why-your-stomach-doesn-t-digest-itself_20260902_094316` | manual_review | 0 | manual review |
| `out/why-your-stomach-doesn-t-digest-itself_20260902_112408` | manual_review | 0 | manual review |

Only `generated_rebuildable` entries marked eligible can be quarantined by this command.
Historical logs, voice samples, helpers, output runs, assets, databases, configuration, and integrations remain protected for manual review.
