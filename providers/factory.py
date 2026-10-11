"""Explicit registry for provider adapter strategies.

The factory resolves one selected provider and never retries with, or substitutes,
another adapter. Concrete adapters are registered by the application bootstrap.
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
    """Register local LLM adapters lazily so importing the factory starts no SDK client."""
    if "vertex_gemini" not in llm_providers.registered_names:
        from .llm.vertex_gemini import VertexGeminiProvider

        llm_providers.register("vertex_gemini", VertexGeminiProvider)
    if "gemini_flash" not in llm_providers.registered_names:
        from .llm.gemini_flash import GeminiFlashProvider

        llm_providers.register(
            "gemini_flash", GeminiFlashProvider,
            required_env=("GEMINI_API_KEY", "GEMINI_MODEL"),
        )


def _register_voice_adapter(name: str) -> None:
    """Import only the selected voice adapter and therefore no unrelated SDK/config code."""
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


def _register_image_adapter(name: str) -> None:
    """Register only the selected image adapter without starting its remote bridge."""
    selected = ProviderFactory._normalize(name)
    if selected in {"flow_agent", "flow_agent_banana"} and selected not in image_providers.registered_names:
        from .image.flow_agent_banana import FlowAgentBananaProvider

        image_providers.register(selected, FlowAgentBananaProvider)
    elif selected == "nano_banana_pro" and selected not in image_providers.registered_names:
        from .image.nano_banana_pro import NanoBananaProProvider

        image_providers.register("nano_banana_pro", NanoBananaProProvider)
    elif selected in {"browser_flow", "flow_browser"} and selected not in image_providers.registered_names:
        from .image.browser_flow import BrowserFlowImageProvider

        image_providers.register(selected, BrowserFlowImageProvider)
    elif selected in {"playwright_flow", "playwright_cdp"} and selected not in image_providers.registered_names:
        from .image.playwright_flow import PlaywrightFlowImageProvider

        image_providers.register(selected, PlaywrightFlowImageProvider)


def _register_video_adapter(name: str) -> None:
    """Register one video strategy; concrete constructors validate their own OR-config."""
    selected = ProviderFactory._normalize(name)
    if selected == "vertex_veo" and selected not in video_providers.registered_names:
        from .video.vertex_veo import VertexVeoProvider

        video_providers.register("vertex_veo", VertexVeoProvider)
    elif selected == "flow_agent" and selected not in video_providers.registered_names:
        from .video.flow_agent_veo import FlowAgentVeoProvider

        video_providers.register("flow_agent", FlowAgentVeoProvider)
    elif selected in {"browser_flow", "flow_browser"} and selected not in video_providers.registered_names:
        from .video.browser_flow import BrowserFlowVideoProvider

        video_providers.register(selected, BrowserFlowVideoProvider)
    elif selected in {"playwright_flow", "playwright_cdp"} and selected not in video_providers.registered_names:
        from .video.playwright_flow import PlaywrightFlowVideoProvider

        video_providers.register(selected, PlaywrightFlowVideoProvider)
    elif selected in {"fal", "fal_video"} and selected not in video_providers.registered_names:
        from .video.fal_video import FalVideoProvider

        video_providers.register(selected, FalVideoProvider)
    elif selected in {"motion_engine", "local"} and selected not in video_providers.registered_names:
        from .video.motion_engine import MotionEngineProvider

        video_providers.register(selected, MotionEngineProvider)
    elif selected == "edge_tts" and selected not in voice_providers.registered_names:
        from .voice.edge_tts import EdgeTTSProvider

        voice_providers.register("edge_tts", EdgeTTSProvider, required_env=("EDGE_TTS_VOICE",))
    elif selected == "elevenlabs" and selected not in voice_providers.registered_names:
        from .voice.elevenlabs import ElevenLabsProvider

        voice_providers.register(
            "elevenlabs", ElevenLabsProvider,
            required_env=(
                "ELEVENLABS_API_KEY", "ELEVENLABS_BASE_URL", "ELEVENLABS_VOICE_ID",
                "ELEVENLABS_MODEL",
            ),
        )


def _register_sfx_adapter(name: str) -> None:
    """Register an explicitly selected, provenance-preserving SFX catalogue."""
    selected = ProviderFactory._normalize(name)
    if selected in {"local_manifest", "manifest"} and selected not in sfx_providers.registered_names:
        from .sfx.local_manifest import LocalManifestSfxProvider

        sfx_providers.register(selected, LocalManifestSfxProvider)
    elif selected in {"elevenlabs", "eleven_labs"} and selected not in sfx_providers.registered_names:
        from .sfx.elevenlabs import ElevenLabsSfxProvider

        sfx_providers.register(selected, ElevenLabsSfxProvider)
    elif selected == "mmaudio" and selected not in sfx_providers.registered_names:
        from .sfx.mmaudio import MMAudioProvider

        sfx_providers.register(selected, MMAudioProvider)


def get_llm_provider(name: str | None = None, **kwargs: Any) -> BaseLLMProvider:
    """Return the one explicitly selected LLM adapter from ``LLM_PROVIDER``."""
    _load_project_env()
    _register_llm_adapters()
    return llm_providers.create(name, **kwargs)


def get_voice_provider(name: str | None = None, **kwargs: Any) -> BaseVoiceProvider:
    """Return the one explicitly selected voice adapter from ``VOICE_PROVIDER``."""
    _load_project_env()
    selected = name or os.getenv("VOICE_PROVIDER", "")
    if selected:
        _register_voice_adapter(selected)
    return voice_providers.create(name, **kwargs)


def get_image_provider(name: str | None = None, **kwargs: Any) -> BaseImageProvider:
    """Return the one explicitly selected image adapter from ``IMAGE_PROVIDER``."""
    _load_project_env()
    selected = name or os.getenv("IMAGE_PROVIDER", "")
    if selected:
        _register_image_adapter(selected)
    return image_providers.create(name, **kwargs)


def get_video_provider(name: str | None = None, **kwargs: Any) -> BaseVideoProvider:
    """Return the one explicitly selected video adapter from ``VIDEO_PROVIDER``."""
    _load_project_env()
    selected = name or os.getenv("VIDEO_PROVIDER", "")
    if selected:
        _register_video_adapter(selected)
    return video_providers.create(name, **kwargs)


def get_sfx_provider(name: str | None = None, **kwargs: Any) -> BaseSfxProvider:
    """Return the explicitly selected SFX catalogue; never scrape or fall back."""
    _load_project_env()
    selected = name or os.getenv("SFX_PROVIDER", "")
    if selected:
        _register_sfx_adapter(selected)
    return sfx_providers.create(name, **kwargs)
