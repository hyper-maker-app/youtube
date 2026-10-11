"""Explicit production bundles for the two user-facing video routes."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .base import ConfigurationError


@dataclass(frozen=True)
class ProductionBundle:
    route: str
    video_provider: str
    image_provider: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_BUNDLES = {
    "vertex": ProductionBundle("vertex", "vertex_veo", "nano_banana_pro"),
    "vertex_veo": ProductionBundle("vertex", "vertex_veo", "nano_banana_pro"),
    "flow": ProductionBundle("flow", "flow_agent", "flow_agent"),
    "flow_agent": ProductionBundle("flow", "flow_agent", "flow_agent"),
}


def production_bundle(route_or_video: str, requested_image: str | None = None) -> ProductionBundle:
    key = route_or_video.strip().casefold().replace("-", "_")
    try:
        bundle = _BUNDLES[key]
    except KeyError as exc:
        raise ConfigurationError(f"No user-facing production bundle exists for video route {route_or_video!r}.") from exc
    if requested_image and requested_image.casefold().replace("-", "_") != bundle.image_provider:
        raise ConfigurationError(f"{bundle.route} route requires image provider {bundle.image_provider!r}; refusing a hidden cross-provider bundle.")
    return bundle
