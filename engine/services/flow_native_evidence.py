"""Pure parsers for observed browser RPCs. Raw auth-bearing data never leaves memory."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qs, urlparse

VIDEO_RPCS = {"YhhmEf", "eb1hJf", "nprQif", "MZZa6b"}


def walk(value):
    yield value
    if isinstance(value, list):
        for child in value:
            yield from walk(child)


def rpc_requests(body: str) -> list[tuple[str, object]]:
    encoded = parse_qs(body).get("f.req", [])
    if len(encoded) != 1:
        raise ValueError("Missing browser RPC envelope")
    result = []
    for row in walk(json.loads(encoded[0])):
        if isinstance(row, list) and len(row) >= 2 and isinstance(row[0], str) and isinstance(row[1], str):
            try:
                result.append((row[0], json.loads(row[1])))
            except ValueError:
                pass
    return result


def rpc_responses(raw: str) -> list[tuple[str, object]]:
    result = []
    for line in raw.splitlines():
        if not line.startswith("["):
            continue
        try:
            decoded = json.loads(line)
        except ValueError:
            continue
        for row in walk(decoded):
            if isinstance(row, list) and len(row) >= 3 and row[0] == "wrb.fr" and isinstance(row[2], str):
                try:
                    result.append((row[1], json.loads(row[2])))
                except ValueError:
                    pass
    return result


def validate_text_submission(rpc: str, argument: object, prompt: str) -> dict:
    """Layout reviewed against pinned buildVideoArgument; browser observation is authority."""
    try:
        rows = argument[0]
        if rpc != "YhhmEf" or len(rows) != 1:
            raise ValueError("Only count=1 text video RPC is authorized")
        row = rows[0]
        prompt_actual = row[0][2][0][0][0]
        if not isinstance(prompt_actual, str) or (
            prompt_actual.strip() != prompt.strip()
            and " ".join(prompt_actual.split()) != " ".join(prompt.split())
        ) or row[1] != "abra_t2v_8s_360p" or row[2] not in (1, 2) or row[3] != 1:
            raise ValueError("Observed browser model/aspect/count/conditioning differs")
        aspect = "16:9" if row[2] == 1 else "9:16"
        return {"origin": "transport_submission", "rpc_id": rpc,
                "internal_model_key": row[1], "quality": "360p", "native_duration": 8,
                "aspect_ratio": aspect, "count": len(rows), "conditioning": "text_to_video",
                "provider_model_attested": False,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    except (IndexError, TypeError) as exc:
        raise ValueError("Unsupported browser submission shape") from exc


def submitted_media(payload: object) -> str:
    try:
        rows = payload[2]
        if len(rows) != 1 or not isinstance(rows[0][0], str) or not rows[0][0]:
            raise ValueError("Generation response has no single media result")
        return rows[0][0]
    except (TypeError, IndexError) as exc:
        raise ValueError("Generation response empty or failed") from exc


def original_assets(payload: object) -> dict[str, str]:
    """Project listing rows: content-id, project-id, media-id, original type CAE."""
    assets = {}
    for row in walk(payload):
        if (isinstance(row, list) and len(row) >= 6 and row[3] == "CAE"
                and isinstance(row[0], str) and isinstance(row[2], str)):
            assets[row[2]] = row[0]
    return assets


def matching_video_url(payload: object, content_id: str) -> str | None:
    urls = set()
    for value in walk(payload):
        if isinstance(value, str):
            url = urlparse(value)
            if url.scheme == "https" and url.hostname == "flow-content.google" and url.path == f"/video/{content_id}":
                urls.add(value)
    if len(urls) > 1:
        raise ValueError("Ambiguous content URLs")
    return next(iter(urls), None)
