"""Provider-neutral asynchronous contracts.

Concrete adapters own their endpoint, authentication, and request behavior. These
contracts deliberately supply neither credentials nor implicit fallback behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ProviderError(RuntimeError):
    """A selected provider could not complete its requested operation."""


class ConfigurationError(ProviderError):
    """A selected provider is missing explicit configuration."""


class HandoffPending(ProviderError):
    """A provider needs a human to complete a resumable external step.

    This is deliberately distinct from a transport failure.  Adapters use it where a
    browser-bound provider (currently Google Flow) cannot safely retry after a session
    or bridge failure, but can leave an exact manual command in ``handoff.md``.
    """

    def __init__(self, message: str, handoff_path: Path) -> None:
        super().__init__(f"{message} Manual completion: {handoff_path}")
        self.handoff_path = Path(handoff_path)


class BaseLLMProvider(ABC):
    async def review_images(self, images: list[Path], contract: str) -> dict[str, Any]:
        """Review supplied assets with the explicitly selected multimodal adapter."""
        raise ProviderError("Selected LLM adapter does not support visual admission")

    async def generate_topic_selection(self, system_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a structured autonomous topic-selection payload."""
        raise ProviderError("Selected LLM provider does not implement autonomous topic selection.")

    @abstractmethod
    async def generate_script(
        self, topic: str, system_prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a structured script that satisfies ``schema``."""


class BaseImageProvider(ABC):
    @abstractmethod
    async def generate_keyframe(
        self,
        prompt: str,
        out_path: Path,
        seed: int,
        aspect_ratio: str = "9:16",
        reference_image: Path | None = None,
        is_hero: bool = False,
        reference_images: list[Path] | None = None,
        negative_prompt: str | None = None,
    ) -> Path:
        """Write and return a generated keyframe path.

        ``reference_image`` is the immediately preceding accepted keyframe when a
        Match-Cut chain needs image-conditioned continuity.  It is deliberately a
        provider-boundary input: services only author the visual contract and never
        learn a provider's transport or media-upload details.

        ``is_hero`` selects the provider's configured opening/reveal quality tier.
        Providers without tiers accept it as a no-op to preserve one polymorphic
        factory contract.
        """

    async def generate_reference_sheet(
        self, prompt: str, out_path: Path, seed: int, aspect_ratio: str,
    ) -> Path:
        """Generate a roster reference sheet through the selected image provider.

        Adapters may override this when their sheet transport differs.  The default
        retains one provider-owned image path and never introduces a fallback.
        """
        return await self.generate_keyframe(prompt, out_path, seed, aspect_ratio)


class BaseVideoProvider(ABC):
    # Adapter capability, never a creative scene-duration limit.
    native_clip_duration: float = 4.0

    @abstractmethod
    async def animate_block(
        self,
        start_frame: Path,
        end_frame: Path | None,
        motion_prompt: str,
        out_path: Path,
        duration: float = 4.0,
    ) -> Path:
        """Write and return one animated block."""


class BaseVoiceProvider(ABC):
    @abstractmethod
    async def generate_narration(
        self, beats: list[Any], out_path: Path, lang: str
    ) -> dict[str, Any]:
        """Return ``vo_path``, measured ``duration``, and word-level ``words``."""


class BaseSfxProvider(ABC):
    """Resolve deliberately licensed sound effects from one selected catalogue.

    This boundary intentionally has no generic web-search operation.  An adapter may
    download a catalogue item only after it has supplied the complete provenance
    metadata represented by ``query``; callers must verify that metadata before an
    item is admitted to the local cache.
    """

    @abstractmethod
    async def resolve_asset(self, query: dict[str, Any], cache_dir: Path) -> dict[str, Any]:
        """Return one downloaded/local asset record with licensing provenance."""


class BaseResearchProvider(ABC):
    """Fetch and sanitize live research data to enrich a HistoricalTruthSheet.

    Concrete adapters implement network retrieval (Wikipedia, academic sources).
    The service layer (services/live_research_engine.py) is strictly AST-clean
    and only receives pre-fetched ResearchResult objects injected from pipeline.py.

    In ``--dry-run`` mode, providers/research/mock_provider.py must be used.
    """

    @abstractmethod
    async def fetch(self, query: "Any") -> "Any":
        """Fetch and return a ResearchResult for the given ResearchQuery.

        Implementations must sanitize raw text (strip [1], [citation needed],
        editorial marks) before populating ResearchResult fields.
        Returns a ResearchResult dataclass defined in services/live_research_engine.py.
        """

