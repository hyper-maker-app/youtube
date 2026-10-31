"""Voice provider factory exports and registration shim.

Provides unified access to voice provider factory registries:
- get_voice_provider(name, **kwargs)
- voice_providers (ProviderFactory instance)
- AzureNeuralVoiceProvider registration
"""

from __future__ import annotations

from typing import Any

try:
    from engine.providers.factory import (
        ProviderFactory,
        _register_voice_adapter,
        get_voice_provider,
        voice_providers,
    )
except ImportError:
    from providers.factory import (  # type: ignore[no-redef]
        ProviderFactory,
        _register_voice_adapter,
        get_voice_provider,
        voice_providers,
    )

# Ensure 'azure' is registered
_register_voice_adapter("azure")

__all__ = [
    "get_voice_provider",
    "voice_providers",
    "_register_voice_adapter",
]
