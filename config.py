"""Central configuration: style constants, model IDs, FX coefficients, ffmpeg resolution."""

from __future__ import annotations

import os
import shutil
import importlib.util
import subprocess
import zlib
from pathlib import Path

from dotenv import load_dotenv
from providers.base import ConfigurationError

ROOT = Path(__file__).resolve().parent
OUT_ROOT = ROOT / "out"

# override=True: this project pins its own model/endpoint in .env, and the surrounding
# Claude Code process injects its own ANTHROPIC_* (e.g. ANTHROPIC_MODEL=claude-sonnet-5)
# into the environment, which would otherwise silently win over .env.
load_dotenv(ROOT / ".env", override=True)


# --------------------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------------------

def env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def require_env(*names: str, provider: str) -> tuple[str, ...]:
    """Read explicit provider values or fail at the selected provider boundary.

    Credentials, tokens, and gateway endpoints intentionally have no Python fallback.
    Concrete adapters call this only after their provider has been selected.
    """
    values = tuple(env(name) for name in names)
    missing = [name for name, value in zip(names, values) if value is None]
    if missing:
        raise ConfigurationError(
            f"{provider} provider requires: {', '.join(missing)}. Configure them in .env."
        )
    return tuple(value for value in values if value is not None)


def env_bool(name: str, default: bool = False) -> bool:
    """Parse an opt-in environment switch without accepting ambiguous values."""
    value = env(name)
    if value is None:
        return default
    return value.casefold() in {"1", "true", "yes", "on"}


LLM_PROVIDER = env("LLM_PROVIDER")
VIDEO_PROVIDER = env("VIDEO_PROVIDER")
IMAGE_PROVIDER = env("IMAGE_PROVIDER")
VOICE_PROVIDER = env("VOICE_PROVIDER")
PRODUCTION_FORMAT = (env("PRODUCTION_FORMAT") or "zackd").casefold()
IS_EXPLORER_FORMAT = PRODUCTION_FORMAT == "explorer"
LONGFORM_MODE = env_bool("LONGFORM_MODE", True if IS_EXPLORER_FORMAT else False)
LONGFORM_HYBRID_MODE = env_bool("LONGFORM_HYBRID_MODE", False)
EXPLORER_LIPSYNC_PROVIDER = env("EXPLORER_LIPSYNC_PROVIDER") or "gradio_client"
EXPLORER_LIPSYNC_ENABLED = env_bool("EXPLORER_LIPSYNC_ENABLED", True if (IS_EXPLORER_FORMAT or LONGFORM_MODE) else False)
GEMINI_API_KEY = env("GEMINI_API_KEY")
FLOW_AGENT_SESSION_TOKEN = env("FLOW_AGENT_SESSION_TOKEN")
FLOW_AGENT_CLI_PATH = env("FLOW_AGENT_CLI_PATH")

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
OPENAI_API_KEY = env("OPENAI_API_KEY")
FAL_KEY = env("FAL_KEY")
VERTEX_PROJECT = env("GOOGLE_CLOUD_PROJECT") or env("VERTEX_PROJECT")
VERTEX_LOCATION = env("VERTEX_LOCATION") or env("GOOGLE_CLOUD_LOCATION")
VERTEX_OPERATION_TIMEOUT_SECONDS = int(env("VERTEX_OPERATION_TIMEOUT_SECONDS") or "1200")
VERTEX_OPERATION_POLL_SECONDS = float(env("VERTEX_OPERATION_POLL_SECONDS") or "10")
# Calibration is deliberately process/config scoped: it is for development runs where
# quality exploration is worth additional provider spend.  Normal production retains
# the historical one-request, fail-closed Vertex policy.
CALIBRATION_MODE = env_bool("CALIBRATION_MODE", False)
CALIBRATION_MAX_ATTEMPTS = max(1, int(env("CALIBRATION_MAX_ATTEMPTS") or "3"))
# Nano Banana Pro is the sole image/keyframe model. Veo remains a separate video
# provider and is never selected for still-image generation.
NANO_BANANA_PRO_MODEL = env("NANO_BANANA_PRO_MODEL") or "gemini-3-pro-image"
VERTEX_HERO_VIDEO_MODEL = env("VERTEX_HERO_VIDEO_MODEL") or "vertex_veo_fast"
# Text/planning is deliberately separate from the Image/Veo model choices. The supplied
# Vertex console reference documents Gemini 3.8 Flash as a GA text model with Vertex ADC.
VERTEX_TEXT_MODEL = env("VERTEX_TEXT_MODEL") or "gemini-3.8-flash"
VERTEX_TEXT_LOCATION = env("VERTEX_TEXT_LOCATION") or "global"
VERTEX_TEXT_MAX_OUTPUT_TOKENS = max(1024, int(env("VERTEX_TEXT_MAX_OUTPUT_TOKENS") or "16000"))
# A text plan must either arrive promptly or fail into the configured Anthropic
# recovery path.  Leaving the SDK default unbounded can stall a whole production
# before it has even persisted script.json or submitted any media request.
VERTEX_TEXT_TIMEOUT_SECONDS = max(10, int(env("VERTEX_TEXT_TIMEOUT_SECONDS") or "90"))
# New Lighthouse V2 runs inspect their already-generated keyframes with Gemini Vision
# before any Veo clip is submitted.  Keep this independent from Anthropic review settings
# and freeze the selected values into vertex_plan for deterministic resumes.
VERTEX_KEYFRAME_PREFLIGHT_MODEL = env("VERTEX_KEYFRAME_PREFLIGHT_MODEL") or VERTEX_TEXT_MODEL
VERTEX_KEYFRAME_PREFLIGHT_LOCATION = env("VERTEX_KEYFRAME_PREFLIGHT_LOCATION") or VERTEX_TEXT_LOCATION
VERTEX_KEYFRAME_PREFLIGHT_MAX_OUTPUT_TOKENS = max(
    512, int(env("VERTEX_KEYFRAME_PREFLIGHT_MAX_OUTPUT_TOKENS") or "8192")
)
# A 429 RESOURCE_EXHAUSTED response from Gemini Vision is a transient capacity result,
# not a visual verdict.  Retry only that narrow case before the fail-closed preflight is
# persisted.  These limits deliberately apply to the no-video-review request only; they
# never cause keyframes or Veo clips to be regenerated.
VERTEX_KEYFRAME_PREFLIGHT_429_RETRIES = min(
    5, max(0, int(env("VERTEX_KEYFRAME_PREFLIGHT_429_RETRIES") or "3"))
)
VERTEX_KEYFRAME_PREFLIGHT_429_BACKOFF_SECONDS = min(
    60.0, max(1.0, float(env("VERTEX_KEYFRAME_PREFLIGHT_429_BACKOFF_SECONDS") or "5"))
)
# A completed V2 Lighthouse clip is reviewed with the same Vertex Gemini Vision route
# before the next Veo request.  These are frozen into vertex_plan alongside the keyframe
# preflight settings; no V2 Vertex production should fall back to Anthropic for either
# semantic decision.
VERTEX_CLIP_REVIEW_MODEL = env("VERTEX_CLIP_REVIEW_MODEL") or VERTEX_KEYFRAME_PREFLIGHT_MODEL
VERTEX_CLIP_REVIEW_LOCATION = env("VERTEX_CLIP_REVIEW_LOCATION") or VERTEX_KEYFRAME_PREFLIGHT_LOCATION
VERTEX_CLIP_REVIEW_MAX_OUTPUT_TOKENS = max(
    512, int(env("VERTEX_CLIP_REVIEW_MAX_OUTPUT_TOKENS") or "4096")
)
# The opening image is always the hero asset. A short needs at most one additional
# premium mechanism/reveal keyframe; unlimited keyword matches can quietly promote every
# scene to Pro Image without producing a more coherent video.
VERTEX_MAX_HERO_KEYFRAMES = max(1, int(env("VERTEX_MAX_HERO_KEYFRAMES") or "2"))
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
DEEPGRAM_API_KEY = env("DEEPGRAM_API_KEY")
DEEPGRAM_BASE_URL = env("DEEPGRAM_BASE_URL")
DEEPGRAM_MODEL = env("DEEPGRAM_VOICE_MODEL") or env("DEEPGRAM_MODEL")
DEEPGRAM_LONGFORM_VOICE_MODEL = env("DEEPGRAM_LONGFORM_VOICE_MODEL") or "aura-2-hera-en"
DEEPGRAM_WITNESS_VOICE_MODEL = env("DEEPGRAM_WITNESS_VOICE_MODEL") or "aura-2-hermes-en"
DEEPGRAM_TTS_SPEED = float(env("DEEPGRAM_TTS_SPEED") or ("1.0" if LONGFORM_MODE else "1.12"))
DEEPGRAM_FLUX_ROSTER = env_bool("DEEPGRAM_FLUX_ROSTER", False)
DEEPGRAM_FLUX_SPEAK_VERSION = env("DEEPGRAM_FLUX_SPEAK_VERSION") or "v2"
VOYSLITY_API_KEY = env("VOYSLITY_API_KEY")
VOYSLITY_BASE_URL = env("VOYSLITY_BASE_URL")
VOYSLITY_VOICE_ID = env("VOYSLITY_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"
VOYSLITY_MODEL_ID = env("VOYSLITY_MODEL_ID") or "eleven_multilingual_v2"

# Seslab returns synchronous JSON {audio_url} for short texts.
SESLAB_API_KEY = env("SESLAB_API_KEY")
SESLAB_BASE_URL = env("SESLAB_BASE_URL")
SESLAB_VOICE_ID = env("SESLAB_VOICE_ID") or "1Ui4bRFeTBgvTVC1eVFz"
SESLAB_VOICE_PACKAGE = env("SESLAB_VOICE_PACKAGE") or "voice-natural"

# Voice generation is independent from the visual source.  In particular, a manual Flow
# handoff still ships a real voiceover and must not silently fall back to Edge merely
# because its visual tier is free.  Daniel is the channel's canonical ElevenLabs voice;
# the local MP3 is an audit/reference sample, not a cloning input.
TTS_PROVIDERS = ("deepgram", "elevenlabs", "seslab", "voyslity", "edge", "edge_tts")
TTS_PROVIDER = (VOICE_PROVIDER or env("TTS_PROVIDER") or "").lower()
if TTS_PROVIDER == "edge_tts":
    TTS_PROVIDER = "edge"
DANIEL_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"
DANIEL_SAMPLE_PATH = ROOT / "_voice_samples" / "Daniel_onwK4e.mp3"


def commercial_tts_available() -> bool:
    """Whether the explicitly selected non-Edge narration provider is usable."""
    return {
        "deepgram": bool(DEEPGRAM_API_KEY),
        "elevenlabs": bool(ELEVENLABS_API_KEY),
        "seslab": bool(SESLAB_API_KEY),
        "voyslity": bool(VOYSLITY_API_KEY),
        "edge": False,
    }.get(TTS_PROVIDER, False)

CODEFAST_BASE_URL = env("CODEFAST_BASE_URL")
CODEFAST_API_KEY = env("CODEFAST_API_KEY")
CODEFAST_MODEL = os.environ.get("CODEFAST_MODEL", "deepseek-v4-flash")

SEEKAI_API_KEY = env("SEEKAI_API_KEY")
SEEKAI_BASE_URL = env("SEEKAI_BASE_URL")
SEEKAI_MODEL = os.environ.get("SEEKAI_MODEL", "claude-opus-4-8")

ANTHROPIC_WORKSPACE_ID = env("ANTHROPIC_WORKSPACE_ID")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
# A validation failure from Haiku is retried once with Sonnet before any paid visual or
# voice work begins.  This is deliberately separate from the transport/gateway fallback.
ANTHROPIC_QUALITY_FALLBACK_MODEL = env("ANTHROPIC_QUALITY_FALLBACK_MODEL") or "claude-sonnet-5"
# A structured five-beat / five-shot script normally completes well below this cap.  The
# old 16k ceiling made a malformed tool response needlessly expensive and increased the
# time a streaming request could remain open before Vertex preflight had any script to
# validate.  This is an output ceiling only; it does not affect media generation.
ANTHROPIC_SCRIPT_MAX_TOKENS = max(1024, int(env("ANTHROPIC_SCRIPT_MAX_TOKENS") or "8000"))
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-2024-11-20")

ANTHROPIC_BASE_URL = env("ANTHROPIC_BASE_URL")
ANTHROPIC_AUTH_TOKEN = env("ANTHROPIC_AUTH_TOKEN")
ANTHROPIC_VISION_BASE_URL = env("ANTHROPIC_VISION_BASE_URL")

# Topic categories for autonomous topic generation
TOPIC_CATEGORIES = (
    "random",
    "biology",
    "engineering",
    "aviation",
    "space",
    "physics",
    "history",
    "everyday_science",
    "folklore",
    "fiction",
)

TOPIC_MODES = ("mixed", "trend", "evergreen")
CONTENT_MODES = ("mixed", "factual", "folklore", "fiction")
CONTENT_MIX_TARGETS = {"factual": 0.60, "folklore": 0.25, "fiction": 0.15}



# --------------------------------------------------------------------------------------
# Tiers
# --------------------------------------------------------------------------------------

TIER_FREE = "free"
TIER_PAID = "paid"
TIERS = (TIER_FREE, TIER_PAID)


def paid_tier_available() -> list[str]:
    """Return credentials that are indispensable to the paid visual path.

    A paid Fal run can still use the local edge-tts voice fallback, so treating an optional
    commercial TTS key as mandatory made a valid video run incorrectly downgrade to free.
    """
    missing = []
    if not FAL_KEY:
        missing.append("FAL_KEY")
    return missing


def vertex_ai_available() -> list[str]:
    """Return missing local requirements for direct Vertex AI generation.

    ADC is deliberately used instead of a JSON service-account key.  It is created by
    ``gcloud auth application-default login`` and is never copied into this repository.
    """
    missing: list[str] = []
    if importlib.util.find_spec("google.genai") is None:
        missing.append("google-genai (run: python -m pip install google-genai)")
    try:
        import google.auth
        google.auth.default()
    except Exception:
        missing.append("Application Default Credentials (run: gcloud auth application-default login)")
    try:
        project = vertex_project_id()
    except RuntimeError as exc:
        missing.append(str(exc))
    else:
        command = gcloud_command()
        if command:
            try:
                result = subprocess.run(
                    [command, "services", "list", "--enabled", "--project", project,
                     "--filter", "config.name:aiplatform.googleapis.com", "--format=value(config.name)"],
                    check=True, capture_output=True, text=True, timeout=20,
                )
                if "aiplatform.googleapis.com" not in result.stdout:
                    missing.append("Vertex AI API is not enabled (enable aiplatform.googleapis.com)")
            except (OSError, subprocess.SubprocessError):
                missing.append("Vertex AI API access could not be verified with local gcloud")
    return missing


def gcloud_command() -> str | None:
    """Return a local gcloud executable without relying only on the parent PATH.

    Windows desktop installs commonly place Cloud SDK under LOCALAPPDATA but do not
    propagate that directory into every GUI-launched Python process.  This helper
    performs local executable discovery only; it never reads credentials or calls a
    Cloud API by itself.
    """
    names = ("gcloud.cmd", "gcloud") if os.name == "nt" else ("gcloud", "gcloud.cmd")
    for name in names:
        if found := shutil.which(name):
            return found
    if os.name == "nt":
        candidates = (
            Path(os.environ.get("LOCALAPPDATA") or "") / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd",
            Path(os.environ.get("ProgramFiles") or "") / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd",
            Path(os.environ.get("ProgramFiles(x86)") or "") / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd",
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None


def vertex_project_id() -> str:
    """Resolve the Vertex project from explicit config or the active local gcloud config."""
    if VERTEX_PROJECT:
        return VERTEX_PROJECT
    command = gcloud_command()
    if not command:
        raise RuntimeError(
            "Google Cloud project is unset and gcloud was not found. Set GOOGLE_CLOUD_PROJECT "
            "or install Google Cloud CLI / add it to PATH."
        )
    try:
        result = subprocess.run(
            [command, "config", "get-value", "project"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Could not read the active gcloud project; set GOOGLE_CLOUD_PROJECT explicitly.") from exc
    project = result.stdout.strip()
    if not project or project == "(unset)":
        raise RuntimeError("No Google Cloud project is configured; set GOOGLE_CLOUD_PROJECT or run gcloud config set project.")
    return project



def resolve_tier(requested: str | None) -> str:
    """Degrade to free rather than dying halfway through a paid run."""
    req = (requested or TIER_FREE).lower()
    if req not in TIERS:
        raise ValueError(f"Unknown tier '{req}'. Use one of: {', '.join(TIERS)}")
    if req == TIER_PAID and (missing := paid_tier_available()):
        print(f"  [tier] paid requested but {', '.join(missing)} missing -> using free tier")
        return TIER_FREE
    return req


# --------------------------------------------------------------------------------------
# FFmpeg
# --------------------------------------------------------------------------------------

def resolve_ffmpeg() -> str:
    """Prefer a PATH ffmpeg, else fall back to the binary bundled with imageio-ffmpeg."""
    override = env("FFMPEG_BINARY")
    if override and Path(override).exists():
        return override

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError(
            "No ffmpeg found on PATH and imageio-ffmpeg is not installed. "
            "Run: pip install imageio-ffmpeg"
        ) from exc

    return imageio_ffmpeg.get_ffmpeg_exe()


# --------------------------------------------------------------------------------------
# Video geometry / timing
# --------------------------------------------------------------------------------------

LONGFORM_MODE = env_bool("LONGFORM_MODE", True if IS_EXPLORER_FORMAT else False)
LONGFORM_HYBRID_MODE = env_bool("LONGFORM_HYBRID_MODE", False)

WIDTH = 1920 if LONGFORM_MODE else 1080
HEIGHT = 1080 if LONGFORM_MODE else 1920
FPS = 30

# Every provider-native motion clip is a four-second unit.  New runs begin with a
# lightweight screenplay plan, synthesize the narration, then freeze the actual
# 6..13-block plan from the measured audio duration.  The selected plan is persisted
# in script.json and is never recomputed by --resume.
BLOCK_DURATION = 4.0
MIN_BLOCKS = 6
MAX_BLOCKS = 13
TAIL_HOLD = 1.5

# Target duration and block profile for production Shorts (Sweet Spot: 45–55s, 11–13 blocks).
TARGET_MIN_DURATION = float(env("TARGET_MIN_DURATION") or "45.0")
TARGET_MAX_DURATION = float(env("TARGET_MAX_DURATION") or "52.0")
TARGET_DURATION = float(env("TARGET_DURATION") or "48.0")
DEFAULT_PRODUCTION_BLOCKS = int(env("DEFAULT_PRODUCTION_BLOCKS") or "12")



def compute_target_duration(footage_duration: float, voice_duration: float | None = None) -> float:
    """Return the final render budget, including the cloned tail.

    The tail is deliberately *inside* this budget.  The final native block may be
    trimmed before ``tpad`` so a short has one intentional 1.5-second hold rather
    than an accidental second hold after every available provider frame.
    """
    floor = float(voice_duration) + 0.4 if voice_duration is not None else float(footage_duration)
    return round(max(float(footage_duration), floor), 3)


# These values are deliberately named legacy because they are only a safe
# deserialization fallback for script.json files created before timeline persistence.
LEGACY_BLOCK_DURATION = BLOCK_DURATION
LEGACY_SHOT_DURATIONS = (4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 6.0)
LEGACY_TARGET_DURATION = sum(LEGACY_SHOT_DURATIONS)


def legacy_shot_duration(block: int) -> float:
    """Duration fallback for an old persisted shot with no explicit duration."""
    if 1 <= block <= len(LEGACY_SHOT_DURATIONS):
        return LEGACY_SHOT_DURATIONS[block - 1]
    return LEGACY_BLOCK_DURATION


def legacy_shot_window(block: int) -> tuple[float, float]:
    """Time window fallback for legacy persisted blocks only."""
    start = sum(LEGACY_SHOT_DURATIONS[:max(0, block - 1)])
    return (round(start, 3), round(start + legacy_shot_duration(block), 3))


# --------------------------------------------------------------------------------------
# Post FX coefficients (see editor.build_video_filter)
# --------------------------------------------------------------------------------------

# Base zoom: minimal 1.02 overscan is sufficient for clean framing without extreme crop.
BASE_ZOOM = 1.02
# Visual impact is opt-in through the persisted editorial plan.  Caption/word
# emphasis is deliberately not a camera instruction.
PUNCH_AMOUNT = 0.0
PUNCH_DECAY = 0.28
PUNCH_MIN_GAP = 0.60
PUNCH_MAX_COUNT = 3

# Shake is disabled by default.  Strong beats belong to the generated diegetic
# action; FFmpeg only supports the explicitly-selected subtle reframing pulse.
SHAKE_DURATION = 0.30
SHAKE_AMPLITUDE_PX = 0
SHAKE_FREQ_X = 19
SHAKE_FREQ_Y = 23

# Block-boundary transitions (see editor.build_video_filter). Each xfade consumes D
# seconds of overlap, so a block keeps half of each adjacent D as extra footage beyond
# block_dur; boundary timestamps stay pinned at (k+1)*block_dur so captions stay in sync.
XFADE_SAME_DUR = 0.28      # crossfade at same-subject boundaries (hides Flow drift)
XFADE_CHANGE_DUR = 0.14    # fadeblack snap at subject-change boundaries
BOUNDARY_PUNCH_AMT = 0.0   # legacy boundary spikes are never inferred from a cut
BOUNDARY_PUNCH_LEAD = 0.18 # half-width of the triangular punch window (seconds)

# The sole editorial post-FX impact: an explicit, short, local reframing pulse.
# It is intentionally below the old 6% crash-punch and never carries shake.
SUBTLE_IMPACT_AMOUNT = 0.015
SUBTLE_IMPACT_DURATION = 0.20
EDITORIAL_MIN_EFFECT_GAP = 0.75
EDITORIAL_MAX_IMPACTS_PER_12S = 2



def shake_margin_px(axis: str = "x") -> float:
    """Pixels of spare crop area per side that BASE_ZOOM leaves for shake/float."""
    span = WIDTH if axis == "x" else HEIGHT
    return span * (1.0 - 1.0 / BASE_ZOOM) / 2.0


MUSIC_VOLUME = 0.19
DUCK_THRESHOLD = 0.03
DUCK_RATIO = 8
DUCK_ATTACK = 5
DUCK_RELEASE = 300

LOUDNORM_I = -14
LOUDNORM_TP = -1.5
LOUDNORM_LRA = 11

X264_CRF = 18
X264_PRESET = "slow"
AAC_BITRATE = "192k"
AUDIO_RATE = 44100

# Free-tier keyframes arrive at 576x1024 and are upscaled 1.87x, so grain and a firmer
# unsharp are what stop the result reading as a soft slideshow.
FINAL_UNSHARP = "unsharp=5:5:0.5"
FINAL_GRAIN = "noise=alls=2:allf=t+u"
FINAL_EQ = "eq=contrast=1.06:saturation=1.05"
FINAL_VIGNETTE = "vignette=PI/5"

# Remote candidates are checked locally before they can become a block in the final edit.
# `freezedetect` reports near-identical consecutive frames; 0.001 is intentionally
# permissive enough to ignore normal compression shimmer while catching a visibly frozen
# provider-native generation. SSIM is deliberately not used here: first-vs-last SSIM is expected
# to be low for an intentional zoom, cross-section, or scale transition.
QUALITY_MIN_DURATION = LEGACY_BLOCK_DURATION - 0.15
QUALITY_MIN_WIDTH = 360
QUALITY_MIN_HEIGHT = 640
FREEZEDETECT_NOISE = 0.001
FREEZE_MAX_DURATION = 0.65
MAX_QUALITY_RETRIES_PER_BLOCK = 2
VISUAL_QUALITY_MIN_SCORE = 7
VISUAL_QUALITY_MAX_RETRIES_PER_BLOCK = 2
# Keyframe admission is a visual quality decision before Veo is charged.  Keep
# the retry budget small and explicit: a rejected endpoint is rerolled with its
# reviewer evidence, while accepted neighbours are never regenerated.
KEYFRAME_ADMISSION_ATTEMPTS = min(3, max(1, int(env("KEYFRAME_ADMISSION_ATTEMPTS") or "3")))
# When all normal admission attempts are exhausted for a scale_transition or
# subject_change shot, attempt one final generation with relaxed same_subject
# semantics.  Disable this to enforce strict rejection on misclassified transitions.
KEYFRAME_FALLBACK_RELABEL = str(env("KEYFRAME_FALLBACK_RELABEL") or "true").casefold() in {"1", "true", "yes"}
# When true, explicitly permits image providers without review_keyframe to bypass visual review.
ALLOW_UNREVIEWED_KEYFRAMES = str(env("ALLOW_UNREVIEWED_KEYFRAMES") or "false").casefold() in {"1", "true", "yes"}
# Maximum concurrent video block generation requests to Vertex AI Veo.
# Must strictly remain 1: Vertex AI Veo quota drops concurrent video generation requests (ADR-008).
VERTEX_VEO_MAX_CONCURRENT_BLOCKS = max(1, min(4, int(env("VERTEX_VEO_MAX_CONCURRENT_BLOCKS") or "1")))
# Visual review is deliberately limited to physical-effect shots and to live Anthropic
# production credentials.  Dry-runs, Flow handoffs and local fallback stay cost-free.
VISUAL_QUALITY_ENABLED = True
# `reverse` needs a short decoded tail to reliably select the literal final frame.  One
# second is enough at every supported frame rate while keeping memory bounded.
CHAIN_FRAME_SEEK_SECONDS = 1.0




# --------------------------------------------------------------------------------------
# Local motion engine (editor.MotionEngine)
# --------------------------------------------------------------------------------------

# The still is upscaled past the output size so zoompan crops from real pixels instead of
# inventing them, and so the handheld float has margin to move inside.
MOTION_OVERSCAN = 1.12
MOTION_SRC_WIDTH = int(WIDTH * MOTION_OVERSCAN) // 2 * 2
MOTION_SRC_HEIGHT = int(HEIGHT * MOTION_OVERSCAN) // 2 * 2

# Multipliers applied to MOTION_OVERSCAN: (zoom_at_start, zoom_at_end). 1.00 means the
# crop is exactly WIDTHxHEIGHT, i.e. pixel-for-pixel with no resample.
MOTION_ZOOM = {
    "push_in": (1.00, 1.12),
    "deep_push": (1.00, 1.17),
    "pull_out": (1.12, 1.00),
    "lateral_pan": (1.00, 1.00),
}

MOTION_DRIFT_PX = 30.0
MOTION_SRC_UNSHARP = "unsharp=3:3:0.8"

# Summed incommensurate frequencies: a single sine reads as a mechanical sweep, two that
# do not share a period read as an operator holding the camera. (amplitude_px, hz)
MOTION_FLOAT_X = ((6.0, 0.13), (3.0, 0.31))
MOTION_FLOAT_Y = ((5.0, 0.11), (3.0, 0.27))

RACK_FOCUS_SIGMA = 9.0
RACK_FOCUS_START = 0.30
RACK_FOCUS_DURATION = 2.40


def motion_float_amplitude(axis: str = "x") -> float:
    terms = MOTION_FLOAT_X if axis == "x" else MOTION_FLOAT_Y
    return sum(a for a, _ in terms)


def motion_margin_px(axis: str = "x") -> float:
    """Spare crop area per side at the widest point of the move (zoom == OVERSCAN)."""
    src = MOTION_SRC_WIDTH if axis == "x" else MOTION_SRC_HEIGHT
    return (src - src / MOTION_OVERSCAN) / 2.0


# --------------------------------------------------------------------------------------
# Longform (16:9) motion engine overrides
# --------------------------------------------------------------------------------------

LONGFORM_WIDTH = 1920
LONGFORM_HEIGHT = 1080
LONGFORM_FPS = 30

LONGFORM_MOTION_OVERSCAN = 1.35
LONGFORM_MOTION_SRC_WIDTH = int(LONGFORM_WIDTH * LONGFORM_MOTION_OVERSCAN) // 2 * 2
LONGFORM_MOTION_SRC_HEIGHT = int(LONGFORM_HEIGHT * LONGFORM_MOTION_OVERSCAN) // 2 * 2

LONGFORM_MOTION_ZOOM = {
    "push_in": (1.00, 1.05),
    "deep_push": (1.00, 1.07),
    "pull_out": (1.05, 1.00),
    "lateral_pan": (1.00, 1.00),  # dominant motion is pan
}

LONGFORM_MOTION_DRIFT_PX = 18.0
LONGFORM_MOTION_SRC_UNSHARP = "unsharp=3:3:0.8"
LONGFORM_MOTION_FLOAT_X = ((8.0, 0.13), (4.0, 0.31))
LONGFORM_MOTION_FLOAT_Y = ((6.0, 0.11), (3.0, 0.27))

LONGFORM_RACK_FOCUS_SIGMA = 9.0
LONGFORM_RACK_FOCUS_START = 0.30
LONGFORM_RACK_FOCUS_DURATION = 2.40


# --------------------------------------------------------------------------------------
# Fal.ai (Balanced Profile: Seedream/Flux + Hailuo/Kling Pro/Veo Fast/Wan)
# --------------------------------------------------------------------------------------

FAL_QUEUE_BASE = env("FAL_QUEUE_BASE_URL")

FAL_SEEDREAM_MODEL = "fal-ai/bytedance/seedream/v4/text-to-image"
FAL_FLUX_MODEL = "fal-ai/flux/dev"
FAL_HAILUO_MODEL = "fal-ai/minimax/hailuo-02/standard/image-to-video"
FAL_KLING_PRO_MODEL = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
FAL_VEO_FAST_MODEL = "fal-ai/veo3.1/fast/image-to-video"
FAL_VEO_FLF_MODEL = "fal-ai/veo3.1/fast/first-last-frame-to-video"
FAL_WAN_MODEL = "fal-ai/wan/v2.2-a14b/image-to-video"
FAL_H3_MAX_MODEL = "fal-ai/minimax/h3-max/image-to-video"

DEFAULT_IMAGE_MODEL = FAL_SEEDREAM_MODEL

# Seedream V4 settings (native 9:16 high-fidelity renders). Aspect comes from image_size
# alone — the seedream v4 text-to-image schema has no aspect_ratio field.
SEEDREAM_WIDTH = 1080
SEEDREAM_HEIGHT = 1920

# Flux dev settings (fallback image generator)
FLUX_WIDTH = 768
FLUX_HEIGHT = 1344
FLUX_STEPS = 32
FLUX_GUIDANCE = 3.5
FLUX_OUTPUT_FORMAT = "png"
FLUX_ACCELERATION = "regular"
FLUX_SAFETY_CHECKER = False

KLING_CFG_PRIMARY = 0.5
KLING_CFG_RETRY = 0.35

# Provider-native duration payload values.  The active run passes its TimelinePlan's
# native duration to MotionForge, so no output is generated merely to be trimmed away.
KLING_DURATION = "5"
VEO_FAST_DURATION = "8s"
HAILUO_DURATION = "6"
HAILUO_RESOLUTION = "768P"
# Wan: 4 seconds at 16 fps = 65 frames; the provider-native profile owns that duration.
WAN_RESOLUTION = "720p"
WAN_FPS = 16
WAN_NUM_FRAMES = int(4.0 * WAN_FPS) + 1  # 65

# MiniMax H3 Max: integer duration 5-15s, 768P resolution
H3_MAX_DURATION = 5
H3_MAX_RESOLUTION = "768P"

POLL_INTERVAL_FAST = 3.0
POLL_INTERVAL_SLOW = 10.0
POLL_BACKOFF_AFTER = 30.0
ATTEMPT_TIMEOUT = 420.0
NETWORK_RETRIES = 3

MAX_PAID_ATTEMPTS = 12


# --------------------------------------------------------------------------------------
# edge-tts (voiceover engine, no key)
# --------------------------------------------------------------------------------------

# Christopher is the News/Novel "Reliable, Authority" persona, which is the Zack D register.
# Fixed 24kHz mono 48kbps output; the bitrate is a library constant and cannot be raised.
EDGE_RATE_MAX_PCT = 18  # past this the intonation flattens
EDGE_RETRIES = 3
EDGE_BACKOFF = 3.0

# edge_tts XML-escapes the input (communicate.py: escape(remove_incompatible_characters())),
# so <break time="..."/> is read ALOUD rather than honoured. The only real prosody handles
# are the rate/pitch/volume params, each validated against ^[+-]\d+(%|Hz)$ — signed
# integers only, no decimals. So drama = one synth call per beat + real ffmpeg silence
# between them (see generator.EdgeVoiceForge / concat_audio_with_pauses).
BEAT_VOICE_PROFILE = {
    "hook":        {"rate": 2,   "pitch": "+0Hz",  "pause_after": 0.20},
    "question":    {"rate": 0,   "pitch": "-4Hz",  "pause_after": 0.25},
    "reveal":      {"rate": 5,   "pitch": "+3Hz",  "pause_after": 0.18},
    "turn":        {"rate": -3,  "pitch": "-8Hz",  "pause_after": 0.35},
    "payoff":      {"rate": -5,  "pitch": "-16Hz", "pause_after": 0.00},
    # Read-only resume compatibility for the former fixed narrative template.
    "myth":        {"rate": 0,   "pitch": "+0Hz",  "pause_after": 0.28},
    "twist":       {"rate": -6,  "pitch": "-10Hz", "pause_after": 0.42},
    "mechanism_a": {"rate": 8,   "pitch": "+5Hz",  "pause_after": 0.20},
    "mechanism_b": {"rate": 6,   "pitch": "+0Hz",  "pause_after": 0.45},
    "kicker":      {"rate": -10, "pitch": "-30Hz", "pause_after": 0.00},
}
BEAT_VOICE_DEFAULT = {"rate": 0, "pitch": "+0Hz", "pause_after": 0.25}

PAUSE_BUDGET = sum(BEAT_VOICE_PROFILE[name]["pause_after"] for name in ("hook", "question", "reveal", "turn", "payoff"))
BEAT_LEAD_SILENCE = 0.12  # a breath before the first beat

def beat_voice(role: str) -> dict:
    return BEAT_VOICE_PROFILE.get(role, BEAT_VOICE_DEFAULT)


def speech_budget_seconds(voice_target_duration: float) -> float:
    """Actual speech budget for one persisted timeline's narration target."""
    return max(1.0, float(voice_target_duration) - PAUSE_BUDGET - BEAT_LEAD_SILENCE)


# --------------------------------------------------------------------------------------
# faster-whisper (primary word timing)
# --------------------------------------------------------------------------------------

# Word timings are measured on the FINAL concatenated vo.mp3 rather than accumulated from
# the per-beat WordBoundary streams. Each beat is its own mp3, so its offsets restart at
# zero, and re-basing them by cumulative duration also inherits every encoder delay/padding
# error in the chain. Whisper reads the file that actually ships, so the captions cannot
# drift from the audio no matter how the parts were assembled.
WHISPER_MODEL = "small"
WHISPER_DEVICE = "cpu"          # CTranslate2, not torch; a Shorts narration on CPU is a few seconds
WHISPER_COMPUTE = "int8"
WHISPER_BEAM = 5


# --------------------------------------------------------------------------------------
# ElevenLabs
# --------------------------------------------------------------------------------------

ELEVEN_BASE = env("ELEVENLABS_BASE_URL")
ELEVEN_MODEL = env("ELEVEN_MODEL") or "eleven_flash_v2_5"
ELEVEN_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_VOICE_ID = env("ELEVENLABS_VOICE_ID") or env("ELEVEN_VOICE_ID") or DANIEL_VOICE_ID

VOICE_SETTINGS = {
    "stability": 0.55,
    "similarity_boost": 0.80,
    "style": 0.15,
    "use_speaker_boost": True,
    "speed": 0.98,
}

# forced-alignment returns a per-request loss; above this we distrust it and fall back.
LOSS_THRESHOLD = 0.60
SPEED_MAX = 1.12
DURATION_TOLERANCE = 0.40


# --------------------------------------------------------------------------------------
# Prompting
# --------------------------------------------------------------------------------------

ASPECT_RATIO_STRING = "16:9" if LONGFORM_MODE else "9:16"
COMPOSITION_STRING = "16:9 horizontal composition" if LONGFORM_MODE else "9:16 vertical composition"
ORIENTATION_STRING = "landscape orientation" if LONGFORM_MODE else "portrait orientation"
ASPECT_RATIO_FULL_STRING = "16:9 horizontal aspect ratio" if LONGFORM_MODE else "9:16 vertical aspect ratio"

DOCUMENTARY_PBR_STYLE = (
    "A clean, high-end 3D animated cinematic frame, minimalist dark studio void lighting, "
    f"expressive smooth character design, dramatic side-shadows, {ASPECT_RATIO_FULL_STRING}, "
    "vivid colors, hyper-detailed textures, Blender Cycles render aesthetic, "
    "Glossy Stylized 3D Mannequin / Medical Animation Render; premium PBR materials, "
    "smooth medical-mannequin surfaces, strong subsurface scattering on translucent material, "
    "dark neutral 3D studio void background, 45-degree warm golden key light and sharp cyan rim light; "
    f"crisp readable silhouette, {COMPOSITION_STRING}"
)

# Physical phenomena read badly when the same low-poly language used for a simple
# explainer character is forced onto them.  This profile intentionally keeps the
# documentary render language, but removes geometry-simplification directives.
PHYSICAL_EFFECTS_STYLE = (
    "High-detail cinematic 3D documentary reconstruction, physically grounded materials; "
    "volumetric participating media, organic turbulent flow, layered semi-transparent gases, "
    "fine airborne particles, natural irregular edges and continuous density variation; "
    "premium PBR metal, ceramic, rock and fabric surfaces with microgeometry and plausible wear; "
    "cinematic contrast, deep shadow detail, filmic atmospheric haze, crisp subject separation; "
    f"high-end Octane-quality production render, {COMPOSITION_STRING}"
)

CLINICAL_ANATOMY_STYLE = (
    "Clean clinical 3D medical illustration, educational and non-graphic; anatomically plausible "
    "proportions, layered tissue boundaries, readable vessel and fibre networks, controlled subsurface "
    "scattering, precise cut surfaces and calm diagnostic lighting; no surgery, blood splatter, exposed wounds, "
    f"or graphic gore; high-detail medical visualization, {COMPOSITION_STRING}"
)

MICROANATOMY_STYLE = (
    "Clean high-detail cellular and molecular 3D visualization; distinct membrane bilayers, organelles, fibres "
    "and molecular layers with physically plausible translucency, controlled microscope illumination and clear "
    f"scale separation; no wet human-scale tissue lighting, no gore; scientific educational render, {COMPOSITION_STRING}"
)

MECHANICAL_DETAIL_STYLE = (
    "High-detail engineering documentary 3D render; plausible metal, ceramic and polymer materials, fasteners, "
    "machined edges, plausible wear, readable cooling channels and internal mechanisms, precise section cuts and "
    f"functional tolerances; clean technical lighting, {COMPOSITION_STRING}"
)

ENVIRONMENT_SPACE_STYLE = (
    "Cinematic scientific environment reconstruction with physically consistent light direction, atmospheric "
    "perspective, terrain or planetary surface micro-detail, scale cues and deep distance layers; high-detail 3D "
    f"documentary render, {COMPOSITION_STRING}"
)

# --------------------------------------------------------------------------------------
# Virtual Explorer (16:9 Long-Form & Widescreen Photorealistic Cinematography)
# --------------------------------------------------------------------------------------

EXPLORER_STYLE_PHOTOREALISTIC = (
    f"Photorealistic cinematic documentary frame, {ASPECT_RATIO_FULL_STRING}, natural atmospheric lighting, "
    "high dynamic range, shallow depth of field with sharp subject focus, "
    "film grain texture, warm color grading, National Geographic / BBC documentary quality, "
    "detailed environmental micro-textures, volumetric light rays, "
    f"hyper-realistic materials and surfaces, 8K detail level, {COMPOSITION_STRING}"
)

EXPLORER_STYLE_HISTORICAL = (
    f"Photorealistic historical reconstruction, {ASPECT_RATIO_FULL_STRING}, "
    "period-accurate architecture and setting, atmospheric golden hour lighting, "
    "cinematic depth, dust particles floating in light beams, weathered stone and ancient wood textures, "
    "historically plausible color palette, epic scale with human reference points, "
    f"masterpiece documentary cinematography, {COMPOSITION_STRING}"
)

EXPLORER_STYLE_MYSTERY = (
    f"Dark atmospheric photorealistic scene, {ASPECT_RATIO_FULL_STRING}, moody blue-teal color grade, "
    "fog and mist effects, dramatic chiaroscuro lighting, deep mysterious shadows, "
    "subtle anamorphic lens flare, cinematic suspense quality, tension-building composition, "
    f"{COMPOSITION_STRING}"
)

EXPLORER_STYLE_NATURE = (
    f"Breathtaking nature cinematography, {ASPECT_RATIO_FULL_STRING}, pristine wilderness, "
    "golden hour or blue hour lighting, macro detail on physical geological textures, "
    "epic landscape scale, award-winning natural history documentary quality, "
    f"vivid natural colors without oversaturation, {COMPOSITION_STRING}"
)

EXPLORER_STYLE_CHARACTER = (
    f"Photorealistic portrait, {ASPECT_RATIO_FULL_STRING}, natural skin texture with pores and "
    "micro-details, warm ambient lighting, soft catchlights in eyes, "
    "shallow depth of field background blur, candid expedition field photography style, "
    f"authentic engaging expression, {COMPOSITION_STRING}"
)

# Kept as the compatibility default for older scripts and asset sheets.  New scene
# compilers select a profile per shot via style_for_profile().
ZACK_STYLE = DOCUMENTARY_PBR_STYLE
CANONICAL_STYLE_VERSION = "zdf-scene-intelligence-v3"

VISUAL_PROFILE_DOCUMENTARY = "documentary_pbr"
VISUAL_PROFILE_PHYSICAL = "physical_effects_detail"
VISUAL_PROFILE_CLINICAL = "clinical_anatomy"
VISUAL_PROFILE_MICROANATOMY = "microanatomy_detail"
VISUAL_PROFILE_MECHANICAL = "mechanical_detail"
VISUAL_PROFILE_ENVIRONMENT = "environment_space_detail"
VISUAL_PROFILE_EXPLORER_PHOTO = "explorer_photorealistic"
VISUAL_PROFILE_EXPLORER_HISTORICAL = "explorer_historical"
VISUAL_PROFILE_EXPLORER_MYSTERY = "explorer_mystery"
VISUAL_PROFILE_EXPLORER_NATURE = "explorer_nature"
VISUAL_PROFILE_EXPLORER_CHARACTER = "explorer_character"
VISUAL_PROFILES = (
    VISUAL_PROFILE_DOCUMENTARY, VISUAL_PROFILE_PHYSICAL, VISUAL_PROFILE_CLINICAL,
    VISUAL_PROFILE_MICROANATOMY, VISUAL_PROFILE_MECHANICAL, VISUAL_PROFILE_ENVIRONMENT,
    VISUAL_PROFILE_EXPLORER_PHOTO, VISUAL_PROFILE_EXPLORER_HISTORICAL,
    VISUAL_PROFILE_EXPLORER_MYSTERY, VISUAL_PROFILE_EXPLORER_NATURE,
    VISUAL_PROFILE_EXPLORER_CHARACTER,
)
VISUAL_DOMAINS = (
    "character", "anatomy", "microanatomy", "technical_mechanism",
    "physical_effect", "environment", "space",
)
DETAIL_TARGETS = ("editorial", "clinical", "mechanical", "physical_realism")
STRUCTURE_TAGS = (
    "organ", "vessel", "bone", "muscle", "tissue", "cell", "nucleus", "membrane",
    "organelle", "dna", "chromosome", "engine", "turbine", "nozzle", "gear", "circuit",
    "cooling_channel", "valve", "cross_section",
)
EFFECT_TAGS = (
    "rocket_exhaust", "smoke", "fire", "fluid", "dust", "explosion",
    "atmosphere", "space", "technical_macro",
)
CRITICAL_EFFECT_TAGS = frozenset({"rocket_exhaust", "smoke", "fire", "fluid", "dust", "explosion"})
EFFECT_KEYWORDS = {
    "rocket_exhaust": ("rocket exhaust", "engine ignition", "engine ignite", "launch pad", "rocket lifts", "plume", "nozzle flame"),
    "smoke": ("smoke", "fume", "vapour", "vapor", "condensation cloud"),
    "fire": ("fire", "flame", "burning", "combustion", "embers"),
    "fluid": ("fluid", "water", "blood", "liquid", "flowing", "pouring"),
    "dust": ("dust", "debris", "regolith", "ash", "particles"),
    "explosion": ("explosion", "explosive", "blast", "shockwave", "detonation"),
    "atmosphere": ("atmosphere", "cloud", "storm", "sky", "air"),
    "space": ("space", "orbit", "moon", "planet", "starfield", "lunar"),
    "technical_macro": ("macro", "cooling channel", "turbopump", "engine housing", "nozzle wall", "cross-section"),
}

STRUCTURE_KEYWORDS = {
    "organ": ("heart", "lung", "kidney", "liver", "brain", "organ"),
    "vessel": ("vessel", "vein", "artery", "capillary", "vascular"),
    "bone": ("bone", "rib", "skeleton", "femur", "marrow"),
    "muscle": ("muscle", "myocyte", "muscular", "fibre", "fiber"),
    "tissue": ("tissue", "epithelium", "dermis", "tendon", "cartilage"),
    "cell": ("cell", "cellular", "cyte"),
    "nucleus": ("nucleus", "nuclei", "nuclear"),
    "membrane": ("membrane", "membranous", "bilayer"),
    "organelle": ("organelle", "mitochondria", "ribosome", "golgi"),
    "dna": ("dna", "genome", "double helix", "chromatin"),
    "chromosome": ("chromosome", "chromosomes"),
    "engine": ("engine", "motor", "turbopump", "combustion chamber"),
    "turbine": ("turbine", "turbofan", "compressor", "rotor"),
    "nozzle": ("nozzle", "nozzle bell"),
    "gear": ("gear", "gearbox", "cog", "transmission"),
    "circuit": ("circuit", "pcb", "semiconductor", "microchip", "wire"),
    "cooling_channel": ("cooling channel", "cooling tube", "coolant duct"),
    "valve": ("valve", "solenoid", "actuator"),
    "cross_section": ("cross-section", "cross section", "cutaway", "cut-away"),
}

ENVIRONMENT_KEYWORDS = ("landscape", "forest", "ocean", "desert", "mountain", "city", "atmosphere", "weather")
SPACE_KEYWORDS = ("space", "orbit", "moon", "lunar", "planet", "asteroid", "starfield", "galaxy")
HIGH_DETAIL_DOMAINS = frozenset({"anatomy", "microanatomy", "technical_mechanism", "physical_effect"})


def classify_scene_intelligence(
    *texts: str, requested_domain: str | None = None, requested_detail_target: str | None = None,
    requested_structure_tags: list[str] | None = None, requested_effect_tags: list[str] | None = None,
    requested_quality_critical: bool | None = None,
) -> dict:
    """Classify a scene with deterministic safety locks around LLM creative choices."""
    haystack = " ".join(t for t in texts if t).casefold()
    structure_tags = {str(tag).strip() for tag in (requested_structure_tags or []) if str(tag).strip() in STRUCTURE_TAGS}
    effect_tags = {str(tag).strip() for tag in (requested_effect_tags or []) if str(tag).strip() in EFFECT_TAGS}
    for tag, keywords in STRUCTURE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            structure_tags.add(tag)
    for tag, keywords in EFFECT_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            effect_tags.add(tag)

    # Domain locks are deliberately ordered from most semantically specific to broadest.
    if structure_tags & {"cell", "nucleus", "membrane", "organelle", "dna", "chromosome"}:
        domain, target, profile = "microanatomy", "clinical", VISUAL_PROFILE_MICROANATOMY
    elif structure_tags & {"organ", "vessel", "bone", "muscle", "tissue"}:
        domain, target, profile = "anatomy", "clinical", VISUAL_PROFILE_CLINICAL
    elif effect_tags & CRITICAL_EFFECT_TAGS:
        domain, target, profile = "physical_effect", "physical_realism", VISUAL_PROFILE_PHYSICAL
    elif structure_tags & {"engine", "turbine", "nozzle", "gear", "circuit", "cooling_channel", "valve"}:
        domain, target, profile = "technical_mechanism", "mechanical", VISUAL_PROFILE_MECHANICAL
    elif any(keyword in haystack for keyword in SPACE_KEYWORDS):
        domain, target, profile = "space", "physical_realism", VISUAL_PROFILE_ENVIRONMENT
    elif any(keyword in haystack for keyword in ENVIRONMENT_KEYWORDS):
        domain, target, profile = "environment", "editorial", VISUAL_PROFILE_ENVIRONMENT
    else:
        domain = requested_domain if requested_domain in VISUAL_DOMAINS else "character"
        target = requested_detail_target if requested_detail_target in DETAIL_TARGETS else "editorial"
        profile = VISUAL_PROFILE_DOCUMENTARY

    critical = domain in HIGH_DETAIL_DOMAINS
    if requested_quality_critical is True:
        critical = True
    return {
        "visual_domain": domain, "detail_target": target, "visual_profile": profile,
        "structure_tags": sorted(structure_tags), "effect_tags": sorted(effect_tags),
        "quality_critical": critical,
    }


def classify_visual_profile(*texts: str, requested_profile: str | None = None,
                            requested_tags: list[str] | None = None) -> tuple[str, list[str]]:
    """Return a deterministic scene profile, preserving valid LLM classifications.

    The keyword pass is intentionally additive: a model that forgets to label a rocket
    launch still receives the physical-effects profile rather than producing polygonal
    exhaust.  Unknown LLM tags are discarded so manifests remain queryable.
    """
    scene = classify_scene_intelligence(*texts, requested_effect_tags=requested_tags)
    profile = requested_profile if requested_profile in VISUAL_PROFILES else scene["visual_profile"]
    # A deterministic domain lock must not be defeated by an old low-detail profile.
    if scene["visual_domain"] in HIGH_DETAIL_DOMAINS:
        profile = scene["visual_profile"]
    return profile, scene["effect_tags"]


def style_for_profile(profile: str | None) -> str:
    return {
        VISUAL_PROFILE_PHYSICAL: PHYSICAL_EFFECTS_STYLE,
        VISUAL_PROFILE_CLINICAL: CLINICAL_ANATOMY_STYLE,
        VISUAL_PROFILE_MICROANATOMY: MICROANATOMY_STYLE,
        VISUAL_PROFILE_MECHANICAL: MECHANICAL_DETAIL_STYLE,
        VISUAL_PROFILE_ENVIRONMENT: ENVIRONMENT_SPACE_STYLE,
        VISUAL_PROFILE_EXPLORER_PHOTO: EXPLORER_STYLE_PHOTOREALISTIC,
        VISUAL_PROFILE_EXPLORER_HISTORICAL: EXPLORER_STYLE_HISTORICAL,
        VISUAL_PROFILE_EXPLORER_MYSTERY: EXPLORER_STYLE_MYSTERY,
        VISUAL_PROFILE_EXPLORER_NATURE: EXPLORER_STYLE_NATURE,
        VISUAL_PROFILE_EXPLORER_CHARACTER: EXPLORER_STYLE_CHARACTER,
    }.get(profile, DOCUMENTARY_PBR_STYLE)


def structure_detail_prompt(domain: str, tags: list[str] | tuple[str, ...], intensity: str = "peak") -> str:
    """Return precise, non-graphic domain detail to complement the generic style profile."""
    selected = set(tags)
    prefix = "subtle structural detail emerging" if intensity == "latent" else "fully readable structural detail"
    if domain == "anatomy":
        return f"{prefix}: anatomically plausible layered tissue, clean vessel networks, directional muscle fibres and precise clinical cut surfaces"
    if domain == "microanatomy":
        return f"{prefix}: distinct membrane bilayers, individual organelles, layered molecular structures and controlled translucent scale separation"
    if domain == "technical_mechanism":
        parts = []
        if "cooling_channel" in selected: parts.append("visible cooling channels with plausible wall thickness")
        if "turbine" in selected: parts.append("readable turbine blades and mechanical clearances")
        if "nozzle" in selected: parts.append("machined nozzle surfaces and internal channel geometry")
        return f"{prefix}: " + "; ".join(parts or ["readable fasteners, material joins, machined surfaces and functional internal mechanisms"])
    if domain in {"environment", "space"}:
        return f"{prefix}: physically consistent light direction, scale cues, distant depth layers and detailed terrain or surface material"
    return ""


def lighting_for_scene(domain: str, scale: str | None) -> str:
    """Prevent anatomy and engineering shots inheriting unrelated human-scale lighting."""
    if domain == "anatomy":
        return "clean clinical cool-white key light, neutral blue-grey fill, soft rim separation and readable tissue depth"
    if domain == "microanatomy":
        return "controlled microscope illumination, cool transmitted light, restrained amber organelle accents and black depth falloff"
    if domain == "technical_mechanism":
        return "neutral engineering key light, controlled specular highlights on metal and deep shadows inside cutaway cavities"
    if domain in {"environment", "space"}:
        return "physically consistent directional light, atmospheric perspective and accurate deep-space shadow falloff"
    return scale_light(scale)


def effect_detail_prompt(tags: list[str] | tuple[str, ...], intensity: str = "peak") -> str:
    """Scene-specific physical detail appended only to critical effect scenes."""
    selected = set(tags)
    details: list[str] = []
    if "rocket_exhaust" in selected:
        details.append(
            "four distinct engine exhaust streams with white-hot cores, visible shock diamonds, "
            "turbulent translucent gas, heat shimmer, rolling grey-white condensation smoke and launchpad dust"
        )
    if "smoke" in selected:
        details.append("volumetric smoke with turbulent billows, wispy edges and continuously changing density")
    if "fire" in selected:
        details.append("layered flame with a bright inner core, transparent heat distortion, sparks and soot")
    if "fluid" in selected:
        details.append("continuous fluid motion with surface tension, specular ripples and suspended droplets")
    if "dust" in selected:
        details.append("fine particulate dust lifting in irregular eddies, with foreground and background depth layers")
    if "explosion" in selected:
        details.append("expanding pressure wave, fragmented debris, turbulent fireball and volumetric smoke")
    if not details:
        return ""
    prefix = "subtle physical effect beginning" if intensity == "latent" else "fully developed physical effect"
    return f"{prefix}: " + "; ".join(details)


GLOBAL_NEGATIVE = (
    "text, caption, subtitle, watermark, logo, signature, UI, interface, "
    "open mouth, talking, lip movement, speech, teeth, "
    "extra limbs, deformed anatomy, duplicated subject, collage, split screen, "
    "waxy plastic skin, toy-like rubber materials, blurry, low quality, jpeg artifacts, "
    "live-action presentation, oversaturated, flat lighting, "
    "floaty motion, sliding feet, warping, morphing, jitter, 2D camera slide"
)

VEO_NEGATIVE = (
    "photorealistic gore, blood, open wounds, sharp weapons, blades, razors, real children, real celebrities, brand logos, "
    "floaty motion, sliding feet, warping, morphing, clipping through geometry, body parts merging, gravity-defying, rubbery limbs, jitter, 2D camera slide, cross-dissolve morph, frozen static pose"
)

# The compiler, rather than the LLM, owns this style.  Keeping an explicit version in
# manifests makes it possible to compare a later visual-quality experiment with the
# exact canonical suffix that produced an older run.

KLING_NEGATIVE = (
    "talking, lip movement, mouth opening, speech, "
    "text, caption, subtitle, watermark, "
    "subject change, morphing into different object, camera cut, scene change, "
    "waxy plastic skin, toy-like rubber materials, blur, distort, low quality, flicker"
)

# Shared narration pacing only.  Production story structure is selected by
# NarrativePlan (mechanism_reveal or mystery_escalation), never by a fixed
# myth->twist->mechanism->kicker formula.
BEAT_TEMPLATE = [
    {"index": 1, "role": "hook", "share": 0.16,
     "function": "Put the visible event, risk, or paradox on screen."},
    {"index": 2, "role": "question", "share": 0.20,
     "function": "Clarify what the viewer must now understand."},
    {"index": 3, "role": "reveal", "share": 0.28,
     "function": "Show the causal mechanism, rule, or escalation."},
    {"index": 4, "role": "turn", "share": 0.20,
     "function": "Add the functional limit, disruption, response, or comparison."},
    {"index": 5, "role": "payoff", "share": 0.16,
     "function": "Physically or emotionally close the opening question."},
]


def beat_windows(voice_target_duration: float) -> list[tuple[float, float]]:
    """(t_start, t_end) per beat for one timeline's measured speech budget."""
    budget = speech_budget_seconds(voice_target_duration)
    out, t = [], BEAT_LEAD_SILENCE
    for b in BEAT_TEMPLATE:
        span = budget * b["share"]
        out.append((t, t + span))
        t += span + beat_voice(b["role"])["pause_after"]
    return out

# A structured response may need one targeted correction after a schema miss. More than
# two paid calls is not a safe default: malformed tool payloads previously consumed large
# token budgets without ever reaching the pre-credit storyboard gate.
SCRIPT_REPAIR_ATTEMPTS = max(1, int(env("SCRIPT_REPAIR_ATTEMPTS") or "3"))

# Retention rule from the prompt-engineering research: the opening hook must land early.
# Twelve English words remains inside the first spoken beat while giving structured models
# enough room to state a grammatical scientific premise.
HOOK_MAX_WORDS = 12


# --------------------------------------------------------------------------------------
# Languages
# --------------------------------------------------------------------------------------

# Aura English is paced from the usable speech window, not a fixed 40-second band.
# Keep this overrideable for a measured voice/model change.
ENGLISH_PRODUCTION_WPS = (
    # Zack D. Films viral pacing is snappy and staccato (160-175 WPM / ~2.75 spoken words/sec).
    float(env("DEEPGRAM_ENGLISH_WPS") or "2.75") if TTS_PROVIDER == "deepgram"
    else 2.50 if TTS_PROVIDER == "elevenlabs" else 2.64
)
LANG_PROFILES = {
    "en": {
        "name": "English",
        "voice": "en-US-ChristopherNeural",
        "wps": ENGLISH_PRODUCTION_WPS,
        "target": 0,
        "min": 0,
        "max": 0,
    },
    "tr": {
        "name": "Turkish",
        "voice": "tr-TR-AhmetNeural",
        "wps": 1.74,
        "target": 0,
        "min": 0,
        "max": 0,
    },
}


DEFAULT_LANG = "en"


def lang_profile(lang: str | None) -> dict:
    code = (lang or DEFAULT_LANG).lower()
    if code not in LANG_PROFILES:
        raise ValueError(
            f"Unsupported language '{code}'. Use one of: {', '.join(LANG_PROFILES)}"
        )
    return LANG_PROFILES[code]


def narration_profile(lang: str | None, voice_target_duration: float) -> dict:
    """Return a run-local word budget without mutating global language configuration."""
    profile = dict(lang_profile(lang))
    target = max(8, round(profile["wps"] * speech_budget_seconds(voice_target_duration)))
    if (lang or DEFAULT_LANG).lower() == "tr":
        # Turkish syllable structure and authored pauses make a duration estimate less
        # reliable than the measured narration that locks the visual plan.
        # Broad enough for 45..55-second shorts while preventing runaway scripts.
        profile.update({"target": min(90, max(70, target)), "min": 70, "max": 90})
        return profile
    if (lang or DEFAULT_LANG).lower() == "en" and TTS_PROVIDER == "deepgram":
        # Keep word count within safe 6-13 block Shorts envelope (100-120 words per ADR-013)
        # to ensure measured narration lands reliably between 24-50s and never overflows MAX_BLOCKS (13).
        if voice_target_duration >= 40.0:
            safe_target = min(106, target)
            profile.update({
                "target": safe_target,
                "min": max(100, round(safe_target * 0.94)),
                "max": min(112, round(safe_target * 1.06)),
            })
        else:
            safe_target = target
            profile.update({
                "target": safe_target,
                "min": round(safe_target * 0.96),
                "max": round(safe_target * 1.04),
            })
        return profile
    profile.update({
        "target": target,
        "min": round(target * 0.91),
        "max": round(target * 1.06),
    })
    return profile


def beat_word_range(beat: dict, profile: dict) -> tuple[int, int]:
    """Scale one beat's words to a run-local narration budget."""
    target = profile["target"]
    mid = target * beat["share"]
    return max(3, round(mid * 0.88)), max(4, round(mid * 1.14))


# --------------------------------------------------------------------------------------
# Camera direction per block
# --------------------------------------------------------------------------------------

# Legacy/local fallback camera variation. New SceneCards pass their authored
# transition_hint to MotionEngine; this block-number map is never fed into a new Flow/Fal
# narrative prompt and is only used when no authored transition intent is available.
BLOCK_CAMERA = {
    1: {
        "directive": "slow creeping push-in, subtle floating handheld camera",
        "motion": "push_in",
        "drift": "up",
        "rack_focus": False,
    },
    2: {
        "directive": "microscopic zoom-in, cross-section shift, focus pull",
        "motion": "deep_push",
        "drift": "down",
        "rack_focus": True,
    },
    3: {
        "directive": "slow pull-back reveal, shifting light",
        "motion": "pull_out",
        "drift": "up",
        "rack_focus": False,
    },
    4: {
        "directive": "low angle camera pan, macro depth of field",
        "motion": "push_in",
        "drift": "down",
        "rack_focus": False,
    },
    5: {
        "directive": "slow orbit rotation, diagnostic lighting change",
        "motion": "deep_push",
        "drift": "up",
        "rack_focus": True,
    },
    6: {
        "directive": "slow push-in and dramatic focus pull, cinematic rim light",
        "motion": "pull_out",
        "drift": "down",
        "rack_focus": False,
    },
}


def block_camera(block: int) -> dict:
    idx = (block - 1) % len(BLOCK_CAMERA) + 1
    return BLOCK_CAMERA[idx]


# --------------------------------------------------------------------------------------
# Captions (see captions.py)
# --------------------------------------------------------------------------------------

CAPTIONS_ENABLED = True
CAPTION_FONT = "Arial"
CAPTION_FONT_SIZE = 82
CAPTION_BOLD = True
CAPTION_OUTLINE = 7
CAPTION_SHADOW = 3
CAPTION_MARGIN_V = 470
CAPTION_MARGIN_H = 40
# libass BGR, not RGB: &H00D7FF& is amber.
CAPTION_ACTIVE_COLOUR = "&H00D7FF&"
CAPTION_EMPHASIS_SCALE = 112
# WrapStyle 0 (smart wrap) is mandatory: WrapStyle 2 (no wrap) clips long words
# horizontally instead of breaking the line.
CAPTION_WRAP_STYLE = 0
CAPTION_MAX_WORDS = 3
CAPTION_MAX_CHARS = 22
CAPTION_MIN_DURATION = 0.35
CAPTION_LEAD_IN = 0.06
CAPTION_FONTS_DIR = "C:/Windows/Fonts"


def deterministic_seed(topic: str, subject_id: str) -> int:
    """Same topic + same subject always yields the same image seed."""
    return zlib.crc32(f"{topic}:{subject_id}".encode("utf-8")) % (2**31)


# --------------------------------------------------------------------------------------
# Asset Library
# --------------------------------------------------------------------------------------

ASSETS_DIR = ROOT / "assets"
ASSET_CATALOG = ASSETS_DIR / "catalog.json"
ASSET_SHEETS_DIR = ASSETS_DIR / "sheets"
ASSET_PROMPTS_DIR = ASSETS_DIR / "prompts"

SHEET_RATIOS = {
    "character": "3:2" if LONGFORM_MODE else "2:3",
    "prop": "1:1",
    "environment": ASPECT_RATIO_STRING,
}

SHEET_STYLE_SUFFIX = {
    "character": (
        "Character reference sheet, full body, neutral standing pose, plain light-grey studio background — "
        f"{ZACK_STYLE}, single character only, mouth closed and neutral"
    ),
    "prop": (
        "Object reference, isolated on a plain light-grey background — "
        f"{ZACK_STYLE}, single object only"
    ),
    "environment": (
        "ENVIRONMENT SHEET — EMPTY LOCATION PLATE. ABSOLUTELY NO people, NO animals, NO characters, NO subject — "
        f"{ZACK_STYLE}"
    ),
}



# --------------------------------------------------------------------------------------
# Legacy camera-journey compatibility
# --------------------------------------------------------------------------------------

# These values are retained only to read archived scripts and prompt-study fixtures. New
# production runs use NarrativePlan + SceneCard and must not select a journey phase.
JOURNEY_TYPES = ["body_dive", "object_explode", "scale_shift", "time_lapse"]

# Ordered from widest to narrowest
CAMERA_SCALES = ["wide", "medium", "close", "macro", "micro", "nano"]

JOURNEY_PHASES = ["establish", "descend", "explore", "reveal", "resolve"]

# Max allowed jump between adjacent scales (1 = only neighbours allowed).  A full
# powers-of-ten-scale jump needs an intervening shot; otherwise image-to-video models tend
# to morph anatomy rather than travel through it.
MAX_SCALE_JUMP = 1

# Viewing angles for perspective consistency validation between paired keyframes.
# Adjacent keyframes in the same shot must share camera_angle unless the shot uses
# cross_section or match_cut transition.
CAMERA_ANGLES = [
    "eye_level_front",       # Eye-level, straight on
    "eye_level_3q_left",     # Eye-level, 3/4 left
    "eye_level_3q_right",    # Eye-level, 3/4 right
    "high_angle",            # Looking down at subject
    "low_angle",             # Looking up at subject
    "top_down",              # Directly above
    "interior",              # Interior cross-section view
]


# --------------------------------------------------------------------------------------
# Targeted spatial camera (see editor._targeted_pan_terms)
# --------------------------------------------------------------------------------------

# Which region of the frame the neon-green arrow / red trajectory line points at. The
# camera pushes toward THAT point instead of the frame centre, so the move and the
# narration are aimed at the same thing.
QUADRANTS = [
    "center", "top_left", "top_right", "bottom_left", "bottom_right",
    "upper_center", "lower_center",
]

# Normalised (x, y) targets. Corners sit at 0.28/0.26 rather than the obvious 0.25/0.75:
# further out buys the camera real reach before clip() saturates it at the frame edge.
QUADRANT_COORDS = {
    "center":       (0.50, 0.50),
    "top_left":     (0.28, 0.26),
    "top_right":    (0.72, 0.26),
    "bottom_left":  (0.28, 0.74),
    "bottom_right": (0.72, 0.74),
    "upper_center": (0.50, 0.28),
    "lower_center": (0.50, 0.72),
}

# How much z climbs above BASE_ZOOM across a targeted block. This is not decoration: the
# reachable pan offset is (dim - dim/z)/2, so at BASE_ZOOM=1.06 a target at 0.28 moves the
# camera only 30.6px (2.8% of frame) and reads as nothing. At z=1.30 the reach is +-124.6px
# (11.5%) and the 22% scale-up carries the rest of the move.
TARGET_ZOOM_GAIN = 0.24
# Veo at 720p: a z=1.30 crop is a 1.95x upscale and goes soft. Measure the first real
# block with ffprobe and switch to this if the height comes back below 1080.
TARGET_ZOOM_GAIN_720P = 0.16

# The Veo clip already contains its own camera move. Pushing on top of every block gives a
# double-move, so the targeted push only fires on shots whose transition is itself inward.
TARGET_PUSH_HINTS = {"zoom_in", "cross_section", "match_cut"}


def target_zoom_gain(source_height: int | None = None) -> float:
    """Drop the gain when the footage is below 1080p, where the crop would go soft."""
    if source_height and source_height < HEIGHT:
        return TARGET_ZOOM_GAIN_720P
    return TARGET_ZOOM_GAIN


def quadrant_coord(name: str | None) -> tuple[float, float]:
    return QUADRANT_COORDS.get((name or "center").strip(), QUADRANT_COORDS["center"])


# --------------------------------------------------------------------------------------
# Model Recommendations (per scene complexity)
# --------------------------------------------------------------------------------------

# Scenes at these scales benefit from the more capable video model
MODEL_RECOMMENDATION = {
    "wide":   "Omni Flash",
    "medium": "Omni Flash",
    "close":  "Veo 3.1",
    "macro":  "Veo 3.1",
    "micro":  "Veo 3.1",
    "nano":   "Veo 3.1",
}

# Legacy annotation handling strategy per phase. New compilers add an annotation only
# when SceneCard.proof_on_screen explicitly calls for one.
ANNOTATION_PHASE_RULES = {
    "establish": "none",       # Clean cinematic intro
    "descend":   "green",      # Neon-green arrows guide the eye inward
    "explore":   "green",      # Neon-green outlines explain mechanism
    "reveal":    "red",        # Red trajectories/cracks show force/danger
    "resolve":   "none",       # Clean cinematic outro
}

MARKER_PROSE = {
    "green": "neon-green arrow",
    "red": "red trajectory line",
    "none": "focal",
}

QUADRANT_PROSE = {
    "center": "centre",
    "top_left": "upper-left",
    "top_right": "upper-right",
    "bottom_left": "lower-left",
    "bottom_right": "lower-right",
    "upper_center": "upper-centre",
    "lower_center": "lower-centre",
}


def annotation_rule(phase: str | None) -> str:
    return ANNOTATION_PHASE_RULES.get((phase or "explore").strip(), "green")


def marker_prose(phase: str | None) -> str:
    return MARKER_PROSE[annotation_rule(phase)]


def quadrant_prose(name: str | None) -> str:
    return QUADRANT_PROSE.get((name or "center").strip(), "centre")


# --------------------------------------------------------------------------------------
# Legacy VFX prompt layer (used only by the legacy Flow compiler)
# --------------------------------------------------------------------------------------

# (latent, peak) per journey phase. The start keyframe gets `latent`, the end keyframe gets
# `peak`. This asymmetry is the whole point: Veo interpolates between First and Last Frame,
# so if both frames carry the effect at the same intensity there is nothing left to
# interpolate and Veo just slides the camera.
VFX_LAYER = {
    "establish": (
        "still air, faint dust motes suspended in the key light",
        "dust motes beginning to drift, first hint of interior glow",
    ),
    "descend": (
        "a single hairline fissure of cyan light on the surface",
        "the fissure blown open into a corona ring of cyan light, "
        "particles streaming outward along the ring",
    ),
    "explore": (
        "interior structure faintly backlit through translucent tissue",
        "structure fully lit from within, volumetric god-rays through the membrane, "
        "fine particulate dispersion in the beam",
    ),
    "reveal": (
        "compression building, micro-cracks radiating from the impact point",
        "explosive light burst at the impact point, shockwave ring, "
        "debris dispersing along the red trajectory lines",
    ),
    "resolve": (
        "the burst collapsing, embers cooling",
        "settled darkness, one last ember drifting out of frame",
    ),
}

CAMERA_TRACK_TEMPLATE = (
    "camera tracks and pushes in toward the {region} of the frame, keeping the {marker} "
    "marker centred as it closes; the marker stays locked to the same anatomical point "
    "throughout, no cut, no subject change"
)

VFX_EVOLUTION_TEMPLATE = "the effect evolves from {latent} into {peak} across the shot"


def vfx_layer(phase: str | None) -> tuple[str, str]:
    return VFX_LAYER.get((phase or "explore").strip(), VFX_LAYER["explore"])


# --------------------------------------------------------------------------------------
# Scale-aware lighting palette (#4 improvement)
# --------------------------------------------------------------------------------------

# The ZACK_STYLE string uses a single warm-golden / cobalt-blue rig that looks great at
# human scale but is physically nonsensical inside a cell nucleus.  Each scale gets its
# own rig that stays stylistically coherent at that magnification level.
SCALE_LIGHT = {
    "wide": (
        "dramatic 45-degree warm golden key light from screen-left, "
        "deep cobalt-blue shadow fill, vivid cyan rim light, dark neutral void background, "
        "volumetric atmospheric haze, 85mm prime lens, shallow DOF bokeh, "
        "detailed environment geometry with parallax depth layers, atmospheric perspective"
    ),
    "medium": (
        "soft directional amber key light, cool blue-grey fill, subtle cyan rim, "
        "dark neutral backdrop, shallow depth of field, 85mm lens, "
        "textured backdrop with soft falloff, subtle contact shadows grounding the subject"
    ),
    "close": (
        "clinical cool-white side light from screen-right, "
        "deep red subsurface glow bleeding through wet tissue, cyan rim, "
        "dark void background, macro lens, "
        "intricate internal geometry, layered translucent membranes, crisp micro-detail"
    ),
    "macro": (
        "transmitted white light from below as in a light microscope, "
        "deep red subsurface-scattering through tissue fibers, "
        "cyan edge highlights, pitch-black background, "
        "intricate internal geometry, layered translucent membranes, crisp micro-detail"
    ),
    "micro": (
        "bioluminescent cyan transmitted light, "
        "cell membrane emitting a soft blue-green SSS glow, "
        "organelles lit with warm amber point sources, cosmic void background, "
        "intricate internal geometry, layered translucent membranes, crisp micro-detail"
    ),
    "nano": (
        "ethereal blue X-ray transmitted light, "
        "DNA double-helix strands glowing teal-cyan, "
        "chromatin emitting violet phosphorescence, absolute void black background, "
        "intricate internal geometry, layered translucent membranes, crisp micro-detail"
    ),
}


def scale_light(scale: str | None) -> str:
    """Return the physically correct lighting description for the given render scale."""
    return SCALE_LIGHT.get((scale or "medium").strip(), SCALE_LIGHT["medium"])


# --------------------------------------------------------------------------------------
# Transition prose for video prompts (#6 improvement)
# --------------------------------------------------------------------------------------

# These sentences are injected into the video_prompt to give Veo explicit interpolation
# direction. Without them Veo defaults to a smooth linear dissolve between keyframes,
# which reads as flat and makes cross_section and match_cut indistinguishable.
TRANSITION_PROSE = {
    "zoom_in": (
        "The viewpoint accelerates into the subject as if pulled by gravity — "
        "the frame tightens steadily until the subject fills the full vertical height."
    ),
    "zoom_out": (
        "The camera retreats in a long dolly pull-back; the subject shrinks as "
        "the surrounding context blooms into view around it."
    ),
    "cross_section": (
        "The outer surface of the subject splits apart in a single clean geometric cut, "
        "revealing the perfectly rendered interior in one continuous unbroken move — "
        "no cut, no flash, no dissolve."
    ),
    "match_cut": (
        "A dominant shape in the outgoing frame morphs seamlessly into a matching "
        "shape in the incoming subject — same geometry, different scale; the viewer "
        "only realises the subject has changed after the cut."
    ),
    "whip": (
        "A fast lateral whip-pan carries the camera off the current subject in a "
        "motion blur streak and snaps it onto the next — kinetic, deliberate, "
        "and visually surprising."
    ),
    "none": (
        "The camera settles on the final frame with a slow, barely perceptible drift "
        "to stillness — no cut, no further motion."
    ),
}


def transition_prose(hint: str | None) -> str:
    return TRANSITION_PROSE.get((hint or "none").strip(), TRANSITION_PROSE["none"])
