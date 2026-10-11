"""Voice provider adapters."""

__all__ = ["DeepgramAuraProvider", "EdgeTTSProvider", "ElevenLabsProvider"]


def __getattr__(name: str):
    """Avoid importing unrelated SDK/config dependencies for the selected adapter."""
    if name == "DeepgramAuraProvider":
        from .deepgram_aura import DeepgramAuraProvider

        return DeepgramAuraProvider
    if name == "EdgeTTSProvider":
        from .edge_tts import EdgeTTSProvider

        return EdgeTTSProvider
    if name == "ElevenLabsProvider":
        from .elevenlabs import ElevenLabsProvider

        return ElevenLabsProvider
    raise AttributeError(name)
