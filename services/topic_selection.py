"""Deterministic, provider-neutral autonomous topic selection.

Live research may be injected by an outer adapter in a future run.  This service itself
does not perform network I/O: when no verified live signal is supplied it records that
fact and chooses from a cited evergreen pool rather than inventing a trend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import run_history


COMPLETED_EXCLUDES = {
    "why-artemis-iii-launches-on-40-year-old-rocket-e_20260902_133520",
    "your-bones-are-secretly-liquid-metal-factories_20260831_003233",
    "why-your-heart-never-gets-cancer_20260828_144657",
}


@dataclass(frozen=True)
class TopicCandidate:
    topic: str
    source_urls: tuple[str, ...]
    freshness: int
    curiosity: int
    visual_story: int
    factual_quality: int
    zack_visual: int
    provider_safe: int
    rationale: str


EVERGREEN_CANDIDATES = (
    TopicCandidate("Why does glass shatter into tiny cubes?", ("https://www.nist.gov/pml",), 5, 9, 9, 8, 9, 10, "Tempered-glass stress can be shown as one clear 3D causal chain."),
    TopicCandidate("Why can a bridge cable hold so much weight?", ("https://www.fhwa.dot.gov/bridge/",), 5, 8, 9, 9, 9, 10, "Tension, sag, and load transfer are visually causal without speculative claims."),
    TopicCandidate("How does a solar panel turn light into electricity?", ("https://science.nasa.gov/solar-system/",), 6, 8, 9, 9, 9, 10, "A photon-to-current journey offers an eight-shot scale-aware visualization."),
    TopicCandidate("Why do lightning rods protect buildings?", ("https://www.weather.gov/safety/lightning",), 7, 9, 8, 9, 9, 10, "Charge concentration and a controlled path to ground make a strong physical payoff."),
)


def _completed_topics(history_path: Path) -> set[str]:
    completed = set(COMPLETED_EXCLUDES)
    connection = run_history.connect(history_path)
    try:
        rows = connection.execute("SELECT topic, status FROM runs WHERE lower(status) IN ('completed', 'published', 'publishable')").fetchall()
    finally:
        connection.close()
    completed.update(run_history.topic_key(str(topic)) for topic, _ in rows)
    return completed


def select_topic(history_path: Path, *, live_candidates: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Score candidates and return provenance suitable for ``topic_selection.json``.

    A caller may provide only already-verified live candidates.  Empty/unavailable live
    data is made explicit and never receives a fabricated momentum score.
    """
    completed = _completed_topics(history_path)
    supplied = list(live_candidates or [])
    source = "live_verified" if supplied else "evergreen_fallback"
    candidates: list[dict[str, Any]] = []
    for item in EVERGREEN_CANDIDATES:
        duplicate = run_history.topic_key(item.topic) in completed
        scores = {"freshness_or_momentum": item.freshness, "first_second_curiosity": item.curiosity, "eight_shot_causal_fit": item.visual_story, "factual_source_quality": item.factual_quality, "zack_3d_potential": item.zack_visual, "provider_safety": item.provider_safe, "originality": 0 if duplicate else 10}
        total = sum(scores.values())
        candidates.append({"topic": item.topic, "scores": scores, "total": total, "source_urls": list(item.source_urls), "selected": False, "reason": "duplicate completed/publishable run" if duplicate else item.rationale})
    eligible = [item for item in candidates if item["scores"]["originality"] > 0]
    if not eligible:
        raise RuntimeError("Autonomous topic selection found no eligible evergreen candidate; completed history is authoritative.")
    chosen = max(eligible, key=lambda item: (item["total"], item["topic"]))
    chosen["selected"] = True
    return {"schema_version": 1, "selected_topic": chosen["topic"], "selection_mode": source,
            "trend_status": "verified" if supplied else "unavailable", "research_time": datetime.now(timezone.utc).isoformat(),
            "duplicate_policy": "Only completed/published/publishable run-history records and the explicit three-run allowlist block duplicates; handoffs and partial runs do not.",
            "candidates": candidates, "live_candidate_count": len(supplied), "selection_reason": chosen["reason"]}


def topic_selection_schema() -> dict[str, Any]:
    candidate = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "minLength": 8}, "source_urls": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "anatomical_angle": {"type": "string", "minLength": 8}, "curiosity_reason": {"type": "string", "minLength": 8},
            "provider_safe": {"type": "boolean"},
        },
        "required": ["topic", "source_urls", "anatomical_angle", "curiosity_reason", "provider_safe"], "additionalProperties": False,
    }
    return {"type": "object", "properties": {"candidates": {"type": "array", "minItems": 3, "maxItems": 6, "items": candidate}}, "required": ["candidates"], "additionalProperties": False}


async def select_topic_with_llm(history_path: Path, llm: Any) -> dict[str, Any]:
    """Use the explicitly selected LLM only after a production route is explicit."""
    completed = _completed_topics(history_path)
    prompt = (
        "Produce globally understandable science-short candidates using the curiosity loop: everyone assumes X, "
        "actually Y happens, because hidden mechanism Z. Prefer an anatomical/cutaway angle that can be shown in a dark neutral 3D void. "
        "Include authoritative source URLs. Exclude these normalized completed topics: " + ", ".join(sorted(completed))
    )
    payload = await llm.generate_topic_selection(prompt, topic_selection_schema())
    raw = payload.get("candidates") if isinstance(payload, dict) else None
    candidates: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict) or not item.get("provider_safe"):
            continue
        topic = str(item.get("topic") or "").strip()
        if not topic or run_history.topic_key(topic) in completed:
            continue
        candidates.append({
            "topic": topic, "source_urls": [str(url) for url in item.get("source_urls") or [] if str(url).startswith(("https://", "http://"))],
            "anatomical_angle": str(item.get("anatomical_angle") or ""), "reason": str(item.get("curiosity_reason") or ""),
            "scores": {"provider_safe": 10, "originality": 10}, "selected": False,
        })
    if not candidates:
        raise RuntimeError("Autonomous LLM topic selection returned no eligible, source-backed candidates.")
    chosen = candidates[0]
    chosen["selected"] = True
    return {"schema_version": 2, "selected_topic": chosen["topic"], "selection_mode": "llm_provider", "trend_status": "unavailable",
            "research_time": datetime.now(timezone.utc).isoformat(), "duplicate_policy": "Only completed/published/publishable runs and the preserved completed allowlist are excluded.",
            "candidates": candidates, "selection_reason": chosen["reason"], "model_selection": "explicit selected LLM provider"}
