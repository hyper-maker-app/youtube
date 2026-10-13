"""Live Wikipedia research provider for dynamic topic truth enrichment."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any

from providers.base import BaseResearchProvider
from providers.research.mock_provider import MockResearchProvider
from services.live_research_engine import HistoricalTruthSheetEnricher, ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)


class WikipediaResearchProvider(BaseResearchProvider):
    """Asynchronous research provider querying the public Wikipedia REST API."""

    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.fallback = MockResearchProvider()

    async def fetch(self, query: Any) -> Any:
        """Fetch and parse intro summary facts from Wikipedia for the query topic."""
        topic_str = getattr(query, "topic", str(query))
        era_str = getattr(query, "era", "default")
        max_results = getattr(query, "max_results", 5)

        clean_topic = re.sub(r"[^\w\s-]", "", topic_str).strip()
        if not clean_topic:
            return await self.fallback.fetch(query)

        # Construct standard Wikipedia API query
        encoded = urllib.parse.quote(clean_topic)
        url = (
            f"https://en.wikipedia.org/w/api.php?action=query&format=json"
            f"&prop=extracts&exintro=1&explaintext=1&titles={encoded}&redirects=1"
        )

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "YouTubeDocuBot/1.0 (historical research enricher)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            pages = data.get("query", {}).get("pages", {})
            extract = ""
            for _, page in pages.items():
                if "extract" in page:
                    extract = page["extract"]
                    break

            if not extract or len(extract) < 50:
                logger.info(f"[WIKI RESEARCH] No direct extract for '{clean_topic}', using fallback fixture.")
                return await self.fallback.fetch(query)

            # Split extract into clean factual sentences
            raw_sentences = re.split(r"(?<=[.!?])\s+", extract)
            facts: list[str] = []
            for s in raw_sentences:
                clean_s = HistoricalTruthSheetEnricher.sanitize_text(s)
                if len(clean_s) > 25 and not clean_s.startswith("For other uses"):
                    facts.append(clean_s)
                if len(facts) >= max_results:
                    break

            if not facts:
                return await self.fallback.fetch(query)

            return ResearchResult(
                topic=topic_str,
                era=era_str,
                fetched_facts=facts,
                fetched_materials=[],
                fetched_sensory=[],
                source_urls=[f"https://en.wikipedia.org/wiki/{encoded}"],
                confidence_score=0.90,
                is_offline_fallback=False,
            )

        except Exception as exc:
            logger.warning(f"[WIKI RESEARCH] Network fetch failed ({exc}), falling back to fixture.")
            return await self.fallback.fetch(query)
