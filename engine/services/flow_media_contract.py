"""Validate measured transport media without creating a provider."""
from __future__ import annotations

import math
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess

EVIDENCE_SCHEMA_VERSION = 2
PINNED_SOURCE_REVISION = "70ec73861091267dd1f57184bcf809a922bea85b"


def probe_media(path: Path, executable: str | None = None) -> dict:
    """Read stream evidence, including SAR/DAR. Never infer it from the request."""
    binary = executable or shutil.which("ffprobe")
    if not binary:
        raise ValueError("ffprobe is required for Flow media evidence; repair the probe dependency")
    result = subprocess.run([binary, "-v", "error", "-show_streams", "-show_format",
                             "-of", "json", str(path)], capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError("Flow media probe failed")
    return json.loads(result.stdout)


def validate_catalog(entry: dict, wire_key: str) -> dict:
    catalog = entry.get("catalog_evidence", {})
    if (catalog.get("rpc_id") != "HTrJv" or catalog.get("http_status") != 200
            or catalog.get("display_name") != entry.get("display_name")
            or wire_key not in catalog.get("internal_model_keys", [])
            or not catalog.get("observed_at")):
        raise ValueError("Flow catalog family/key evidence missing or mismatched")
    return {"origin": "catalog", "canonical_alias": entry["alias"],
            **{key: catalog[key] for key in ("display_name", "rpc_id", "observed_at", "record_path")},
            "wire_key": wire_key}


def normalize_video_outcome(response: dict, *, request: dict, catalog: dict,
                            invocation_root: Path, launched_at: float,
                            source_revision: str, probe=None) -> tuple[Path, dict]:
    """Normalize the pinned BatchVideoOutcome; stdout is NOT provider attestation.

    engine.go:GenerateVideoViaBatch uses the SAME local model/quality variables in
    GenerateVideoRequest and BatchVideoOutcome (lines 3550-3564 and 3635-3643).
    collectVideo creates Files from this outcome's MediaIDs. The CLI prints this
    outcome directly. Require a fresh private output directory for each invocation.
    """
    if source_revision != PINNED_SOURCE_REVISION:
        raise ValueError("Unreviewed Flow source revision; explicit repair required")
    expected_key = request["transport_request_model_key"]
    if response.get("model") != expected_key or response.get("quality") != request["quality"]:
        raise ValueError("Flow transport model/quality missing or mismatched")
    family = validate_catalog(catalog, response["model"])
    files, media_ids = response.get("files"), response.get("media_ids")
    job_id = response.get("job_id")
    if (response.get("status") != "ready" or not isinstance(job_id, str) or not job_id
            or not isinstance(files, list) or len(files) != 1
            or not isinstance(media_ids, list) or len(media_ids) != 1):
        raise ValueError("Flow invocation has no single ready job/media result")
    item = files[0]
    if not isinstance(item, dict) or item.get("media_id") != media_ids[0] or not media_ids[0]:
        raise ValueError("Flow output belongs to another media/job")
    root = invocation_root.resolve()
    path = Path(item.get("path") or "")
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if (not path.is_relative_to(root) or not path.is_file()
            or path.stat().st_mtime < launched_at
            or path.stat().st_size <= 0 or item.get("bytes") != path.stat().st_size):
        raise ValueError("Flow output missing, stale or outside invocation directory")
    measured = (probe or probe_media)(path)
    streams = measured.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    if len(videos) != 1:
        raise ValueError("Flow output must contain exactly one video stream")
    video = videos[0]
    try:
        sar = Fraction(video["sample_aspect_ratio"].replace(":", "/"))
        dar = Fraction(video["width"], video["height"]) * sar
        if sar != 1 or dar != Fraction(request["aspect_ratio"].replace(":", "/")):
            raise ValueError("Flow measured SAR/aspect differs")
        reported_dar = video.get("display_aspect_ratio")
        if reported_dar and Fraction(reported_dar.replace(":", "/")) != dar:
            raise ValueError("Flow measured DAR is inconsistent")
        duration = float(video.get("duration", measured.get("format", {}).get("duration", 0)))
        from types import SimpleNamespace
        validate_video_geometry(SimpleNamespace(width=video["width"], height=video["height"], duration=duration),
                                quality=request["quality"], aspect_ratio=request["aspect_ratio"],
                                minimum_duration=request["duration"])
    except (KeyError, ZeroDivisionError, TypeError) as exc:
        raise ValueError("Flow media probe evidence incomplete") from exc
    # Whitelist only. Never persist raw stdout, signed URLs or account/project IDs.
    evidence = {"schema_version": EVIDENCE_SCHEMA_VERSION, "publishable": False,
                "expected": {"origin": "request", **{key: request[key] for key in
                    ("quality", "aspect_ratio", "duration", "transport_request_model_key", "execution_mode")}},
                "transport": {"origin": "transport_submission", "internal_model_key": response["model"],
                              "quality": response["quality"], "status": "ready",
                              "provider_model_attested": False,
                              "job_sha256": hashlib.sha256(job_id.encode()).hexdigest(),
                              "media_sha256": hashlib.sha256(str(media_ids[0]).encode()).hexdigest()},
                "catalog": family,
                "measured": {"origin": "media_probe", "asset_type": "video",
                             "width": video["width"], "height": video["height"],
                             "quality": f"{min(video['width'], video['height'])}p",
                             "aspect_ratio": f"{dar.numerator}:{dar.denominator}",
                             "sample_aspect_ratio": str(sar), "duration": duration,
                             "has_audio": any(s.get("codec_type") == "audio" for s in streams)}}
    return path, evidence


def validate_video_geometry(info, *, quality: str, aspect_ratio: str, minimum_duration: float) -> None:
    short_edge = {"360p": 360, "720p": 720}.get(quality)
    dimensions = (short_edge, round(short_edge * 16 / 9)) if short_edge else None
    expected = dimensions if aspect_ratio == "9:16" else tuple(reversed(dimensions)) if dimensions else None
    if aspect_ratio not in ("9:16", "16:9") or not expected or (info.width, info.height) != expected:
        raise ValueError("Provider output geometry differs from locked native quality/aspect")
    duration = float(info.duration or 0)
    if not math.isfinite(duration) or duration + 1/30 < minimum_duration:
        raise ValueError("Provider output is shorter than locked duration")
    if duration > minimum_duration + 1/30:
        raise ValueError("Provider output duration differs from locked native duration")


def validate_response_identity(response: dict, *, model_key: str, quality: str,
                               duration: int, aspect_ratio: str) -> None:
    """Missing response evidence is not success and cannot be inferred from a request."""
    expected = {"internal_model_key": model_key, "quality": quality,
                "duration": duration, "aspect_ratio": aspect_ratio, "asset_type": "video"}
    for name, value in expected.items():
        if response.get(name) != value:
            raise ValueError(f"Flow response {name} missing or mismatched; output rejected")
