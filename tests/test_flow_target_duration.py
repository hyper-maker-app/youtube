import asyncio

import pytest


@pytest.mark.parametrize("measured,blocked", [(102.16, True), (12.5, False)])
def test_voice_duration_gate_runs_before_video_generation(tmp_path, monkeypatch, measured, blocked):
    import engine.flow_bridge as bridge

    class Voice:
        async def generate_narration(self, *, beats, out_path, lang):
            out_path.write_bytes(b"test voice data")
            return {"vo_path": str(out_path), "duration": measured, "words": []}

    monkeypatch.setattr(bridge, "get_voice_provider", lambda _: Voice())
    calls = []

    def pack(**kwargs):
        calls.append(True)
        raise RuntimeError("reached video allocation")

    monkeypatch.setattr(bridge, "pack_durations_to_veo_blocks", pack)
    scenes = [{"id": "scene_01", "narration": "You wait.", "duration": 12}]
    expected = ValueError if blocked else RuntimeError
    with pytest.raises(expected, match="exceeds target" if blocked else "reached video allocation"):
        asyncio.run(bridge.execute_grok_flow_production(
            project_title="duration test", scenes=scenes, out_dir=tmp_path,
            target_duration=12,
        ))
    assert bool(calls) is not blocked
