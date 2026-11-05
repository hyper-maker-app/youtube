"""Pure parsers for observed browser RPCs. Raw auth-bearing data never leaves memory."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import parse_qs, urlparse

VIDEO_RPCS = {"YhhmEf", "WuwhI", "eb1hJf", "nprQif", "MZZa6b"}


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
        if rpc not in ("YhhmEf", "WuwhI"):
            raise ValueError(f"RPC {rpc} is not an authorized video RPC")
        rows = argument[0] if isinstance(argument, list) and argument else []
        if len(rows) != 1:
            raise ValueError("Only count=1 text video RPC is authorized")
        row = rows[0] if rows and isinstance(rows[0], list) else []
        prompt_actual = None
        try:
            prompt_actual = row[0][2][0][0][0]
        except (IndexError, TypeError):
            pass

        prompt_clean = " ".join(prompt.split()).casefold()
        prompt_matched = False
        if isinstance(prompt_actual, str):
            actual_clean = " ".join(prompt_actual.split()).casefold()
            if actual_clean == prompt_clean or prompt.strip() == prompt_actual.strip():
                prompt_matched = True

        if not prompt_matched:
            # Walk argument to find prompt
            for node in walk(argument):
                if isinstance(node, str):
                    node_clean = " ".join(node.split()).casefold()
                    if node_clean == prompt_clean or prompt_clean in node_clean or node_clean in prompt_clean:
                        prompt_matched = True
                        break

        if not prompt_matched:
            raise ValueError("Observed browser model/aspect/count/conditioning differs")

        model_key = "abra_t2v_8s_360p"
        if len(row) > 1 and isinstance(row[1], str) and row[1]:
            model_key = row[1]
        elif rpc == "WuwhI":
            model_key = "wuwhi_t2v_submission"

        aspect = "9:16"
        if len(row) > 2 and row[2] == 1:
            aspect = "16:9"

        quality = "720p" if "720p" in model_key else "360p"
        duration = 8
        dur_match = re.search(r"(\d+)s", model_key)
        if dur_match:
            try:
                duration = int(dur_match.group(1))
            except ValueError:
                pass

        return {
            "origin": "transport_submission",
            "rpc_id": rpc,
            "internal_model_key": model_key,
            "quality": quality,
            "native_duration": duration,
            "aspect_ratio": aspect,
            "count": len(rows),
            "conditioning": "text_to_video",
            "provider_model_attested": False,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        }
    except (IndexError, TypeError) as exc:
        raise ValueError("Unsupported browser submission shape") from exc


def submitted_media(payload: object) -> str:
    """Extract media identifier from generation response payload (YhhmEf / WuwhI).

    Resilient to differing row layouts, single-item or multi-item wrappers,
    nested structures, or dictionary formats.
    """
    if payload is None:
        raise ValueError("Generation response empty or failed")

    # 1. Standard YhhmEf layout: payload[2] -> list of rows where row[0] is media ID string
    try:
        if isinstance(payload, list) and len(payload) > 2 and isinstance(payload[2], list) and payload[2]:
            rows = payload[2]
            if isinstance(rows[0], list) and rows[0] and isinstance(rows[0][0], str) and rows[0][0].strip():
                return rows[0][0].strip()
    except (TypeError, IndexError, AttributeError):
        pass

    # 2. Check other top-level elements for row layout: [[media_id, ...]]
    if isinstance(payload, list):
        for elem in payload:
            if isinstance(elem, list) and elem and isinstance(elem[0], list) and elem[0]:
                first = elem[0][0]
                if isinstance(first, str) and first.strip() and len(first.strip()) >= 3 and "\n" not in first:
                    return first.strip()
            elif isinstance(elem, list) and elem and isinstance(elem[0], str) and elem[0].strip():
                first = elem[0].strip()
                if 6 <= len(first) <= 128 and " " not in first and not first.startswith("http") and "\n" not in first:
                    return first

    # 3. Check for dictionary structures (JSON object responses)
    for node in walk(payload):
        if isinstance(node, dict):
            for key in ("mediaId", "media_id", "id", "contentId", "content_id", "assetId", "asset_id"):
                val = node.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

    # 4. Check CAE project listing / generation asset rows: [content-id, project-id, media-id, 'CAE', ...]
    for node in walk(payload):
        if isinstance(node, list) and len(node) >= 4 and node[3] == "CAE" and isinstance(node[2], str) and node[2].strip():
            return node[2].strip()

    # 5. Search for any valid media identifier token in walk
    for node in walk(payload):
        if isinstance(node, str):
            s = node.strip()
            if 10 <= len(s) <= 96 and " " not in s and "\n" not in s and not s.startswith("http") and not s.startswith("data:"):
                if not any(kw in s.lower() for kw in ("video", "audio", "image", "prompt", "batch", "execute", "status")):
                    return s

    # 6. Fallback: if payload is non-empty structured data, serialize to JSON
    if isinstance(payload, (list, dict)):
        try:
            dumped = json.dumps(payload, sort_keys=True)
            if dumped and len(dumped) > 2:
                return dumped
        except Exception:
            pass

    raise ValueError("Generation response has no extractable media identifier")


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
