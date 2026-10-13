"""Unit tests for Engine 3: Live Deep-Research Engine (services/live_research_engine.py)."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest
from providers.research.mock_provider import MockResearchProvider
from providers.research.wikipedia_provider import WikipediaResearchProvider
from services.historical_research import HistoricalTruthSheet, get_historical_truth_sheet
from services.live_research_engine import (
    HistoricalTruthSheetEnricher,
    ResearchQuery,
    ResearchResult,
)


def test_sanitize_text_strips_citations_and_html():
    raw = "The pyramid was completed in 1850 BC[1][citation needed]. <b>Excavations</b> confirmed underground shafts[12]."
    cleaned = HistoricalTruthSheetEnricher.sanitize_text(raw)
    assert "[1]" not in cleaned
    assert "[citation needed]" not in cleaned
    assert "[12]" not in cleaned
    assert "<b>" not in cleaned
    assert "</b>" not in cleaned
    assert "1850 BC." in cleaned
    assert "Excavations confirmed" in cleaned


def test_enricher_merges_facts_without_duplicates():
    base_sheet = get_historical_truth_sheet("The Lost Labyrinth of Hawara")
    orig_fact_count = len(base_sheet.verified_facts)

    new_facts = [
        "Subterranean passages were mapped using ground-penetrating radar in 2008.",
        base_sheet.verified_facts[0],  # Duplicate
        "A multi-chamber limestone foundation was confirmed beneath the mud-brick structure.",
    ]

    result = ResearchResult(
        topic="The Lost Labyrinth of Hawara",
        era="egyptian",
        fetched_facts=new_facts,
        fetched_materials=["dressed quartzite blocks"],
        fetched_sensory=["echoing acoustic chamber humidity"],
    )

    enricher = HistoricalTruthSheetEnricher()
    enriched = enricher.enrich(base_sheet, result)

    assert len(enriched.verified_facts) > orig_fact_count
    # Verify no duplicate entries
    assert len(enriched.verified_facts) == len(set(f.lower() for f in enriched.verified_facts))
    assert any("quartzite" in m for m in enriched.architecture_and_materials)
    assert any("acoustic" in s for s in enriched.sensory_details)


def test_enricher_merges_historical_figures_dedup():
    base_sheet = get_historical_truth_sheet("Gallipoli 1915")
    enricher = HistoricalTruthSheetEnricher()

    result = ResearchResult(
        topic="Gallipoli 1915",
        era="world_war_i",
        fetched_figures=[
            {"name": "Corporal Seyit", "role": "artilleryman"},  # might exist
            {"name": "Commander Cevat Pasha", "role": "fortified area commander"},  # new figure
        ],
    )

    enriched = enricher.enrich(base_sheet, result)
    names = [f.get("name") for f in enriched.historical_figures if isinstance(f, dict)]
    assert "Commander Cevat Pasha" in names


def test_calculate_enrichment_score():
    base_sheet = get_historical_truth_sheet("Pompeii Volcanic Blast")
    enricher = HistoricalTruthSheetEnricher()

    result = ResearchResult(
        topic="Pompeii Volcanic Blast",
        era="greco_roman",
        fetched_facts=["Fact 1: Pyroclastic density current reached 300C.", "Fact 2: Ash layer exceeded 4 meters."],
        fetched_materials=["pumice lapilli layers"],
    )

    enriched = enricher.enrich(base_sheet, result)
    score = enricher.calculate_enrichment_score(base_sheet, enriched)
    assert score > 1.0


def test_mock_research_provider_fetch():
    provider = MockResearchProvider()
    query = ResearchQuery(topic="Göbekli Tepe Megaliths", era="neolithic")
    result = asyncio.run(provider.fetch(query))

    assert isinstance(result, ResearchResult)
    assert len(result.fetched_facts) >= 2
    assert result.is_offline_fallback is True
    assert result.topic == "Göbekli Tepe Megaliths"


def test_wikipedia_provider_graceful_fallback():
    # Pass an impossible/empty topic or short timeout to test graceful fallback
    provider = WikipediaResearchProvider(timeout_seconds=0.01)
    query = ResearchQuery(topic="NonExistentTopic9876543210XYZ", era="default")
    result = asyncio.run(provider.fetch(query))

    assert isinstance(result, ResearchResult)
    assert len(result.fetched_facts) > 0


def test_ast_cleanliness_services_layer():
    """Verify services/live_research_engine.py contains zero network or transport imports."""
    source_path = Path(__file__).resolve().parent.parent / "services" / "live_research_engine.py"
    tree = ast.parse(source_path.read_text("utf-8"), filename=str(source_path))

    forbidden_modules = {"httpx", "requests", "urllib", "aiohttp", "websockets", "google"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                assert mod not in forbidden_modules, f"Forbidden import: {mod}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                assert mod not in forbidden_modules, f"Forbidden from-import: {mod}"
