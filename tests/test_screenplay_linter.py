"""Linter diagnoses model repair requirements without authoring creative content."""
from engine.services.screenplay_linter import lint_scenes, sanitize_prompt, _fix_pov, _strip_premature_cta, _strip_veo_violations

def test_valid_pov_is_preserved():
    text = "You cross the shelter threshold."
    assert _fix_pov(text,0) == (text,None)

def test_invalid_pov_is_reported_without_prose_injection():
    text = "The sky darkens."
    unchanged, issue = _fix_pov(text,0)
    assert unchanged == text
    assert "ERROR" in issue and "model-authored" in issue

def test_empty_narration_requires_model_repair():
    assert _fix_pov("",0)[0] == ""
    assert "empty" in _fix_pov("",0)[1]

def test_premature_cta_is_reported_without_dropping_story_sentences():
    text = "You listen. Subscribe now."
    assert _strip_premature_cta(text,0,2)[0] == text
    assert "premature CTA" in _strip_premature_cta(text,0,2)[1]

def test_final_cta_preserved():
    text = "You listen. Subscribe now."
    assert _strip_premature_cta(text,1,2) == (text,None)

def test_veo_violation_is_reported_without_visual_substitutions():
    text = "A mirror reflecting your face"
    assert _strip_veo_violations(text,0)[0] == text
    assert "guardrail" in _strip_veo_violations(text,0)[1]

def test_broll_can_contain_readable_graphics():
    text = "[DATA_BROLL] digital display showing numbers"
    assert _strip_veo_violations(text,0) == (text,None)

def test_sanitize_prompt_preserves_authored_direction_and_negatives():
    text = "A close view --no lens flare"
    assert sanitize_prompt("  " + text + "  ") == text
    assert sanitize_prompt("") == ""

def test_lint_deep_copies_and_reports_meaningful_errors():
    scenes = [{"narration":"The sky darkens.","visual_prompt":"digital display reading 123"}]
    result,diagnostics = lint_scenes(scenes)
    assert result == scenes and result is not scenes and result[0] is not scenes[0]
    assert any("POV" in d for d in diagnostics)
    assert any("guardrail" in d for d in diagnostics)
    assert any("micro_math" in d for d in diagnostics)

def test_repetition_never_replaces_original_narration():
    scene = {"narration":"You check the doorway.","visual_prompt":"doorway","micro_math":"4 seconds"}
    result,diagnostics = lint_scenes([scene,scene])
    assert result == [scene,scene]
    assert any("repetitive" in d for d in diagnostics)

def test_direct_negative_visuals_do_not_trigger_but_positive_or_ambiguous_do():
    negative = "A shelter, no faces, no dials, no gauges, no readable text"
    assert _strip_veo_violations(negative, 0)[1] is None
    assert _strip_veo_violations("A shelter, no faces, gauges", 0)[1]
    assert _strip_veo_violations("A shelter, no faces or gauges", 0)[1]

def test_linter_errors_block_review_even_with_two_high_judge_scores(monkeypatch):
    from engine.services.screenplay_reviewer import ScreenplayReviewer
    reviewer = ScreenplayReviewer(xai_api_key="test", short_test=True)
    judge = lambda *args, **kwargs: {"screenplay_score": 99, "defects": []}
    monkeypatch.setattr(reviewer, "_consult_grok_critique", judge)
    monkeypatch.setattr(reviewer, "_consult_gemini_critique", judge)
    scenes = [{"narration": "You wait. You subscribe.", "visual_prompt": "A gauge", "micro_math": "1 second"}]
    card = reviewer.review(scenes, consult_ai=True)
    assert not card.passed
    assert any("Veo visual guardrail violation" in defect for defect in card.defects)
