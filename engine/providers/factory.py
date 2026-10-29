"""Explicit registry for provider adapter strategies in YOUTUBE_STUDIO.

Only active, verified providers are registered:
- LLM: grok, gemini_flash
- Video: playwright_flow
- Image: playwright_flow
- Voice: deepgram
- SFX: local_manifest, mmaudio
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from dotenv import load_dotenv

from .base import (
    BaseImageProvider,
    BaseLLMProvider,
    BaseSfxProvider,
    BaseVideoProvider,
    BaseVoiceProvider,
    ConfigurationError,
)

ProviderT = TypeVar(
    "ProviderT",
    BaseLLMProvider,
    BaseImageProvider,
    BaseVideoProvider,
    BaseVoiceProvider,
    BaseSfxProvider,
)
ProviderConstructor = Callable[..., ProviderT]


class ProviderFactory(Generic[ProviderT]):
    """Create a registered adapter for exactly one capability and provider name."""

    def __init__(self, capability: str, env_var: str) -> None:
        self.capability = capability
        self.env_var = env_var
        self._constructors: dict[str, ProviderConstructor[ProviderT]] = {}
        self._required_env: dict[str, tuple[str, ...]] = {}

    def register(
        self,
        name: str,
        constructor: ProviderConstructor[ProviderT],
        *,
        required_env: tuple[str, ...] = (),
    ) -> None:
        normalized = self._normalize(name)
        if normalized in self._constructors:
            raise ValueError(
                f"{self.capability} provider '{normalized}' is already registered"
            )
        self._constructors[normalized] = constructor
        self._required_env[normalized] = tuple(required_env)

    def create(self, name: str | None = None, **kwargs: Any) -> ProviderT:
        selected = self._normalize(name or os.getenv(self.env_var, ""))
        if not selected:
            raise ConfigurationError(
                f"No {self.capability} provider selected. Set {self.env_var}."
            )
        try:
            constructor = self._constructors[selected]
        except KeyError as exc:
            available = ", ".join(sorted(self._constructors)) or "none"
            raise ConfigurationError(
                f"Unknown {self.capability} provider '{selected}'. "
                f"Registered providers: {available}."
            ) from exc
        missing = [key for key in self._required_env[selected] if not os.getenv(key)]
        if missing:
            raise ConfigurationError(
                f"{self.capability} provider '{selected}' requires: "
                f"{', '.join(missing)}. Configure them in .env."
            )
        return constructor(**kwargs)

    @property
    def registered_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._constructors))

    @staticmethod
    def _normalize(name: str) -> str:
        return name.strip().casefold().replace("-", "_")


llm_providers: ProviderFactory[BaseLLMProvider] = ProviderFactory("LLM", "LLM_PROVIDER")
image_providers: ProviderFactory[BaseImageProvider] = ProviderFactory("image", "IMAGE_PROVIDER")
video_providers: ProviderFactory[BaseVideoProvider] = ProviderFactory("video", "VIDEO_PROVIDER")
voice_providers: ProviderFactory[BaseVoiceProvider] = ProviderFactory("voice", "VOICE_PROVIDER")
sfx_providers: ProviderFactory[BaseSfxProvider] = ProviderFactory("SFX", "SFX_PROVIDER")


def _load_project_env() -> None:
    """Make provider selection work from ``.env`` in a standalone Python process."""
    load_dotenv(Path.cwd() / ".env", override=False)


def _register_llm_adapters() -> None:
    """Register active LLM adapters (grok, gemini_flash)."""
    if "grok" not in llm_providers.registered_names:
        from .llm.grok import GrokLLMProvider

        llm_providers.register(
            "grok", GrokLLMProvider,
            required_env=("XAI_API_KEY",),
        )
    if "gemini_flash" not in llm_providers.registered_names:
        from .llm.gemini_flash import GeminiFlashProvider

        llm_providers.register(
            "gemini_flash", GeminiFlashProvider,
            required_env=("GEMINI_API_KEY", "GEMINI_MODEL"),
        )


def _register_voice_adapter(name: str) -> None:
    """Register active voice adapter (deepgram, voyslity, elevenlabs)."""
    selected = ProviderFactory._normalize(name)
    if selected == "deepgram" and selected not in voice_providers.registered_names:
        from .voice.deepgram_aura import DeepgramAuraProvider

        voice_providers.register(
            "deepgram", DeepgramAuraProvider,
            required_env=(
                "DEEPGRAM_API_KEY", "DEEPGRAM_BASE_URL", "DEEPGRAM_VOICE_MODEL",
                "DEEPGRAM_TRANSCRIBE_MODEL",
            ),
        )
    elif selected in {"voyslity", "elevenlabs", "eleven_labs", "eleven"} and selected not in voice_providers.registered_names:
        from .voice.voyslity_english import VoyslityEnglishVoiceProvider

        voice_providers.register(selected, VoyslityEnglishVoiceProvider)


def _register_image_adapter(name: str) -> None:
    """Register active image adapter (playwright_flow)."""
    selected = ProviderFactory._normalize(name)
    if selected in {"playwright_flow", "playwright_cdp", "flow"} and selected not in image_providers.registered_names:
        from .image.playwright_flow import PlaywrightFlowImageProvider

        image_providers.register(selected, PlaywrightFlowImageProvider)


def _register_video_adapter(name: str) -> None:
    """Register active video adapter (playwright_flow)."""
    selected = ProviderFactory._normalize(name)
    if selected in {"playwright_flow", "playwright_cdp", "flow"} and selected not in video_providers.registered_names:
        from .video.playwright_flow import PlaywrightFlowVideoProvider

        video_providers.register(selected, PlaywrightFlowVideoProvider)


def _register_sfx_adapter(name: str) -> None:
    """Register active SFX adapter (local_manifest, mmaudio, gradio_space, ffmpeg_lavfi)."""
    selected = ProviderFactory._normalize(name)
    if selected in {"local_manifest", "manifest"} and selected not in sfx_providers.registered_names:
        from .sfx.local_manifest import LocalManifestSfxProvider

        sfx_providers.register(selected, LocalManifestSfxProvider)
    elif selected == "mmaudio" and selected not in sfx_providers.registered_names:
        from .sfx.mmaudio import MMAudioProvider

        sfx_providers.register(selected, MMAudioProvider)
    elif selected in {"gradio_space", "space", "huggingface", "audiogen", "tangoflux"} and selected not in sfx_providers.registered_names:
        from .sfx.gradio_space import GradioSpaceSfxProvider

        sfx_providers.register(selected, GradioSpaceSfxProvider)
    elif selected in {"ffmpeg_lavfi", "lavfi", "synthetic"} and selected not in sfx_providers.registered_names:
        from .sfx.ffmpeg_lavfi import FFmpegLavfiSfxProvider

        sfx_providers.register(selected, FFmpegLavfiSfxProvider)


def get_llm_provider(name: str | None = None, **kwargs: Any) -> BaseLLMProvider:
    """Return the explicitly selected LLM adapter."""
    _load_project_env()
    _register_llm_adapters()
    return llm_providers.create(name, **kwargs)


def get_voice_provider(name: str | None = None, **kwargs: Any) -> BaseVoiceProvider:
    """Return the explicitly selected voice adapter."""
    _load_project_env()
    selected = name or os.getenv("VOICE_PROVIDER", "deepgram")
    if selected:
        _register_voice_adapter(selected)
    return voice_providers.create(name, **kwargs)


def get_image_provider(name: str | None = None, **kwargs: Any) -> BaseImageProvider:
    """Return the explicitly selected image adapter."""
    _load_project_env()
    selected = name or os.getenv("IMAGE_PROVIDER", "playwright_flow")
    if selected:
        _register_image_adapter(selected)
    return image_providers.create(name, **kwargs)


def get_video_provider(name: str | None = None, **kwargs: Any) -> BaseVideoProvider:
    """Return the explicitly selected video adapter."""
    _load_project_env()
    selected = name or os.getenv("VIDEO_PROVIDER", "playwright_flow")
    if selected:
        _register_video_adapter(selected)
    return video_providers.create(name, **kwargs)


def get_sfx_provider(name: str | None = None, **kwargs: Any) -> BaseSfxProvider:
    """Return the explicitly selected SFX catalogue."""
    _load_project_env()
    selected = name or os.getenv("SFX_PROVIDER", "local_manifest")
    if selected:
        _register_sfx_adapter(selected)
    return sfx_providers.create(name, **kwargs)
