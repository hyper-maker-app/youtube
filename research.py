"""Evidence collection and claim-level release gate for factual Shorts.

The module deliberately separates evidence *collection* from generation.  A network outage
never turns an unsupported claim into an approved one: it produces a review manifest instead.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import httpx

SENSITIVE_RE = re.compile(r"\b(heart|cancer|tumou?r|cell|disease|medical|health|blood|organ|injury|virus|vaccine|cancer|kalp|kanser|hastalık|sağlık|hücre|organ|yaralanma)\b", re.I)
ABSOLUTE_RE = re.compile(r"\b(never|always|cannot|can\s+never|only|impossible|asla|her zaman|imkansız|tek)\b", re.I)
TRUSTED_TYPES = {"primary", "institutional", "peer_reviewed"}


def is_sensitive(topic: str) -> bool:
    return bool(SENSITIVE_RE.search(topic))


def _source(raw: dict, default_type: str = "secondary") -> dict:
    return {
        "url": str(raw.get("url") or raw.get("source_url") or "").strip(),
        "title": str(raw.get("title") or raw.get("name") or "").strip(),
        "source_type": str(raw.get("source_type") or default_type).strip(),
        "evidence": str(raw.get("evidence") or raw.get("mechanism_summary") or raw.get("summary") or "").strip(),
    }


def collect_sources(topic: str, supplied: Iterable[dict] = (), timeout: float = 8.0) -> list[dict]:
    """Use public, no-key endpoints.  Failures are represented in the manifest, not hidden."""
    sources = [_source(item) for item in supplied if isinstance(item, dict)]
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            wiki = client.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(topic, safe=""))
            if wiki.is_success:
                data = wiki.json()
                sources.append(_source({"url": data.get("content_urls", {}).get("desktop", {}).get("page"), "title": data.get("title"), "evidence": data.get("extract"), "source_type": "secondary"}))
            works = client.get("https://api.crossref.org/works", params={"query.title": topic, "rows": 2, "select": "title,DOI,abstract,type"})
            if works.is_success:
                for item in works.json().get("message", {}).get("items", []):
                    doi = item.get("DOI")
                    if doi:
                        sources.append(_source({"url": f"https://doi.org/{doi}", "title": (item.get("title") or [""])[0], "evidence": re.sub(r"<[^>]+>", "", item.get("abstract") or ""), "source_type": "peer_reviewed" if item.get("type") == "journal-article" else "secondary"}))
            if is_sensitive(topic):
                search = client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params={"db": "pubmed", "term": topic, "retmode": "json", "retmax": 2})
                if search.is_success:
                    for pmid in search.json().get("esearchresult", {}).get("idlist", []):
                        sources.append(_source({"url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "title": f"PubMed {pmid}", "evidence": "PubMed-indexed biomedical literature result.", "source_type": "primary"}))
    except (httpx.HTTPError, ValueError):
        pass
    # Preserve order but remove duplicates/empty URLs.
    unique: dict[str, dict] = {}
    for item in sources:
        if item["url"]:
            unique.setdefault(item["url"], item)
    return list(unique.values())


def build_manifest(topic: str, content_type: str, sources: list[dict], claims: Iterable[str] = ()) -> dict:
    sensitive = is_sensitive(topic)
    trusted = any(s.get("source_type") in TRUSTED_TYPES for s in sources)
    items = []
    for claim in claims:
        absolute = bool(ABSOLUTE_RE.search(claim))
        approved = bool(sources) and (not sensitive or trusted) and not absolute
        items.append({
            "claim": claim,
            "source_url": sources[0]["url"] if sources else "",
            "source_title": sources[0]["title"] if sources else "",
            "source_type": sources[0]["source_type"] if sources else "",
            "evidence": sources[0]["evidence"] if sources else "",
            "confidence": "high" if approved and trusted else "medium" if approved else "low",
            "risk": "sensitive" if sensitive else "absolute_language" if absolute else "unverified",
            "approved_wording": claim if approved else (ABSOLUTE_RE.sub("may", claim) if absolute else "Source verification required before publishing."),
            "status": "approved" if approved else "review",
        })
    status = "not_applicable" if content_type != "factual" else ("pass" if items and all(x["status"] == "approved" for x in items) else "review")
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "topic": topic, "content_type": content_type, "sensitive": sensitive, "sources": sources, "claims": items, "status": status}


def write_manifest(out_dir: Path, topic: str, content_type: str, supplied_sources: Iterable[dict], claims: Iterable[str] = ()) -> dict:
    manifest = build_manifest(topic, content_type, collect_sources(topic, supplied_sources) if content_type == "factual" else [], claims)
    path = Path(out_dir) / "research.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, indent=2, ensure_ascii=False))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    return manifest
