"""YouTube upload metadata: written once per run from the script's `youtube` block.

The BeatEngine emits the metadata in the same tool call as the script, so it costs no
extra API request. If an old script.json lacks the block, a deterministic fallback is
derived from the topic so every run still ships a metadata.txt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generator import Script


def _fallback(topic: str, lang: str, mode: str = "anatomical") -> dict:
    title = topic.strip().rstrip(".!?")
    if title:
        title = title[0].upper() + title[1:]
    raw_words = [w.lower().strip(".,!?;:\"'") for w in topic.split()]
    stop_words = {
        "what", "when", "where", "which", "your", "this", "that", "from", "with",
        "does", "doesn't", "have", "been", "the", "who", "whom", "whose", "why",
        "how", "and", "or", "but", "out", "into", "got", "get", "will", "would",
        "could", "should", "than", "then", "them", "they", "their", "about",
    }
    meaningful = [w for w in raw_words if len(w) > 3 and w not in stop_words]
    tags: list[str] = []
    for w in meaningful:
        if len(w) > 2 and w not in tags:
            tags.append(w)

    import config
    is_doc = mode == "explorer" or getattr(config, "LONGFORM_MODE", False)
    if is_doc:
        from services.character import detect_era

        era = detect_era(topic)
        era_tags = {
            "world_war_i": ["world war i", "gallipoli campaign", "dardanelles", "military history", "ottoman history"],
            "ottoman": ["ottoman history", "istanbul history", "1453 constantinople", "historical reenactment"],
            "neolithic": ["ancient history", "archaeology", "prehistoric mystery", "neolithic"],
            "egyptian": ["ancient history", "egyptian history", "archaeology", "ancient mystery"],
            "greco_roman": ["ancient history", "roman history", "greek history", "archaeology"],
        }
        base_tags = ["historical documentary", "history", "time travel"] + era_tags.get(
            era, ["historical reenactment", "history documentary"]
        )
        for bt in base_tags:
            if bt not in tags:
                tags.append(bt)
        clean_title = re.sub(r"^(the\s+)?secrets\s+of\s+", "", title, flags=re.IGNORECASE).strip()
        if era == "world_war_i" and "gallipoli" in topic.casefold():
            event_title = "The 18 March 1915 Dardanelles Battle"
            legacy_title = "How Gallipoli's Naval Campaign Changed History"
        else:
            event_title = f"The Untold Story of {clean_title}"
            legacy_title = f"How {clean_title} Changed History"
        titles = [
            f"{title} — Historical Documentary",
            event_title,
            legacy_title,
        ]
        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in base_tags[:4])
        description = f"{title}. A historically grounded, cinematic documentary with researched period detail.\n\n{hashtags}"
    else:
        for bt in ["shorts", "science facts", "3d animation", "facts", "zackdfilms"]:
            if bt not in tags:
                tags.append(bt)
        titles = [
            f"{title}",
            f"The Truth Behind {title}",
            f"What Really Happens: {title}",
        ]
        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in ["shorts", "science", "facts"] + tags[:3])
        description = f"{title}. The surprising science and physical mechanism explained.\n\n{hashtags}"

    return {
        "titles": titles,
        "description": description,
        "tags": tags[:15],
    }


def _validate(meta: dict) -> dict:
    titles = [str(t).strip()[:100] for t in meta.get("titles", []) if str(t).strip()]
    tags: list[str] = []
    for t in meta.get("tags", []):
        t = re.sub(r"\s+", " ", str(t).strip().lower())
        if t and t not in tags:
            tags.append(t)
    return {
        "titles": titles[:3] or ["(no title generated)"],
        "description": str(meta.get("description", "")).strip(),
        "tags": tags[:15],
    }


def _apply_content_frame(meta: dict, content_type: str) -> dict:
    """Make upload metadata carry the same truth framing as the narration contract."""
    # A malformed structured-provider response may put a string/null in `youtube`.
    # Metadata is optional creative copy, never a reason to discard a valid video script.
    framed = dict(meta) if isinstance(meta, dict) else {}
    titles = list(framed.get("titles") or [])
    tags = list(framed.get("tags") or [])
    description = str(framed.get("description") or "").strip()
    if content_type == "folklore":
        titles = [t if "folklore" in t.lower() else f"{t} — Folklore Short" for t in titles]
        lead = "This short presents a documented folklore belief; it does not claim a supernatural event is factual."
        if not description.lower().startswith("this short presents a documented folklore"):
            description = f"{lead}\n\n{description}".strip()
        tags.extend(["folklore", "legend", "mythology"])
    elif content_type == "fiction":
        titles = [t if t.lower().startswith("fiction:") else f"Fiction: {t}" for t in titles]
        lead = "This is a fictional short story."
        if not description.lower().startswith("this is a fictional short story"):
            description = f"{lead}\n\n{description}".strip()
        tags.extend(["fiction", "shortstory"])
    framed["titles"] = titles
    framed["description"] = description
    framed["tags"] = tags
    return framed


def write_metadata(script: "Script", out_dir: Path) -> Path:
    """Write metadata.txt (paste-ready) and metadata.json (automation) into the run dir.

    Idempotent: metadata.txt is refreshed from script.json on every call, so a --resume
    after a script edit picks up the change.
    """
    raw_meta = getattr(script, "youtube", None)
    if not raw_meta and hasattr(script, "to_dict"):
        d = script.to_dict()
        if isinstance(d, dict):
            raw_meta = d.get("youtube")
    meta = _validate(_apply_content_frame(
        raw_meta or _fallback(script.topic, script.lang, getattr(script, "mode", "anatomical")),
        getattr(script, "content_type", "factual"),
    ))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    title_lines = []
    for i, t in enumerate(meta["titles"], 1):
        title_lines.append(f"  {i}. {t}")

    txt = (
        "YOUTUBE YUKLEME METADATASI\n"
        f"Konu: {script.topic}\n"
        f"Dil : {script.lang}\n"
        "\n"
        "BASLIK SECENEKLERI (birini sec):\n"
        + "\n".join(title_lines)
        + "\n\n"
        "ACIKLAMA:\n"
        f"{meta['description']}\n"
        "\n"
        "ETIKETLER (virgulle ayirarak yapistir):\n"
        + ", ".join(meta["tags"])
        + "\n"
    )
    txt_path = out_dir / "metadata.txt"
    txt_path.write_text(txt, encoding="utf-8")
    return txt_path
