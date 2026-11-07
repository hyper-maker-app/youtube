"""Engine services package."""

from services.boundary_inspector import (
    BoundaryQAReport,
    TRANSITION_SCORE_THRESHOLD,
    inspect_transition_boundary,
    write_qa_report,
)
from services.sfx_categorizer import (
    SfxCategoryMatch,
    auto_categorize_scene_sfx,
    extract_sfx_category,
    get_supported_sfx_categories,
)
from services.map_overlay_generator import (
    generate_data_broll,
    generate_pressure_grid_video,
    generate_temperature_curve_video,
    generate_volcano_map_video,
    test_map_overlay_generator,
)
from services.audio_bed import (
    duck_audio_bed,
    generate_audio_bed,
    generate_music_bed,
    inject_audio_trigger_cues,
    normalize_loudness,
    synthesize_audio_trigger_cue,
    test_audio_bed,
)
from services.remotion_bridge import (
    render_remotion_broll,
    resolve_template_name,
)
from services.flow_accounts import (
    FlowAccount,
    FlowAccountManager,
    get_flow_account_manager,
    send_windows_notification,
)

__all__ = [
    "render_remotion_broll",
    "resolve_template_name",
    "FlowAccount",
    "FlowAccountManager",
    "get_flow_account_manager",
    "send_windows_notification",
    "BoundaryQAReport",
    "TRANSITION_SCORE_THRESHOLD",
    "inspect_transition_boundary",
    "write_qa_report",
    "SfxCategoryMatch",
    "auto_categorize_scene_sfx",
    "extract_sfx_category",
    "get_supported_sfx_categories",
    "generate_data_broll",
    "generate_pressure_grid_video",
    "generate_temperature_curve_video",
    "generate_volcano_map_video",
    "test_map_overlay_generator",
    "duck_audio_bed",
    "generate_audio_bed",
    "generate_music_bed",
    "inject_audio_trigger_cues",
    "normalize_loudness",
    "synthesize_audio_trigger_cue",
    "test_audio_bed",
]
