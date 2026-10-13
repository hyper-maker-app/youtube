"""Live Deep-Research Service Layer and Truth Sheet Enricher.

Defines AST-clean interfaces, data models, and deduplication logic for
integrating live research into historical truth sheets (ADR-067).

Strictly AST-clean: Zero network calls, zero provider imports. Network calls
and live web queries are performed exclusively in providers/research/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.historical_research import HistoricalTruthSheet


@dataclass
class ResearchQuery:
    """Input query specification for live research retrieval."""

    topic: str
    era: str
    max_results: int = 5
    language: str = "en"


@dataclass
class ResearchResult:
    """Normalized payload of facts and sensory data fetched from external sources."""

    topic: str
    era: str
    fetched_facts: list[str] = field(default_factory=list)
    fetched_figures: list[dict[str, str]] = field(default_factory=list)
    fetched_materials: list[str] = field(default_factory=list)
    fetched_sensory: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    confidence_score: float = 0.85
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_offline_fallback: bool = False


class HistoricalTruthSheetEnricher:
    """Enriches an existing HistoricalTruthSheet with live research results."""

    _CITATION_STRIP_REGEX = re.compile(
        r"\[(?:[0-9]+|citation needed|clarification needed|edit)\]",
        re.IGNORECASE,
    )
    _HTML_TAG_REGEX = re.compile(r"<[^>]+>")
    _WHITESPACE_REGEX = re.compile(r"\s+")

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Strip editorial bracket citations, HTML artifacts, and excess spaces."""
        cleaned = cls._HTML_TAG_REGEX.sub("", str(text or ""))
        cleaned = cls._CITATION_STRIP_REGEX.sub("", cleaned)
        cleaned = cls._WHITESPACE_REGEX.sub(" ", cleaned).strip()
        return cleaned

    def _merge_facts(self, existing: list[str], fetched: list[str]) -> list[str]:
        """Merge, sanitize, and deduplicate historical facts preserving priority."""
        seen: set[str] = set()
        merged: list[str] = []

        # 1. Add verified existing facts first
        for item in existing:
            sanitized = self.sanitize_text(item)
            key = sanitized.casefold()
            if sanitized and key not in seen:
                seen.add(key)
                merged.append(sanitized)

        # 2. Add fetched facts that don't duplicate existing entries
        for item in fetched:
            sanitized = self.sanitize_text(item)
            key = sanitized.casefold()
            if sanitized and key not in seen and len(sanitized) > 15:
                # Substring deduplication check
                if not any(key in existing_key for existing_key in seen):
                    seen.add(key)
                    merged.append(sanitized)

        return merged

    def _merge_list(self, existing: list[str], fetched: list[str]) -> list[str]:
        """Generic list merger with sanitization and deduplication."""
        seen: set[str] = set()
        merged: list[str] = []
        for item in list(existing) + list(fetched):
            sanitized = self.sanitize_text(item)
            key = sanitized.casefold()
            if sanitized and key not in seen:
                seen.add(key)
                merged.append(sanitized)
        return merged

    def enrich(
        self, sheet: HistoricalTruthSheet, result: ResearchResult
    ) -> HistoricalTruthSheet:
        """Return a newly enriched HistoricalTruthSheet instance."""
        enriched_facts = self._merge_facts(sheet.verified_facts, result.fetched_facts)
        enriched_materials = self._merge_list(
            sheet.architecture_and_materials, result.fetched_materials
        )
        enriched_sensory = self._merge_list(
            sheet.sensory_details, result.fetched_sensory
        )

        # Combine figures without duplicate names
        existing_figure_names = {
            f.get("name", "").casefold() for f in sheet.historical_figures if isinstance(f, dict)
        }
        merged_figures = list(sheet.historical_figures)
        for fig in result.fetched_figures:
            if isinstance(fig, dict):
                name = fig.get("name", "").strip()
                if name and name.casefold() not in existing_figure_names:
                    existing_figure_names.add(name.casefold())
                    merged_figures.append(fig)

        return HistoricalTruthSheet(
            topic=sheet.topic,
            era=sheet.era,
            civilization=sheet.civilization,
            location_name=sheet.location_name,
            time_period=sheet.time_period,
            verified_dates=list(sheet.verified_dates),
            historical_figures=merged_figures,
            architecture_and_materials=enriched_materials,
            sensory_details=enriched_sensory,
            prohibited_anachronisms=list(sheet.prohibited_anachronisms),
            verified_facts=enriched_facts,
            narrative_beats=list(sheet.narrative_beats),
            curated_beats=list(sheet.curated_beats),
        )

    def calculate_enrichment_score(
        self, original: HistoricalTruthSheet, enriched: HistoricalTruthSheet
    ) -> float:
        """Measure net knowledge gain after enrichment (1.0 = equal, >1.0 = gained facts)."""
        orig_count = max(1, len(original.verified_facts) + len(original.architecture_and_materials))
        new_count = len(enriched.verified_facts) + len(enriched.architecture_and_materials)
        return round(float(new_count) / float(orig_count), 2)
