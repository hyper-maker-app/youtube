"""Provider-native generation and audio-clock alignment regressions."""
import pytest
from engine.services.duration_packer import (
    VEO_NATIVE_TIERS, MAX_VEO_SHOT_DURATION, pack_durations_to_veo_blocks,
    split_scene_durations, snap_to_veo_tier,
)
from engine.providers.flow_contract import default_capabilities


def test_native_durations_match_actual_provider_contract():
    assert VEO_NATIVE_TIERS == tuple(default_capabilities().supported_native_durations)
    for requested in (5, 5.2, 6, 8, 10, 100):
        native = split_scene_durations(requested)
        assert set(native) <= set(VEO_NATIVE_TIERS)
        assert max(native) <= MAX_VEO_SHOT_DURATION
        assert sum(native) >= requested
    assert snap_to_veo_tier(5) == 6


def test_six_second_scenes_have_contiguous_audio_slots():
    plans = pack_durations_to_veo_blocks([{"id":"a", "duration":6}, {"id":"b", "duration":6}], 12)
    assert [(p.audio_t0,p.audio_t1) for p in plans] == [(0,6),(6,12)]
    assert all(p.veo_duration >= p.speech_duration for p in plans)
    assert sum(p.speech_duration for p in plans) == 12


def test_eight_second_scene_native_preservation():
    scene = {"id": "hero_scene", "duration": 8.0, "narration": "You stare into the raging vortex."}
    plans = pack_durations_to_veo_blocks([scene], 8.0)
    assert len(plans) == 1
    assert plans[0].scene_id == "hero_scene"
    assert plans[0].veo_duration == 8.0
    assert plans[0].audio_t0 == 0.0
    assert plans[0].audio_t1 == 8.0
    assert plans[0].speech_duration == 8.0
    assert split_scene_durations(8.0) == [8.0]
    assert split_scene_durations(7.5) == [8.0]
    assert split_scene_durations(8.5) == [8.0]


def test_measured_voice_duration_scales_scene_windows_without_final_overflow():
    plans = pack_durations_to_veo_blocks([{"duration":4},{"duration":4}], 20)
    assert plans[-1].audio_t1 == 20
    assert all(p.veo_duration >= p.speech_duration for p in plans)
    assert sum(p.speech_duration for p in plans) == pytest.approx(20)


def test_broll_keeps_exact_duration_and_authored_metadata():
    scene={"id":"chart", "duration":6, "is_data_broll":True,
           "data_broll_template":"TelemetryCurve", "data_broll_payload":{"label":"sample"}}
    plans=pack_durations_to_veo_blocks([scene],6)
    assert len(plans)==1
    assert plans[0].veo_duration==6
    assert plans[0].scene_metadata==scene
    scene["data_broll_payload"]["label"]="changed"
    assert plans[0].scene_metadata["data_broll_payload"]["label"]=="sample"


@pytest.mark.parametrize("duration", [0,-1,float("inf"),float("nan")])
def test_invalid_duration_fails_early(duration):
    with pytest.raises(ValueError):
        split_scene_durations(duration)


def test_uneven_spoken_scenes_follow_provider_word_boundaries():
    scenes=[{"id":"a","duration":6,"narration":"You move."},
            {"id":"b","duration":6,"narration":"You carefully inspect the sealed door."}]
    tokens=["You", "move", "You", "carefully", "inspect", "the", "sealed", "door"]
    starts=[0,1,2,3,5,7,9,11]
    words=[{"text":text,"start":start,"end":start+0.4} for text,start in zip(tokens,starts)]
    plans=pack_durations_to_veo_blocks(scenes,12,words)
    assert next(p for p in plans if p.scene_id.startswith("b")).audio_t0 == 2
    assert plans[0].speech_duration == 2
    assert plans[-1].audio_t1 == 12


def test_word_beat_ids_take_priority_over_nominal_scene_lengths():
    scenes=[{"id":"a","duration":6},{"id":"b","duration":6}]
    plans=pack_durations_to_veo_blocks(scenes,12,[{"beat_id":"b","start":3,"end":4}])
    assert next(p for p in plans if p.scene_id.startswith("b")).audio_t0 == 3
