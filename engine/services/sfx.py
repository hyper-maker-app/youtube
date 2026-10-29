"""Auditable SFX asset admission, cue validation, and run artefact helpers.

No code in this module discovers public-web files.  It only accepts assets whose
source, licence, attribution requirement, and cached byte hash are all known.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


class SfxValidationError(ValueError):
    """An SFX asset or cue failed the release-safe contract."""


_ACCEPTED_LICENSES = {"CC0-1.0", "CC-BY-4.0", "CC-BY-3.0"}


def _atomic_write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_asset_payload(payload: dict[str, Any], *, require_file: bool) -> None:
    required = ("asset_id", "source_url", "creator", "license", "license_url", "commercial_allowed", "sha256", "local_path", "tags")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise SfxValidationError(f"SFX asset missing required provenance: {', '.join(missing)}")
    licence = str(payload["license"]).upper()
    if licence not in _ACCEPTED_LICENSES:
        raise SfxValidationError(f"SFX asset '{payload['asset_id']}' has unsupported licence '{payload['license']}'.")
    if payload["commercial_allowed"] is not True:
        raise SfxValidationError("SFX asset must explicitly allow commercial use.")
    if not str(payload["source_url"]).startswith(("https://", "http://")):
        raise SfxValidationError("SFX asset source_url must be an explicit HTTP(S) source.")
    if not str(payload["license_url"]).startswith(("https://", "http://")):
        raise SfxValidationError("SFX asset license_url must be an explicit HTTP(S) URL.")
    if not isinstance(payload["tags"], list) or not payload["tags"] or not all(isinstance(tag, str) and tag.strip() for tag in payload["tags"]):
        raise SfxValidationError("SFX asset requires non-empty semantic tags.")
    if licence.startswith("CC-BY") and not str(payload.get("attribution", "")).strip():
        raise SfxValidationError("CC-BY SFX asset requires an attribution string.")
    if require_file:
        asset_path = Path(str(payload["local_path"]))
        if not asset_path.is_file():
            root_relative = Path(__file__).resolve().parents[1] / asset_path
            if root_relative.is_file():
                asset_path = root_relative
                payload["local_path"] = str(root_relative)
            else:
                raise SfxValidationError(f"SFX asset file is missing: {asset_path}")
        if _sha256(asset_path) != str(payload["sha256"]).lower():
            raise SfxValidationError(f"SFX asset hash does not match manifest: {payload['asset_id']}")


@dataclass(frozen=True)
class SfxAsset:
    asset_id: str
    local_path: str
    sha256: str
    source_url: str
    creator: str
    license: str
    license_url: str
    commercial_allowed: bool
    attribution: str
    tags: list[str]
    duration: float | None = None
    lufs: float | None = None
    peak: float | None = None
    downloaded_at: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, require_file: bool = True) -> "SfxAsset":
        _validate_asset_payload(payload, require_file=require_file)
        return cls(**{field: payload.get(field) for field in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


class SfxManifestResolver:
    """Read and resolve a central cache manifest without any web discovery."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = Path(manifest_path)

    def assets(self) -> list[SfxAsset]:
        if not self.manifest_path.is_file():
            raise SfxValidationError(f"SFX manifest is missing: {self.manifest_path}")
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SfxValidationError(f"SFX manifest is invalid JSON: {self.manifest_path}") from exc
        records = payload.get("assets") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise SfxValidationError("SFX manifest must contain an 'assets' list.")
        if not all(isinstance(record, dict) for record in records):
            raise SfxValidationError("Every SFX manifest asset must be an object.")
        return [SfxAsset.from_dict(record) for record in records]

    def resolve(self, tags: Iterable[str], asset_id: str | None = None) -> SfxAsset:
        requested = {tag.strip().casefold() for tag in tags if tag.strip()}
        if not requested and not asset_id:
            raise SfxValidationError("SFX resolution needs asset_id or at least one semantic tag.")
        candidates = self.assets()
        if asset_id:
            for asset in candidates:
                if asset.asset_id == asset_id:
                    return asset
            raise SfxValidationError(f"Requested SFX asset is not in the verified manifest: {asset_id}")
        ranked = sorted(
            ((len(requested & {tag.casefold() for tag in asset.tags}), asset.asset_id, asset) for asset in candidates),
            key=lambda item: (-item[0], item[1]),
        )
        if not ranked or ranked[0][0] == 0:
            raise SfxValidationError("No verified SFX asset matches the requested semantic tags.")
        return ranked[0][2]


def validate_cue_sheet(cues: Iterable[dict[str, Any]], assets: Iterable[dict[str, Any] | SfxAsset]) -> list[dict[str, Any]]:
    """Validate bounded, event-linked cues against verified cached assets."""
    indexed = {
        asset.asset_id if isinstance(asset, SfxAsset) else SfxAsset.from_dict(asset).asset_id:
        asset if isinstance(asset, SfxAsset) else SfxAsset.from_dict(asset)
        for asset in assets
    }
    normalized: list[dict[str, Any]] = []
    per_block: dict[int, int] = {}
    for cue in cues:
        required = ("cue_id", "block", "start", "end", "reason", "asset_id", "gain_db", "fade_in", "fade_out")
        missing = [key for key in required if key not in cue or cue[key] in (None, "")]
        if missing:
            raise SfxValidationError(f"SFX cue missing fields: {', '.join(missing)}")
        block = cue["block"]
        if not isinstance(block, int) or block < 1:
            raise SfxValidationError("SFX cue block must be a positive integer.")
        if not (isinstance(cue["start"], (int, float)) and isinstance(cue["end"], (int, float)) and cue["end"] > cue["start"] >= 0):
            raise SfxValidationError("SFX cue requires a non-negative half-open start/end interval.")
        if cue["asset_id"] not in indexed:
            raise SfxValidationError(f"SFX cue references unverified asset: {cue['asset_id']}")
        reason = str(cue["reason"]).strip()
        if len(reason) < 8 or "caption" in reason.casefold():
            raise SfxValidationError("SFX cue reason must describe a visible physical event, not caption emphasis.")
        per_block[block] = per_block.get(block, 0) + 1
        if per_block[block] > 2:
            raise SfxValidationError(f"SFX block {block} has more than two cues.")
        normalized.append(dict(cue))
    return normalized


def write_sfx_cue_sheet(run_dir: Path, cues: Iterable[dict[str, Any]], assets: Iterable[dict[str, Any] | SfxAsset]) -> Path:
    """Persist a validated run-local cue sheet and its asset provenance snapshot."""
    asset_records = [asset.to_dict() if isinstance(asset, SfxAsset) else SfxAsset.from_dict(asset).to_dict() for asset in assets]
    normalized = validate_cue_sheet(list(cues), asset_records)
    return _atomic_write_json(Path(run_dir) / "sfx_cue_sheet.json", {"schema_version": 1, "cues": normalized, "assets": asset_records})


def write_attributions(run_dir: Path, assets: Iterable[dict[str, Any] | SfxAsset]) -> Path:
    """Write only the CC-BY attributions actually used in this final run."""
    records = [asset if isinstance(asset, SfxAsset) else SfxAsset.from_dict(asset) for asset in assets]
    by_asset = {asset.asset_id: asset for asset in records if asset.license.upper().startswith("CC-BY")}
    lines = ["Sound effect attributions", ""]
    for asset_id in sorted(by_asset):
        asset = by_asset[asset_id]
        lines.append(f"{asset.asset_id}: {asset.attribution} ({asset.license})")
        lines.append(f"Source: {asset.source_url}")
        lines.append(f"Licence: {asset.license_url}")
        lines.append("")
    path = Path(run_dir) / "ATTRIBUTIONS.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def detect_peak_transient(wav_path: Path | str) -> float:
    """Find timestamp in seconds of maximum absolute sample amplitude in a WAV file."""
    try:
        import struct
        import wave
        path = Path(wav_path)
        if not path.is_file():
            return 0.0
        with wave.open(str(path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            if n_frames <= 0 or framerate <= 0:
                return 0.0
            max_frames = min(n_frames, framerate * 2)
            raw = wf.readframes(max_frames)
            if sampwidth == 2:
                count = len(raw) // 2
                samples = struct.unpack(f"<{count}h", raw)
                max_val = 0
                max_frame = 0
                for i in range(0, count, n_channels):
                    val = abs(samples[i])
                    if val > max_val:
                        max_val = val
                        max_frame = i // n_channels
                return round(max_frame / framerate, 3)
    except Exception:
        pass
    return 0.0


from services.sfx_dictionary import get_tactile_sfx_tags, translate_to_tactile_foley

__all__ = [
    "SfxAsset",
    "SfxManifestResolver",
    "SfxValidationError",
    "detect_peak_transient",
    "get_tactile_sfx_tags",
    "translate_to_tactile_foley",
    "validate_cue_sheet",
    "write_attributions",
    "write_sfx_cue_sheet",
]

