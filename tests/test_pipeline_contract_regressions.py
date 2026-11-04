"""Offline regressions for production metadata, timeline trim, and B-roll gates."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pytest
from engine import config, editor
from engine.flow_bridge import aligned_block_scene, is_scene_data_broll
from engine.services.duration_packer import pack_durations_to_veo_blocks
from engine.services.boundary_inspector import inspect_transition_boundary


def test_flag_only_broll_preserves_payload_and_canonical_aliases():
    scene={"duration":6,"is_data_broll":True,"data_broll_template":"TelemetryCurve",
           "data_broll_payload":{"metricName":"Pressure", "dataPoints":[1,2]}, "focus_entity":"e1"}
    aligned=aligned_block_scene(pack_durations_to_veo_blocks([scene],6)[0])
    assert is_scene_data_broll(aligned)
    assert aligned["template_name"]=="TelemetryCurve"
    assert aligned["data_payload"]==scene["data_broll_payload"]
    assert aligned["focus_entity"]=="e1"


def test_editor_trims_native_sources_to_exact_audio_slots(tmp_path):
    def fake_probe(path, *args):
        return editor.MediaInfo(Path(path),12 if str(path).endswith("voice.wav") else 4,
                                1920,1080,60,True,False)
    with patch.object(editor,"probe",side_effect=fake_probe), patch.object(editor,"_run",return_value=SimpleNamespace(returncode=0,stderr="")):
        argv,graph=editor.render(block_paths=[tmp_path/f"b{i}.mp4" for i in range(4)],
            vo_path=tmp_path/"voice.wav",out_path=tmp_path/"final.mp4",punch_times=[],
            timeline_durations=[3,3,3,3],target_len=12+config.TAIL_HOLD,dry_run=True)
    for index in range(4):
        assert f"[{index}:v]trim=duration=3.000" in graph
    assert argv[argv.index("-t")+1]==f"{12+config.TAIL_HOLD:.3f}"


@pytest.mark.parametrize("dry_run",[False,True])
def test_broll_qa_rejects_wrong_resolution_and_missing_previous_file(tmp_path,dry_run):
    block=tmp_path/"next.mp4";block.write_bytes(b"x"*1001)
    with patch("engine.services.boundary_inspector.extract_video_frame",return_value=np.zeros((144,256,3),dtype=np.uint8)):
        report=asyncio.run(inspect_transition_boundary(None,tmp_path/"missing.mp4",block,
                          is_data_broll=True,dry_run=dry_run))
    assert not report.passed
    assert len(report.violations)==2


def test_broll_qa_respects_portrait_and_native_flow_resolution(tmp_path):
    previous=tmp_path/"previous.mp4";previous.write_bytes(b"x"*1001)
    current=tmp_path/"next.mp4";current.write_bytes(b"x"*1001)
    with patch("engine.services.boundary_inspector.extract_video_frame",side_effect=[np.zeros((1280,720,3),dtype=np.uint8),np.zeros((1920,1080,3),dtype=np.uint8)]):
        report=asyncio.run(inspect_transition_boundary(None,previous,current,
            is_data_broll=True,expected_width=1080,expected_height=1920))
    assert report.passed


def test_many_fractional_slots_quantize_cumulative_edges(tmp_path):
    import re
    durations=[1.007]*80
    def fake_probe(path,*args):
        return editor.MediaInfo(Path(path),sum(durations) if str(path).endswith("voice.wav") else 4,
                                1920,1080,60,True,False)
    with patch.object(editor,"probe",side_effect=fake_probe), patch.object(editor,"_run",return_value=SimpleNamespace(returncode=0,stderr="")):
        _,graph=editor.render(block_paths=[tmp_path/f"b{i}.mp4" for i in range(len(durations))],
            vo_path=tmp_path/"voice.wav",out_path=tmp_path/"final.mp4",punch_times=[],
            timeline_durations=durations,dry_run=True)
    frame_counts=[int(value) for value in re.findall(r"trim=end_frame=(\d+)",graph)]
    assert len(frame_counts)==len(durations)
    for index in range(1,len(durations)+1):
        assert abs(sum(frame_counts[:index])/60-sum(durations[:index])) <= 1/60


def test_map_to_cinematic_cut_has_no_map_first_frame(tmp_path, monkeypatch):
    import engine.flow_bridge as flow
    from engine.services.boundary_inspector import BoundaryQAReport
    class StopBeforeAudio(BaseException):
        pass
    calls=[]
    voice_calls=[]
    rendered_payloads=[]
    async def voice(**kwargs):
        voice_calls.append(kwargs)
        path=kwargs["out_path"];path.write_bytes(b"x"*10001)
        return {"vo_path":path,"duration":8,"words":[]}
    async def video(**kwargs):
        calls.append(kwargs)
        kwargs["out_path"].write_bytes(b"x"*1001)
    def remotion(**kwargs):
        kwargs["output_path"].write_bytes(b"x"*1001)
        rendered_payloads.append(kwargs["data_payload"])
    async def qa(**kwargs):
        return BoundaryQAReport(1,True)
    def stop(*args):
        raise StopBeforeAudio()
    monkeypatch.setattr(flow,"get_voice_provider",lambda *args:SimpleNamespace(generate_narration=voice))
    monkeypatch.setattr(flow,"get_video_provider",lambda *args:SimpleNamespace(animate_block=video))
    monkeypatch.setattr(flow,"render_remotion_broll",remotion)
    monkeypatch.setattr(flow,"inspect_transition_boundary",qa)
    monkeypatch.setattr(flow,"get_sfx_provider",stop)
    monkeypatch.setattr(flow,"extract_video_frame",lambda *args,**kwargs:pytest.fail("Map frame was read for cinematic conditioning"))
    monkeypatch.setattr(flow,"validate_video_source",lambda *args,**kwargs:None)
    scenes=[{"id":"chart","duration":4,"is_data_broll":True,"data_broll_template":"TelemetryCurve",
             "data_broll_payload":{"source":"authored"}},
            {"id":"shot","duration":4,"visual_prompt":"Physical scene"}]
    for source in ("authored","updated","updated"):
        scenes[0]["data_broll_payload"]={"source":source}
        with pytest.raises(StopBeforeAudio):
            asyncio.run(flow.execute_grok_flow_production(project_title="Contract test",scenes=scenes,out_dir=tmp_path))
    assert rendered_payloads==[{"source":"authored"},{"source":"updated"}]
    assert len(voice_calls)==1
    assert len(calls)==1
    assert calls[0]["start_frame"] is None



def test_countdown_requires_authored_headline(tmp_path):
    with pytest.raises(ValueError,match="explicit countdown_text"):
        editor.build_video_filter(1,[],block_durations=[4],enable_countdown=True)
    with pytest.raises(ValueError,match="explicit banner_text"):
        editor.apply_extinction_countdown_overlay(tmp_path/"input.mp4",tmp_path/"out.mp4")


def test_cache_fingerprint_rejects_legacy_and_changed_payload(tmp_path):
    from engine.flow_bridge import production_fingerprint, cache_matches, write_cache_fingerprint
    block=tmp_path/"block.mp4"; block.write_bytes(b"source")
    signature=production_fingerprint({"template":"chart","payload":{"values":[1,2]},"duration":4})
    assert not cache_matches(block,signature)
    write_cache_fingerprint(block,signature)
    assert cache_matches(block,signature)
    changed=production_fingerprint({"template":"chart","payload":{"values":[2,3]},"duration":4})
    assert not cache_matches(block,changed)
    assert not cache_matches(block,production_fingerprint({"duration":5}))


def test_real_mixed_fps_render_keeps_short_silence_finite(tmp_path,monkeypatch):
    import subprocess
    ffmpeg=editor.config.resolve_ffmpeg()
    for key,value in (("WIDTH",640),("HEIGHT",360),("LONGFORM_MODE",True)):
        monkeypatch.setattr(editor.config,key,value)
    blocks=[]
    for rate in (24,30,60):
        block=tmp_path/f"source_{rate}.mp4";blocks.append(block)
        subprocess.run([ffmpeg,"-v","error","-y","-f","lavfi","-i",f"color=black:s=640x360:r={rate}","-t","0.7","-c:v","libx264",str(block)],check=True,capture_output=True)
    voice=tmp_path/"voice.wav"
    subprocess.run([ffmpeg,"-v","error","-y","-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-t","1.3",str(voice)],check=True,capture_output=True)
    output=tmp_path/"final.mp4"
    editor.render(block_paths=blocks,vo_path=voice,out_path=output,punch_times=[],
                  timeline_durations=[.317,.433,.55],target_len=1.3+editor.config.TAIL_HOLD,final_polish=False)
    info=editor.probe(output)
    assert info.fps==60
    assert info.duration==pytest.approx(1.3+editor.config.TAIL_HOLD,abs=1/60)
    video_frames=subprocess.run([ffmpeg,"-v","error","-i",str(output),"-map","0:v","-an","-f","framemd5","-"],check=True,capture_output=True,text=True)
    actual_frames=sum(1 for line in video_frames.stdout.splitlines() if line and not line.startswith("#"))
    assert actual_frames==round((1.3+editor.config.TAIL_HOLD)*60)
    decoded=subprocess.run([ffmpeg,"-v","error","-i",str(output),"-map","0:a","-f","f32le","-"],check=True,capture_output=True)
    samples=np.frombuffer(decoded.stdout,dtype=np.float32)
    assert samples.size>0 and np.isfinite(samples).all()
    assert np.max(np.abs(samples))==0


def test_cinematic_reference_chain_and_voice_cache_invalidate(tmp_path,monkeypatch):
    import engine.flow_bridge as flow
    from engine.services.boundary_inspector import BoundaryQAReport
    class StopBeforeAudio(BaseException):
        pass
    videos=[];voices=[]
    async def voice(**kwargs):
        voices.append(kwargs["beats"])
        kwargs["out_path"].write_bytes(b"x"*10001)
        return {"vo_path":kwargs["out_path"],"duration":8,"words":[]}
    async def video(**kwargs):
        videos.append(kwargs)
        kwargs["out_path"].write_bytes(kwargs["motion_prompt"].encode()*200)
    async def qa(**kwargs):
        return BoundaryQAReport(1,True)
    def stop(*args):
        raise StopBeforeAudio()
    monkeypatch.setattr(flow,"get_voice_provider",lambda *args:SimpleNamespace(generate_narration=voice))
    monkeypatch.setattr(flow,"get_video_provider",lambda *args:SimpleNamespace(animate_block=video))
    monkeypatch.setattr(flow,"inspect_transition_boundary",qa)
    monkeypatch.setattr(flow,"get_sfx_provider",stop)
    monkeypatch.setattr(flow,"extract_video_frame",lambda *args,**kwargs:np.zeros((16,16,3),dtype=np.uint8))
    monkeypatch.setattr(flow,"validate_video_source",lambda *args,**kwargs:None)
    scenes=[{"id":"a","duration":4,"visual_prompt":"First physical scene", "narration":"Sample one"},
            {"id":"b","duration":4,"visual_prompt":"Next physical scene", "narration":"Sample two"}]
    for version in ("original","changed","changed"):
        scenes[0]["visual_prompt"]=f"First physical scene {version}"
        scenes[0]["narration"]=f"Sample one {version}"
        with pytest.raises(StopBeforeAudio):
            asyncio.run(flow.execute_grok_flow_production(project_title="Cache contract",scenes=scenes,out_dir=tmp_path))
    assert len(voices)==2
    assert len(videos)==4
    assert videos[1]["start_frame"] is not None
    assert videos[3]["start_frame"] is not None


def test_concurrent_output_graphs_do_not_share_a_path(tmp_path):
    first=editor._write_render_graph(tmp_path/"one.mp4","first graph")
    second=editor._write_render_graph(tmp_path/"two.mp4","second graph")
    assert first!=second
    assert first.read_text(encoding="utf-8")=="first graph"
    assert second.read_text(encoding="utf-8")=="second graph"
