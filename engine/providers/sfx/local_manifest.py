"""A local, auditable SFX catalogue adapter.

It deliberately cannot crawl/search the web.  Assets enter its manifest through a
trusted catalogue integration or a human-approved ingest step, each with explicit
licensing metadata.  Resolution is deterministic and verifies the cached bytes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from providers.base import BaseSfxProvider, ConfigurationError, ProviderError
from services.sfx import SfxManifestResolver


class LocalManifestSfxProvider(BaseSfxProvider):
    """Resolve existing verified files from ``SFX_MANIFEST_PATH`` only."""

    def __init__(self, manifest_path: Path | None = None) -> None:
        configured = manifest_path or os.getenv("SFX_MANIFEST_PATH")
        if not configured:
            raise ConfigurationError("local_manifest SFX provider requires SFX_MANIFEST_PATH.")
        self.manifest_path = Path(configured)

    async def resolve_asset(self, query: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
        # cache_dir is part of the provider contract for remote adapters.  This
        # adapter is intentionally local-only and does not create network side effects.
        _ = cache_dir
        resolver = SfxManifestResolver(self.manifest_path)
        tags = query.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ProviderError("SFX query requires a list of semantic string tags.")
        asset = resolver.resolve(tags, asset_id=query.get("asset_id"))
        return asset.to_dict()
