"""Mock research provider for zero-cost offline tests and --dry-run mode."""

from __future__ import annotations

from typing import Any

from providers.base import BaseResearchProvider
from services.live_research_engine import ResearchQuery, ResearchResult


class MockResearchProvider(BaseResearchProvider):
    """Offline deterministic research provider supplying fixture data."""

    def __init__(self, fixture_facts: list[str] | None = None) -> None:
        self.fixture_facts = fixture_facts or [
            "Excavation trenches uncovered stratified occupational layers dating to the 3rd millennium BC.",
            "Sub-surface magnetometer surveys confirmed anomalous geometric stone alignments below topsoil.",
            "Ceramic typology corresponds to regional Late Bronze Age trade networks.",
        ]

    async def fetch(self, query: Any) -> Any:
        """Return a structured ResearchResult populated with fixture data."""
        topic_str = getattr(query, "topic", str(query))
        era_str = getattr(query, "era", "default")

        return ResearchResult(
            topic=topic_str,
            era=era_str,
            fetched_facts=list(self.fixture_facts),
            fetched_materials=[
                "hand-dressed local limestone rubble with lime mortar",
                "charred cedar roof timbers and clay slip roofing tiles",
            ],
            fetched_sensory=[
                "scent of damp calcified earth rising from freshly uncovered bedrock",
                "harsh wind carrying fine quartz dust across the trench perimeter",
            ],
            source_urls=["https://example.org/archaeological_report_sample"],
            confidence_score=0.95,
            is_offline_fallback=True,
        )
