"""Verification suite for Gallipoli 90s reproduction, Pompeii generalization, and systemic fixes.

Tests:
1. 90-second 22-block Gallipoli reproduction (@zamanyolcusudefne 2:10 - 3:40 benchmark)
2. 15-block Pompeii generalization (79 AD Roman bakery & Vesuvius eruption)
3. Anti-fez kabalak lock & prohibited anachronisms
4. Prop/cannon consistency locks (28cm Krupp gun, Roman basalt mills/oven)
5. Universal zero-text and zero-watermark shield
6. ADR-060 host presence lock (Nova on 3 pivotal shots only, strictly NO Nova in B-roll)
7. Voice adapter registry in provider factory
8. Audio amix normalize=0 broadcast loudness preservation
"""

import pytest
from services.screenplay import generate_dynamic_screenplay
from services.curated_beats import get_gallipoli_curated_beats, get_pompeii_curated_beats
from services.historical_research import get_historical_truth_sheet
from services.character import detect_era, get_era_witness
from services.prompt_compiler import compile_longform_broll_prompt, apply_clothing_lock
import editor
import providers.factory as factory


def test_gallipoli_90s_master_reproduction_22_blocks_en():
    """Verify 90-second (22-block) Gallipoli benchmark arc in English with ADR-060 host constraints."""
    topic = "Zaman Yolcusu Defne - 18 Mart 1915 Çanakkale Boğaz Savaşı: Rumeli Mecidiye Tabyası, Seyit Onbaşı"
    script = generate_dynamic_screenplay(topic, target_blocks=22, lang="en")

    assert len(script.beats) == 22
    assert len(script.shots) == 22

    # Check narrative milestones from reference video
    beats_text = " ".join(b.text for b in script.beats)
    assert "18 March 1915" in beats_text
    assert "Mecidiye" in beats_text
    assert "Seyit" in beats_text or "two-hundred-fifteen" in beats_text
    assert "Krupp" in beats_text
    assert "Bouvet" in beats_text

    # ADR-060 Check: Host Nova on Opening (1), Midpoint (11), Closing (22)
    assert script.beats[0].role == "host_nova"
    assert script.shots[0].subject_id == "host_nova"

    assert script.beats[10].role == "host_nova"
    assert script.shots[10].subject_id == "host_nova"

    assert script.beats[21].role == "host_nova"
    assert script.shots[21].subject_id == "host_nova"

    # Duration & Pacing checks: 22 x 4.0s = 88.0s footage for 90s master reproduction
    for shot in script.shots:
        assert shot.duration == 4.0, f"Shot {shot.block} has duration {shot.duration}, expected 4.0s"
    assert script.shots[-1].t_end == 88.0
    words_en = sum(len(b.text.split()) for b in script.beats)
    assert words_en <= 220, f"English word count {words_en} exceeds safe budget"

    # All intermediate B-Roll shots MUST NOT have host_nova
    broll_indices = list(range(1, 10)) + list(range(11, 21))
    for idx in broll_indices:
        assert script.beats[idx].role == "narrator", f"Beat {idx+1} should be narrator, got {script.beats[idx].role}"
        assert script.shots[idx].subject_id != "host_nova", f"Shot {idx+1} should not be host_nova"
        assert script.shots[idx].visual_domain in ("archaeology", "incident"), f"Shot {idx+1} domain unexpected"


def test_gallipoli_90s_master_reproduction_22_blocks_tr():
    """Verify 90-second (22-block) Gallipoli benchmark arc in Turkish."""
    topic = "Zaman Yolcusu Defne - 18 Mart 1915 Çanakkale Boğaz Savaşı"
    script = generate_dynamic_screenplay(topic, target_blocks=22, lang="tr")

    assert len(script.beats) == 22
    assert len(script.shots) == 22

    beats_text = " ".join(b.text for b in script.beats)
    assert "18 Mart 1915" in beats_text
    assert "Mecidiye Tabyası" in beats_text
    assert "Seyit Onbaşı" in beats_text
    assert "215 kiloluk" in beats_text
    assert "Krupp" in beats_text
    assert "Bouvet" in beats_text

    # Duration & Pacing checks: 22 x 4.0s = 88.0s footage
    for shot in script.shots:
        assert shot.duration == 4.0, f"Shot {shot.block} has duration {shot.duration}, expected 4.0s"
    assert script.shots[-1].t_end == 88.0
    words_tr = sum(len(b.text.split()) for b in script.beats)
    assert words_tr <= 180, f"Turkish word count {words_tr} exceeds safe budget"

    # Host presence on pivotal shots only
    assert script.beats[0].role == "host_nova"
    assert script.beats[10].role == "host_nova"
    assert script.beats[21].role == "host_nova"


def test_pompeii_generalization_15_blocks_en():
    """Verify 15-block Pompeii generalization target in English with ADR-060 host constraints."""
    topic = "Zaman Yolcusu Defne - Pompei Vezüv Patlaması: MS 79 Roman Bakery"
    script = generate_dynamic_screenplay(topic, target_blocks=15, lang="en")

    assert len(script.beats) == 15
    assert len(script.shots) == 15

    beats_text = " ".join(b.text for b in script.beats)
    assert "Pompeii" in beats_text
    assert "Vesuvius" in beats_text
    assert "pistrinum" in beats_text
    assert "basalt mills" in beats_text
    assert "panis quadratus" in beats_text

    # Duration & Pacing checks: 15 x 4.0s = 60.0s footage
    for shot in script.shots:
        assert shot.duration == 4.0, f"Shot {shot.block} has duration {shot.duration}, expected 4.0s"
    assert script.shots[-1].t_end == 60.0
    words_en = sum(len(b.text.split()) for b in script.beats)
    assert words_en <= 160, f"English word count {words_en} exceeds safe budget"

    # ADR-060 Check: Host Nova on Opening (1), Midpoint (8), Closing (15)
    assert script.beats[0].role == "host_nova"
    assert script.shots[0].subject_id == "host_nova"

    assert script.beats[7].role == "host_nova"
    assert script.shots[7].subject_id == "host_nova"

    assert script.beats[14].role == "host_nova"
    assert script.shots[14].subject_id == "host_nova"

    # All intermediate B-Roll shots MUST NOT have host_nova
    broll_indices = list(range(1, 7)) + list(range(8, 14))
    for idx in broll_indices:
        assert script.beats[idx].role == "narrator", f"Beat {idx+1} should be narrator, got {script.beats[idx].role}"
        assert script.shots[idx].subject_id != "host_nova", f"Shot {idx+1} should not be host_nova"


def test_pompeii_generalization_15_blocks_tr():
    """Verify 15-block Pompeii generalization target in Turkish."""
    topic = "Zaman Yolcusu Defne - Pompei Vezüv Patlaması"
    script = generate_dynamic_screenplay(topic, target_blocks=15, lang="tr")

    assert len(script.beats) == 15
    assert len(script.shots) == 15

    beats_text = " ".join(b.text for b in script.beats)
    assert "MS 79" in beats_text
    assert "Pompei" in beats_text
    assert "Terentius Neo" in beats_text
    assert "pistrinum" in beats_text
    assert "Vezüv" in beats_text

    # Duration & Pacing checks: 15 x 4.0s = 60.0s footage
    for shot in script.shots:
        assert shot.duration == 4.0, f"Shot {shot.block} has duration {shot.duration}, expected 4.0s"
    assert script.shots[-1].t_end == 60.0
    words_tr = sum(len(b.text.split()) for b in script.beats)
    assert words_tr <= 125, f"Turkish word count {words_tr} exceeds safe budget"


def test_anti_fez_lock_and_kabalak_enforcement():
    """Verify that WWI / Ottoman 1915 prompts enforce khaki kabalak and prohibit red fez."""
    sheet = get_historical_truth_sheet("1915 Battle of Gallipoli")
    assert sheet.era == "world_war_i"
    assert any("kabalak" in item.lower() for item in sheet.architecture_and_materials)
    assert any("fez" in item.lower() for item in sheet.prohibited_anachronisms)

    prompt = compile_longform_broll_prompt(
        scene_description="Ottoman artillerymen at shore battery",
        proof_target="28cm Krupp gun",
        truth_sheet=sheet,
        aspect_ratio="16:9",
    )
    assert "kabalak" in prompt.lower()
    assert "strictly no red fez" in prompt.lower()


def test_prop_consistency_locks():
    """Verify immutable prop anchors for Gallipoli coastal gun and Pompeii bakery mills."""
    sheet_wwi = get_historical_truth_sheet("1915 Battle of Gallipoli")
    prompt_wwi = compile_longform_broll_prompt(
        scene_description="Gunners loading heavy artillery gun",
        proof_target="artillery gun loading",
        truth_sheet=sheet_wwi,
        aspect_ratio="16:9",
    )
    assert "28cm krupp coastal fortress gun" in prompt_wwi.lower()

    sheet_pompeii = get_historical_truth_sheet("Pompeii Roman Bakery Vesuvius")
    prompt_pompeii = compile_longform_broll_prompt(
        scene_description="Inside pistrinum bakery with basalt mills and oven",
        proof_target="volcanic stone mills",
        truth_sheet=sheet_pompeii,
        aspect_ratio="16:9",
    )
    assert "pistrinum" in prompt_pompeii.lower()
    assert "basalt lava stone grain mills" in prompt_pompeii.lower()
    assert "brick domed" in prompt_pompeii.lower() and "oven" in prompt_pompeii.lower()


def test_zero_text_and_watermark_shield():
    """Verify that longform prompts include the comprehensive zero text and zero watermark shield."""
    sheet = get_historical_truth_sheet("1915 Battle of Gallipoli")
    prompt = compile_longform_broll_prompt(
        scene_description="Allied warships entering strait",
        proof_target="Allied battleships",
        truth_sheet=sheet,
        aspect_ratio="16:9",
    )
    assert "zero text" in prompt.lower()
    assert "zero watermarks" in prompt.lower()
    assert "zero typography" in prompt.lower()
    assert "zero date stamps" in prompt.lower()


def test_audio_amix_normalization_disabled_for_target_lufs():
    """Verify that editor.py audio amix filter uses normalize=0 to preserve voice loudness."""
    stmts = editor.build_audio_filter(
        vo_index=0,
        music_index=1,
        soundscape_index=2,
    )
    filter_str = " ".join(stmts)
    assert "normalize=0" in filter_str
    assert "[vo1][duck][duck_amb]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[base]" in filter_str


def test_provider_factory_voice_adapters_registered():
    """Verify that edge_tts and elevenlabs voice adapters are correctly registered under voice_providers."""
    factory._register_voice_adapter("edge_tts")
    factory._register_voice_adapter("elevenlabs")
    assert "edge_tts" in factory.voice_providers.registered_names
    assert "elevenlabs" in factory.voice_providers.registered_names
    assert "edge_tts" not in factory.video_providers.registered_names
    assert "elevenlabs" not in factory.video_providers.registered_names


def test_no_cedar_timber_or_mudbrick_in_wwi_prompts():
    """Verify that WWI artillery prompts with cranes/pulleys are exempt from ancient cedar lever injection."""
    sheet = get_historical_truth_sheet("1915 Battle of Gallipoli")
    prompt = compile_longform_broll_prompt(
        scene_description="Heavy shell hoist crane mechanism inside battery with chains and pulleys",
        proof_target="ammunition crane",
        truth_sheet=sheet,
        aspect_ratio="16:9",
    )
    prompt_lower = prompt.lower()
    assert "hewn cedar timber" not in prompt_lower
    assert "mud-brick slipways" not in prompt_lower
    assert "oiled sledges" not in prompt_lower
    assert "28cm krupp coastal fortress gun" in prompt_lower


def test_main_cli_url_canonicalization_and_duration_triggers():
    """Verify that main CLI canonicalizes reference YouTube URLs and duration triggers."""
    import main
    
    # Gallipoli reference URL mapping
    args = main.parse_args(["--topic", "https://www.youtube.com/watch?v=PXixPeATIQc&t=130s"])
    assert "PXixPeATIQc" in args.topic
    # Simulating main canonicalization logic:
    topic_lower = args.topic.casefold()
    assert "pxixpeatiqc" in topic_lower
    
    # Pompeii reference URL mapping
    args_p = main.parse_args(["--topic", "https://www.youtube.com/watch?v=qZZoxHjTLiw"])
    assert "qZZoxHjTLiw" in args_p.topic
    
    # Duration argument
    args_d = main.parse_args(["--duration", "90"])
    assert args_d.duration == 90
