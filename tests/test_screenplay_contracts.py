"""Regressions for production quality gates, named models and explicit simulation."""
import asyncio
import json
from unittest.mock import Mock
import pytest
from engine.services.screenplay_reviewer import ScreenplayReviewer
from engine.services.universal_narrative import generate_catastrophe_scenes, generate_5act_script, UniversalNarrativeEngine, screenplay_schema

@pytest.fixture
def baseline():
    scenes = generate_catastrophe_scenes("Offline audit fixture",300,simulation=True)
    # Rubric tests use explicit test-only data without the simulation blocker.
    for scene in scenes:
        scene.pop("simulation_only", None)
    return scenes

@pytest.mark.parametrize("score",[0,70,78,80,89,89.9])
def test_sub90_judges_never_certify(monkeypatch,baseline,score):
    reviewer=ScreenplayReviewer(xai_api_key="test-only")
    monkeypatch.setattr(reviewer,"_consult_grok_critique",lambda *a: {"screenplay_score":score})
    monkeypatch.setattr(reviewer,"_consult_gemini_critique",lambda *a: {"screenplay_score":99})
    card=reviewer.review(baseline,consult_ai=True)
    assert not card.passed
    assert card.grade != "Grade A+"

@pytest.mark.parametrize("invalid",[True,False,"99",float("nan"),float("inf"),-1,101,None])
def test_malformed_judge_scores_fail_closed(monkeypatch,baseline,invalid):
    reviewer=ScreenplayReviewer(xai_api_key="test-only")
    monkeypatch.setattr(reviewer,"_consult_grok_critique",lambda *a: {"screenplay_score":invalid})
    monkeypatch.setattr(reviewer,"_consult_gemini_critique",lambda *a: {"screenplay_score":99})
    card=reviewer.review(baseline,consult_ai=True)
    assert not card.passed
    assert any("Grok judge did not return a valid score" in d for d in card.defects)

def test_grok_named_pin_beats_environment(monkeypatch):
    monkeypatch.setenv("XAI_CHAT_MODEL","grok-4.6")
    monkeypatch.setenv("XAI_MODEL","grok-4.6")
    captured=[]
    # Capture request and stop before parsing; the reviewer caller handles transport errors.
    def request(req,**kwargs):
        captured.append(json.loads(req.data))
        raise RuntimeError("test transport")
    monkeypatch.setattr("urllib.request.urlopen",request)
    reviewer=ScreenplayReviewer(xai_api_key="test-only",grok_model="grok-4.20-non-reasoning")
    with pytest.raises(RuntimeError): reviewer._consult_grok_critique([],"test","catastrophe",[])
    assert captured[0]["model"] == "grok-4.20-0309-non-reasoning"

def test_gemini_named_model_has_no_implicit_fallback(monkeypatch):
    from engine.providers.gemini_webapi import call_gemini_chat
    post=Mock(side_effect=RuntimeError("unavailable"))
    monkeypatch.setattr("engine.providers.gemini_webapi._post_with_retry",post)
    with pytest.raises(RuntimeError): call_gemini_chat("test",model="gemini-3.1-pro")
    assert [call.args[0]["model"] for call in post.call_args_list] == ["gemini-3.1-pro"]

def test_gemini_explicit_fallback_allowlist(monkeypatch):
    from engine.providers.gemini_webapi import call_gemini_chat
    post=Mock(side_effect=[RuntimeError("unavailable"),{"choices":[{"message":{"content":"valid"}}]}])
    monkeypatch.setattr("engine.providers.gemini_webapi._post_with_retry",post)
    assert call_gemini_chat("test",model="primary",fallback_models=("consented-alternative",)) == "valid"
    assert [call.args[0]["model"] for call in post.call_args_list] == ["primary","consented-alternative"]

def test_no_provider_never_fabricates_a_live_screenplay():
    with pytest.raises(RuntimeError,match="requires an LLM"):
        generate_catastrophe_scenes("Live production")

def test_live_failure_never_uses_simulation(monkeypatch):
    class Failing:
        async def generate_script(self,**kwargs): raise RuntimeError("authoring unavailable")
    with pytest.raises(RuntimeError,match="authoring unavailable"):
        generate_5act_script("Live",llm_provider=Failing())

def test_simulation_is_explicit_and_marked():
    scenes=generate_catastrophe_scenes("simulation",60,simulation=True)
    assert all(s["simulation_only"] for s in scenes)
    assert sum(s["duration"] for s in scenes) == pytest.approx(60)

def test_authoring_uses_injected_skill_loader_and_broll_contract():
    loader=Mock()
    loader.build_unified_system_prompt.return_value="injected directing rules"
    class Provider:
        def __init__(self): self.calls=[]
        async def generate_script(self,**kwargs):
            self.calls.append(kwargs)
            count=kwargs["schema"]["properties"]["scenes"]["minItems"]
            return {"scenes":[{"narration":"You inspect the test fixture.","visual_prompt":"test fixture","duration":4,"motion_prompt":"","micro_math":"4s"} for _ in range(count)]}
    provider=Provider()
    result=UniversalNarrativeEngine(skill_loader=loader,llm_provider=provider).generate_screenplay("User topic",duration=20)
    assert len(result)==5
    assert loader.build_unified_system_prompt.call_count==1
    assert provider.calls[0]["system_prompt"].startswith("injected directing rules")
    assert "GeospatialStormMap" in provider.calls[0]["system_prompt"]
    fields=screenplay_schema(1)["properties"]["scenes"]["items"]["properties"]
    assert {"is_data_broll","template_name","data_payload"} <= fields.keys()

@pytest.mark.parametrize("field",["narration","visual_prompt"])
def test_missing_authored_text_cannot_certify(monkeypatch,baseline,field):
    baseline[0][field]=""
    reviewer=ScreenplayReviewer(xai_api_key="test-only")
    monkeypatch.setattr(reviewer,"_consult_grok_critique",lambda *a:{"screenplay_score":99})
    monkeypatch.setattr(reviewer,"_consult_gemini_critique",lambda *a:{"screenplay_score":99})
    card=reviewer.review(baseline,consult_ai=True)
    assert not card.passed
    assert any(field in defect for defect in card.defects)

def test_healer_explicit_empty_key_does_not_read_environment(monkeypatch):
    from engine.services.screenplay_healer import ScreenplayHealer
    monkeypatch.setenv("XAI_API_KEY","unrelated-account-key")
    assert ScreenplayHealer(xai_api_key="").xai_api_key == ""


def test_cli_simulation_handoff_never_certifies_or_resumes_live(monkeypatch,tmp_path):
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app
    import cli.produce_commands as commands
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setattr(commands,"_ROOT",tmp_path)
    runner=CliRunner()
    args=["produce-film","Explicit offline example","--duration","60"]
    dry=runner.invoke(app,args+["--dry-run","--plan-only"])
    assert dry.exit_code==0, dry.stdout
    handoff=json.loads(next((tmp_path/"sequences").glob("*_handoff.json")).read_text(encoding="utf-8"))
    assert not handoff["adversarial_review"]["passed"]
    assert all(scene["simulation_only"] for scene in handoff["scenes"])
    live=runner.invoke(app,args+["--force-render","--yes"])
    assert live.exit_code==1
    assert "Live authoring requires" in live.stdout


def test_cli_force_render_cannot_promote_simulation_model_output(monkeypatch,tmp_path,baseline):
    from typer.testing import CliRunner
    from tools.cinematic_studio_cli import app
    import cli.produce_commands as commands
    monkeypatch.setenv("XAI_API_KEY","fake-test-key")
    for scene in baseline:
        scene["simulation_only"] = True
    monkeypatch.setattr(commands,"_ROOT",tmp_path)
    monkeypatch.setattr(commands.UniversalNarrativeEngine,"generate_screenplay",lambda *a,**kw:baseline)
    execute=Mock()
    monkeypatch.setattr(commands,"execute_grok_flow_production",execute)
    result=CliRunner().invoke(app,["produce-film","Simulation must stop","--duration","300","--force-render","--yes"])
    assert result.exit_code==1, result.stdout
    assert "Simulation scenes cannot be rendered" in result.stdout
    execute.assert_not_called()


def test_authoring_rejects_incomplete_broll_payload():
    class Provider:
        async def generate_script(self,**kwargs):
            return {"scenes":[{"narration":"You inspect the graph.","visual_prompt":"[DATA_BROLL]","is_data_broll":True,"template_name":"TelemetryCurve","data_payload":{},"duration":4,"motion_prompt":"","micro_math":"4s"}]}
    with pytest.raises(ValueError,match="B-roll requires"):
        generate_5act_script("Graph",duration=20,llm_provider=Provider())
