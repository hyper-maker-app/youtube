"""Tests for Model A Hybrid Longform Time-Traveler Documentary Architecture (ADR-043)."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pytest

import config
from services.character import (
    DEFAULT_CHARACTER,
    CharacterProfile,
    CharacterSheetSpec,
    detect_era,
    get_active_character,
    classify_shot_role,
    compile_character_shot_prompt,
)
from services.script_engine import (
    Beat,
    Script,
    Shot,
    compile_keyframe_prompt,
    optimize_for_flow,
    validate_script,
    _canonicalize_model_brief,
)
from services.mode_profile import EXPLORER, ANATOMICAL, INCIDENT
from core.narrative_longform import LongformEngine
from providers.base import BaseLLMProvider
import editor
from services.historical_research import get_historical_truth_sheet
from services.screenplay import generate_dynamic_screenplay
from providers.video.playwright_flow import sanitize_flow_prompt


class MockLLM(BaseLLMProvider):
    async def generate_script(self, topic: str, system_prompt: str, schema: dict) -> dict:
        return {}


def test_character_profile_time_traveler_invariants():
    """Verify Nova persona facial features lock, temporal chronometer artifact, and era camouflage."""
    char = get_active_character()
    assert char.name == "Nova"
    assert "hazel eyes" in char.face_traits.lower()
    assert "freckles" in char.face_traits.lower()
    assert "temporal chronometer" in char.time_device.lower()
    assert "gyroscopic" in char.time_device.lower()

    # Anchor description must contain immutable facial lock, signature artifact, and wardrobe
    anchor = char.anchor_description("default")
    assert "FACE LOCK:" in anchor
    assert "SIGNATURE ARTIFACT:" in anchor
    assert "WARDROBE CAMOUFLAGE:" in anchor
    assert "temporal chronometer" in anchor.lower()


def test_era_detection_and_wardrobe_camouflage():
    """Verify era detection from topics and corresponding period-accurate wardrobe."""
    char = get_active_character()

    # Egyptian
    assert detect_era("The Lost Labyrinth of Hawara in Egypt") == "egyptian"
    egyptian_wardrobe = char.wardrobe_for_era("egyptian")
    assert "linen" in egyptian_wardrobe.lower()
    assert "kalasiris" in egyptian_wardrobe.lower()

    # Greco-Roman
    assert detect_era("Secret Chambers of the Roman Colosseum") == "greco_roman"
    roman_wardrobe = char.wardrobe_for_era("greco_roman")
    assert "chiton" in roman_wardrobe.lower()

    # Ottoman
    assert detect_era("Subterranean Cisterns of Ottoman Istanbul") == "ottoman"
    ottoman_wardrobe = char.wardrobe_for_era("ottoman")
    assert "entari" in ottoman_wardrobe.lower()

    # Neolithic
    assert detect_era("The Megalithic Enclosures of Göbeklitepe") == "neolithic"
    neolithic_wardrobe = char.wardrobe_for_era("neolithic")
    assert "deerskin" in neolithic_wardrobe.lower()

    # Default / Modern expedition
    assert detect_era("Quantum Anomaly in Modern Physics Lab") == "default"
    default_wardrobe = char.wardrobe_for_era("default")
    assert "safari utility jacket" in default_wardrobe.lower()


def test_character_sheet_spec_multi_view_prompts():
    """Verify 20-sheet manifest generation and macro artifact prompt."""
    char = get_active_character()
    spec = CharacterSheetSpec(char, aspect_ratio="16:9")

    frontal = spec.frontal_portrait_prompt("egyptian")
    assert "CHARACTER REFERENCE SHEET [FRONTAL CLOSE-UP]" in frontal
    assert "16:9" in frontal
    assert "temporal chronometer" in frontal.lower()

    macro = spec.artifact_macro_prompt()
    assert "[TEMPORAL ARTIFACT CLOSE-UP]" in macro
    assert "gyroscopic" in macro.lower()

    manifest = spec.to_manifest()
    assert "sheets" in manifest
    assert "frontal" in manifest["sheets"]
    assert "temporal_artifact" in manifest["sheets"]
    assert "camouflage_egyptian" in manifest["sheets"]


def test_screenplay_prompt_compilation_explorer_photorealism():
    """Verify explorer / longform mode generates photorealistic 16:9 prompts without mannequin/Blender tokens."""
    char_shot = Shot(
        block=1,
        beat_index=1,
        t_start=0.0,
        t_end=4.0,
        subject_id="nova_host",
        subject_description="Nova standing at the entrance of Hawara labyrinth",
        start_image_prompt="Nova looking at ancient limestone gateway",
        end_image_prompt="Nova pointing camera toward dark corridor",
        motion_prompt="Nova takes one steady step forward toward the stone archway",
        target_quadrant="center",
        dominant_event="Nova approaches the entrance",
        proof_on_screen="ancient limestone archway inscription",
        entry_state="standing outside gateway",
        exit_state="entering archway threshold",
        scale="medium",
        journey_phase="establish",
        transition_kind="same_subject",
        visual_domain="archaeology",
        continuity_anchor="Nova",
        detail_target="weathered limestone relief carvings",
        location_id="hawara_entrance",
    )

    prompt = compile_keyframe_prompt(char_shot, "start", mode=EXPLORER)

    # Explorer longform mode MUST be photorealistic 16:9 National Geographic / BBC Earth style
    assert "Photorealistic 8k cinematic documentary frame" in prompt
    assert "National Geographic and BBC Earth 35mm film aesthetic" in prompt
    assert "16:9 widescreen composition" in prompt
    assert "Horizontal 16:9 widescreen composition" in prompt
    assert "FACE LOCK:" in prompt
    assert "temporal chronometer" in prompt.lower()

    # STRICTLY NO Zack D. Shorts mannequin, glossy 3D, or Blender Cycles tokens in Explorer mode
    assert "Glossy Stylized 3D Mannequin" not in prompt
    assert "glossy stylized 3d" not in prompt.lower()
    assert "Blender Cycles" not in prompt
    assert "Octane Render" not in prompt
    assert "Vertical 9:16" not in prompt


def test_screenplay_motion_prompt_compilation_explorer():
    """Verify motion prompt compilation in explorer mode produces 16:9 cinematic motion instructions."""
    shot = Shot(
        block=2,
        beat_index=2,
        t_start=4.0,
        t_end=8.0,
        subject_id="subterranean_corridor",
        subject_description="dimly lit damp limestone subterranean corridor",
        start_image_prompt="endless vaulted limestone corridor",
        end_image_prompt="corridor opening into grand flooded chamber",
        motion_prompt="camera moves forward through the ancient vaulted corridor",
        target_quadrant="center",
        dominant_event="corridor opens into flooded chamber",
        proof_on_screen="submerged limestone columns",
        entry_state="narrow corridor",
        exit_state="chamber vista",
        scale="wide",
        journey_phase="explore",
        transition_kind="same_subject",
        visual_domain="archaeology",
        continuity_anchor="vaulted limestone walls",
        detail_target="submerged column bases",
        location_id="hawara_subterranean",
    )

    motion = optimize_for_flow(shot, mode=EXPLORER)
    video_prompt = motion["video_prompt"]

    assert "16:9 widescreen cinematic documentary scene" in video_prompt
    assert "National Geographic / BBC Earth documentary cinematography" in video_prompt
    assert "Reserve lower-third caption space" in video_prompt
    assert "Zack D. Films 3D documentary animation style" not in video_prompt
    assert "glossy stylized 3d" not in video_prompt.lower()
    assert "Vertical 9:16" not in video_prompt
    assert "chemical formula symbols" not in video_prompt.lower()
    assert "5600K warm golden directional key" not in video_prompt
    assert "atmospheric dust motes" not in video_prompt
    keyframe_prompt = compile_keyframe_prompt(shot, "start", mode=EXPLORER).lower()
    assert "chemical formula symbols" not in keyframe_prompt
    assert "no modern visitors or archaeologists" in keyframe_prompt


def test_flow_prompt_is_not_truncated_at_vertex_limit():
    source = "A" * 950 + " authored camera tracks beside the ship under cold moonlight."
    compiled = sanitize_flow_prompt(source)
    assert len(compiled) > 900
    assert compiled.endswith("authored camera tracks beside the ship under cold moonlight.")


def test_world_war_one_truth_sheet_is_period_specific():
    sheet = get_historical_truth_sheet("1915 The Battle of Gallipoli")
    corpus = " ".join(sheet.architecture_and_materials + sheet.verified_facts + sheet.prohibited_anachronisms).casefold()
    assert sheet.era == "world_war_i"
    assert "1915" in sheet.time_period
    assert "antiquity" not in corpus
    assert "ashlar" not in corpus
    assert "26 mines" in corpus
    assert "nusret" in corpus


def test_world_war_one_screenplay_keeps_authored_proof():
    script = generate_dynamic_screenplay("1915 The Battle of Gallipoli", target_blocks=15)
    assert "chronometer" in script.shots[0].proof_on_screen.lower()
    assert "allied battleships" in script.shots[0].proof_on_screen.lower()
    assert "nusret" in script.shots[1].proof_on_screen.lower()


def test_canonicalize_model_brief_allows_realism_in_explorer():
    """Verify that _canonicalize_model_brief does not strip photorealism in explorer mode."""
    raw = "A photorealistic portrait of an explorer inspecting a realistic ancient tablet"
    # In anatomical/shorts mode, photorealistic is rewritten to glossy stylized 3D
    shorts_text = _canonicalize_model_brief(raw, mode=ANATOMICAL)
    assert "glossy stylized 3D" in shorts_text
    assert "photorealistic" not in shorts_text

    # In explorer mode, realism language is explicitly preserved
    explorer_text = _canonicalize_model_brief(raw, mode=EXPLORER)
    assert "photorealistic" in explorer_text
    assert "realistic" in explorer_text


def test_longform_engine_system_prompt_explorer():
    """Verify LongformEngine system prompt includes time-traveler Defne standard requirements."""
    engine = LongformEngine(MockLLM(), lang="en", mode=EXPLORER)
    sys_prompt = engine.system_prompt()

    assert "16:9 widescreen long-form investigative explorer documentary" in sys_prompt
    assert "Nova" in sys_prompt
    assert "chronological time-traveler" in sys_prompt
    assert "temporal chronometer" in sys_prompt
    assert "National Geographic / BBC Earth 35mm photorealism" in sys_prompt
    assert "28 beats total" in sys_prompt


def test_render_ken_burns_block_execution():
    """Verify that editor.render_ken_burns_block renders a valid 16:9 MP4 video."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create a test 1920x1080 canvas image via FFmpeg lavfi
        img_path = tmp_path / "test_plate.png"
        out_mp4 = tmp_path / "test_block.mp4"

        cmd_gen = [
            config.resolve_ffmpeg(), "-y",
            "-f", "lavfi", "-i", "color=c=darkblue:s=1920x1080",
            "-vframes", "1", str(img_path)
        ]
        import subprocess
        subprocess.run(cmd_gen, check=True, capture_output=True)
        assert img_path.exists()

        # Render 2.5D Ken Burns Pan/Zoom block for 1.0 second
        res = editor.render_ken_burns_block(img_path, out_mp4, duration=1.0, motion_type="zoom_in", width=1920, height=1080)
        assert res.exists()
        assert res.stat().st_size > 0

        info = editor.probe(res)
        assert info.has_video
        assert info.width == 1920
        assert info.height == 1080
        assert info.duration is not None and info.duration >= 0.9


def test_deepgram_pacing_in_longform():
    """Verify Deepgram provider adapts to 1.0x natural pacing when in longform mode."""
    from providers.voice.deepgram_aura import DeepgramAuraProvider

    # When LONGFORM_MODE=true, default speed should be 1.0 (natural pacing)
    os.environ["LONGFORM_MODE"] = "true"
    os.environ["DEEPGRAM_TTS_SPEED"] = "1.12"  # standard shorts default in .env
    provider = DeepgramAuraProvider(
        api_key="test_key",
        base_url="https://api.deepgram.com/v1",
        voice_model="aura-2-hermes-en",
        transcribe_model="nova-3",
    )
    assert provider.tts_speed == 1.0

    # Reset
    os.environ["LONGFORM_MODE"] = "false"


def test_detect_mode_explorer_and_longform():
    """Verify mode detection routes longform and explorer signals correctly."""
    from services.mode_profile import detect_mode

    # Explorer keywords
    assert detect_mode("The Lost Labyrinth of Hawara").name == "explorer"
    assert detect_mode("Ancient subterranean chambers of Göbeklitepe").name == "explorer"

    # Environment flags
    os.environ["LONGFORM_MODE"] = "true"
    assert detect_mode("Any generic topic").name == "explorer"
    os.environ["LONGFORM_MODE"] = "false"

    os.environ["PRODUCTION_FORMAT"] = "longform"
    assert detect_mode("Another generic topic").name == "explorer"
    os.environ["PRODUCTION_FORMAT"] = "short"


def test_longform_compiler_dry_run_execution():
    """Verify LongformCompiler chunks multi-block video and compiles in dry-run mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ffmpeg = config.resolve_ffmpeg()

        # Create 3 short block fixtures
        block_paths = []
        for i in range(3):
            p = tmp_path / f"block{i:02d}.mp4"
            cmd = [
                ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=24",
                "-t", "4.0", "-pix_fmt", "yuv420p", str(p)
            ]
            import subprocess
            subprocess.run(cmd, check=True, capture_output=True)
            block_paths.append(p)

        vo_path = tmp_path / "vo.wav"
        subprocess.run([
            ffmpeg, "-y", "-f", "lavfi", "-i", "sine=f=220:r=44100",
            "-t", "12.0", str(vo_path)
        ], check=True, capture_output=True)

        out_path = tmp_path / "final_longform.mp4"
        compiler = editor.LongformCompiler(chunk_size=2)
        args, graph = compiler.compile(
            block_paths, vo_path, out_path, [],
            dry_run=True, target_len=12.0
        )
        assert args is not None
        assert graph is not None
        assert "vout" in graph


def test_deepgram_female_nova_and_male_witness_voice_routing():
    """Verify Longform Deepgram uses female voice (aura-2-thalia-en) for Nova and male voice (aura-2-hermes-en) for Historical Witnesses."""
    from providers.voice.deepgram_aura import DeepgramAuraProvider

    os.environ["LONGFORM_MODE"] = "true"
    try:
        provider = DeepgramAuraProvider(
            api_key="test_key",
            base_url="https://api.deepgram.com/v1",
            voice_model="",
            transcribe_model="nova-3",
        )
        assert provider.voice_model in {"aura-2-hera-en", "aura-2-thalia-en"}
        assert provider.witness_voice_model == "aura-2-hermes-en"

        nova_beat = Beat(index=1, text="I just arrived at Hawara.", role="host_nova")
        witness_beat = Beat(index=8, text="We carved three thousand chambers.", role="witness:Chief Royal Architect Neferhotep (1840 BC)")
        assert provider._voice_for_beat(nova_beat) in {"aura-2-hera-en", "aura-2-thalia-en"}
        assert provider._voice_for_beat(witness_beat) == "aura-2-hermes-en"
    finally:
        os.environ["LONGFORM_MODE"] = "false"


def test_explorer_28_beat_hybrid_nova_and_witness_storyboard():
    """Verify build_explorer_script produces 28 distinct beats/shots with era camouflage, witness interviews, and people-free B-roll."""
    from services.explorer_engine import build_explorer_script
    import pipeline

    os.environ["LONGFORM_MODE"] = "true"
    try:
        tl = pipeline.provider_timeline(blocks=28)
        script = build_explorer_script("The Lost Labyrinth of Hawara", tl)
        assert len(script.beats) == 28
        assert len(script.shots) == 28

        # Must contain both Nova host beats and Historical Witness beats
        witness_beats = [b for b in script.beats if b.role.startswith("witness:")]
        nova_beats = [b for b in script.beats if b.role in {"host_nova", "host_question"}]
        assert len(witness_beats) == 2
        assert len(nova_beats) == 26
        assert "Neferhotep" in witness_beats[0].role
        assert "Herodotus" in witness_beats[1].role

        # Nova A-Roll shots (1, 15, 28) must use Egyptian kalasiris camouflage, NEVER safari jacket
        for idx in (0, 14, 27):
            s = script.shots[idx]
            assert "host_nova" in s.subject_id
            assert "kalasiris" in s.start_image_prompt.lower()
            assert "safari utility jacket" not in s.start_image_prompt.lower()
            assert "headroom" in s.start_image_prompt.lower()

        # Witness shots (8, 20) must be Historical Eyewitness interviews, distinct from Nova
        for idx in (7, 19):
            s = script.shots[idx]
            assert "witness" in s.subject_id
            assert "[HISTORICAL EYEWITNESS INTERVIEW" in s.start_image_prompt
            assert "NO modern safari hats" in s.start_image_prompt

        # B-Roll shots must forbid people and never use 'host presents tangible physical evidence on screen'
        broll_shots = [s for s in script.shots if s.subject_id.startswith("broll_")]
        assert len(broll_shots) == 23
        for s in broll_shots:
            assert "ABSOLUTELY NO people" in s.start_image_prompt
            assert "host presents tangible physical evidence" not in s.proof_on_screen

        # 1:1 Keyframe-to-Block alignment in Longform (_keyframe_jobs)
        jobs = pipeline._keyframe_jobs(script, Path("/tmp/test_run"), mode=EXPLORER)
        assert len(jobs) == 29
        # kf15 (index 14 in jobs) must come from shot 15 (Nova midpoint reaction), NOT shot 14!
        kf15_key, kf15_prompt, *_ = jobs[14]
        assert kf15_key == "kf15"
        assert "[SOLO TIME-TRAVELER HOST A-ROLL]" in kf15_prompt
        # kf08 (index 7 in jobs) must come from shot 8 (Historical Witness #1)
        kf08_key, kf08_prompt, *_ = jobs[7]
        assert kf08_key == "kf08"
        assert "[HISTORICAL EYEWITNESS INTERVIEW" in kf08_prompt
    finally:
        os.environ["LONGFORM_MODE"] = "false"


def test_longform_captions_distinguish_nova_and_witness_and_include_era_stamp():
    """Verify Longform ASS subtitles include EraStamp, BrandWatermark, and visually distinct NovaSub vs WitnessSub styles."""
    import captions
    from services.script_engine import annotate_words

    beats = [
        Beat(index=1, text="I arrived at Hawara.", role="host_nova", emphasis=["Hawara"]),
        Beat(index=2, text="We built underground vaults.", role="witness:Architect Neferhotep (1840 BC)", emphasis=["underground"]),
    ]
    raw_words = [
        {"text": "I", "start": 0.1, "end": 0.3},
        {"text": "arrived", "start": 0.3, "end": 0.7},
        {"text": "at", "start": 0.7, "end": 0.9},
        {"text": "Hawara.", "source": "Hawara.", "start": 0.9, "end": 1.5},
        {"text": "We", "start": 1.6, "end": 1.8},
        {"text": "built", "start": 1.8, "end": 2.2},
        {"text": "underground", "start": 2.2, "end": 2.8},
        {"text": "vaults.", "source": "vaults.", "start": 2.8, "end": 3.4},
    ]
    annotated = annotate_words(beats, raw_words)
    assert annotated[0]["speaker"] == "nova"
    assert annotated[4]["speaker"] == "witness"
    assert "Neferhotep" in annotated[4]["speaker_label"]

    ass_text = captions.build_ass(
        annotated,
        total_duration=10.0,
        lang="en",
        topic="The Lost Labyrinth of Hawara",
        is_longform=True,
    )
    assert "Style: NovaSub," in ass_text
    assert "Style: WitnessSub," in ass_text
    assert "Style: WitnessBadge," in ass_text
    assert "Style: EraStamp," in ass_text
    assert "Style: BrandWatermark," in ass_text
    assert "HAWARA, EGYPT — 1840 BC" in ass_text
    assert "TIME TRAVELER NOVA" in ass_text
    assert "[NOVA]:" in ass_text
    assert "[TANIK / WITNESS — ARCHITECT NEFERHOTEP]:" in ass_text
    assert "HISTORICAL EYEWITNESS: ARCHITECT NEFERHOTEP (1840 BC)" in ass_text


def test_longform_gallipoli_era_stamp_uses_world_war_i_not_antiquity():
    import captions

    assert captions._resolve_era_stamp("1915 The Battle of Gallipoli") == "DARDANELLES, OTTOMAN EMPIRE — 1915"


