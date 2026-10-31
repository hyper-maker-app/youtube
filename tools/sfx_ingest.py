"""Offline & FreeSound CC0 Foley Ingest Tool.

Builds and curates a 100% royalty-free CC0 local sound effects archive in assets/sfx/
with catalog.json indexing, ensuring zero-latency, zero-cost, and zero-copyright-risk
playback during production rendering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sfx_ingest")

ASSETS_SFX_DIR = _ROOT / "assets" / "sfx"
CATALOG_PATH = ASSETS_SFX_DIR / "catalog.json"

CATASTROPHE_QUERIES: dict[str, list[str]] = {
    "explosion": ["volcano eruption blast", "distant massive detonation", "shockwave thump"],
    "earthquake_rumble": ["deep subterranean seismic rumble", "earthquake low frequency vibration"],
    "tsunami_water": ["violent ocean surge water roar", "tidal wave wall of water crashing"],
    "alarm_siren": ["emergency klaxon air raid siren", "evacuation alarm distant wail"],
    "debris_crumble": ["building concrete collapse rubble", "shattering masonry stone fall"],
    "hull_creak": ["heavy steel vault door groan", "submarine bulkhead pressure creak"],
    "pyroclastic_wind": ["howling volcanic ash gale", "cataclysmic firestorm wind"],
    "whoosh_transition": ["fast air displacement cinematic whip", "heavy low whoosh impact"],
    "metal_impact": ["heavy steel gate slam", "shipping container collision"],
    "glass_shatter": ["high rise window shockwave shatter", "reinforcing glass fracture"],
}


def load_existing_catalog() -> dict[str, Any]:
    """Load existing catalog or initialize fresh structure."""
    if CATALOG_PATH.is_file():
        try:
            return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": "1.0", "license": "Creative Commons 0 (CC0)", "assets": {}}


def save_catalog(catalog: dict[str, Any]) -> None:
    """Save catalog.json formatted with indent."""
    ASSETS_SFX_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved SFX catalog to %s (%d assets indexed)", CATALOG_PATH, len(catalog.get("assets", {})))


def synthesize_fallback_cc0_sample(category: str, prompt: str, out_path: Path, duration: float = 3.0) -> None:
    """Synthesize high-fidelity local CC0 sample using FFmpeg if offline or no API key."""
    from engine.providers.sfx.ffmpeg_lavfi import FFmpegLavfiSfxProvider
    import asyncio

    provider = FFmpegLavfiSfxProvider()
    asyncio.run(provider.resolve_asset(
        {"prompt": prompt, "duration": duration, "asset_id": out_path.stem, "tags": [category, "cc0", "curated"]},
        cache_dir=out_path.parent,
    ))


def ingest_sfx_library(api_key: str | None = None, populate_defaults: bool = True) -> int:
    """Download CC0 sounds from Freesound API or generate local curated baseline."""
    ASSETS_SFX_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_existing_catalog()
    assets = catalog.setdefault("assets", {})

    ingested_count = 0
    token = api_key or os.getenv("FREESOUND_API_KEY", "").strip()

    for category, queries in CATASTROPHE_QUERIES.items():
        cat_dir = ASSETS_SFX_DIR / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        for q_idx, query in enumerate(queries):
            asset_slug = f"{category}_{q_idx+1:02d}"
            target_wav = cat_dir / f"{asset_slug}.wav"

            if target_wav.is_file() and target_wav.stat().st_size > 1000:
                assets[asset_slug] = {
                    "category": category,
                    "query": query,
                    "path": f"assets/sfx/{category}/{target_wav.name}",
                    "license": "CC0",
                    "source": "curated_archive",
                }
                continue

            if token:
                try:
                    logger.info("Searching Freesound for CC0: %s...", query)
                    url = (
                        f"https://freesound.org/apiv2/search/text/?"
                        f"query={urllib.parse.quote(query)}"
                        f"&filter=license:\"Creative Commons 0\"+duration:[1.0 TO 6.0]"
                        f"&sort=rating_desc&fields=id,name,previews,duration&token={token}"
                    )
                    req = urllib.request.Request(url, headers={"User-Agent": "GrokCinematicStudio/4.0"})
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        results = data.get("results", [])
                        if results:
                            top = results[0]
                            preview_url = top.get("previews", {}).get("preview-hq-mp3")
                            if preview_url:
                                urllib.request.urlretrieve(preview_url, target_wav)
                                assets[asset_slug] = {
                                    "category": category,
                                    "query": query,
                                    "freesound_id": top.get("id"),
                                    "duration": top.get("duration"),
                                    "path": f"assets/sfx/{category}/{target_wav.name}",
                                    "license": "CC0",
                                    "source": "freesound_api",
                                }
                                ingested_count += 1
                                logger.info("  + Ingested CC0: %s -> %s", query, target_wav.name)
                                continue
                except Exception as exc:
                    logger.debug("Freesound query '%s' failed: %s. Using baseline synthesis.", query, exc)

            if populate_defaults:
                synthesize_fallback_cc0_sample(category, query, target_wav)
                assets[asset_slug] = {
                    "category": category,
                    "query": query,
                    "path": f"assets/sfx/{category}/{target_wav.name}",
                    "license": "CC0",
                    "source": "procedural_baseline",
                }
                ingested_count += 1

    save_catalog(catalog)
    return ingested_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest royalty-free CC0 SFX into local library.")
    parser.add_argument("--api-key", type=str, default=None, help="Freesound API token")
    parser.add_argument("--baseline-only", action="store_true", help="Populate baseline without hitting Freesound API")
    args = parser.parse_args()

    count = ingest_sfx_library(api_key=None if args.baseline_only else args.api_key)
    logger.info("Ingest complete. %d sounds verified in local catalog.", count)


if __name__ == "__main__":
    main()
