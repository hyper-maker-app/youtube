from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path

from providers.base import BaseImageProvider, ConfigurationError, HandoffPending
from providers.flow_contract import mapping, settings, transport_provenance, verified_cli_model
from services.playwright_flow_client import FLOW_BINARY
from services.playwright_flow_client import PlaywrightFlowClient

logger = logging.getLogger(__name__)


class PlaywrightFlowImageProvider(BaseImageProvider):
    def __init__(self, *, client=None):
        self.contract = settings(test=False)
        self.client = client or PlaywrightFlowClient()
        self._reference_requests: dict[str, dict] = {}

    def preflight(self):
        return verified_cli_model("image", FLOW_BINARY)

    async def generate_keyframe(
        self,
        prompt: str,
        out_path: Path,
        seed: int = 42,
        aspect_ratio: str = "9:16",
        reference_image: Path | None = None,
        is_hero: bool = False,
        reference_images: list[Path] | None = None,
        negative_prompt: str | None = None,
    ) -> Path:
        _ = (seed, is_hero, negative_prompt)
        refs = list(reference_images or [])
        if reference_image is not None:
            refs.append(reference_image)
        if refs:
            # The catalog label is not an observed conditioning payload.  Persist
            # exact hashes and the missing boundary evidence, then stop before a
            # browser, upload, or paid request can occur.
            if any(not path.is_file() for path in refs):
                raise ConfigurationError("Nano Banana Pro reference image is missing; conditioning was not submitted")
            state_path = Path(out_path).with_suffix(".flow-repair.json")
            request = {
                "asset_type": "image", "model_alias": self.contract["image_model"],
                "model_identity": "GEM_PIX_2", "conditioning": "reference_images",
                "reference_images": [{"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                     for path in refs],
                "response_evidence": {"provider_request_id": None, "provider_response_id": None},
            }
            state_path.write_text(json.dumps({
                "schema_version": 1, "status": "repair_required", "repair_kind": "reference_conditioning",
                "request": request,
                "required_evidence": ["observed_reference_upload_request_payload", "observed_reference_conditioning_field",
                                      "provider_request_id", "provider_response_id", "provider_output_media_binding"],
                "reason": "Nano Banana Pro has no verified Flow reference upload/response contract; no provider request was sent.",
            }, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            raise HandoffPending("Nano Banana Pro reference conditioning requires transport repair before generation", state_path)
        logger.info(f"Generating image with Playwright CDP Flow ({aspect_ratio}): {prompt[:60]}...")
        output = await self.client.generate_asset(
            prompt=prompt,
            out_path=out_path,
            asset_type="image",
            aspect_ratio=aspect_ratio,
            reference_images=refs, model=self.contract["image_model"],
        )
        # A future evidence-producing client writes this sidecar only after the
        # provider response has been normalized.  Keeping the raw sidecar out of
        # the registry prevents invented request IDs or model claims.
        sidecar = Path(output).with_suffix(".flow.json")
        if sidecar.is_file():
            self._reference_requests[str(Path(output).resolve())] = json.loads(sidecar.read_text(encoding="utf-8"))
        return output

    def reference_provenance(self, outputs: list[Path]) -> dict:
        """Return auditable output evidence or fail before registry acceptance.

        This is intentionally not a metadata template: Flow's currently selected
        image route has no verified response contract, so an ordinary production
        run receives a repair error rather than synthetic provenance.
        """
        if not outputs:
            raise ConfigurationError("Nano Banana Pro provenance requires generated output files")
        image_model = mapping()["image"]
        if (image_model.get("alias") != "nano_banana_pro" or image_model.get("cli_name") != "gem_pix_2"
                or image_model.get("internal_model_keys") != ["GEM_PIX_2"]
                or not image_model.get("reference_transport_verified")
                or not image_model.get("response_contract_verified")):
            raise ConfigurationError("Nano Banana Pro provenance is unavailable: verified image reference transport/response evidence is required")
        records = [self._reference_requests.get(str(Path(path).resolve())) for path in outputs]
        if any(record is None for record in records):
            raise ConfigurationError("Nano Banana Pro provenance sidecar is missing; repair the image transport")
        # The evidence schema is deliberately strict so a future adapter cannot
        # bless a filename or request metadata as a provider response.
        hashes = [hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in outputs]
        requests = [record.get("request", {}) for record in records]
        responses = [record.get("response", {}) for record in records]
        request_ids = [item.get("request_id") for item in requests]
        response_ids = [item.get("response_id") for item in responses]
        if (not all(request_ids) or not all(response_ids)
                or any(record.get("evidence_origin") != "observed_provider_boundary"
                       or record.get("test_only") is True or record.get("fixture") is True for record in records)
                or any(item.get("model_alias") != "nano_banana_pro" or item.get("model_identity") != "GEM_PIX_2"
                       or item.get("conditioning") != "reference_images" or not item.get("reference_images") for item in requests)
                or any(item.get("origin") != "provider_response" for item in responses)
                or any(item.get("output_sha256") != digest for item, digest in zip(responses, hashes))):
            raise ConfigurationError("Nano Banana Pro sidecar lacks provider-bound request/response provenance")
        transport = transport_provenance()
        return {"provider": "nano_banana_pro", "model_alias": "nano_banana_pro", "model_identity": "GEM_PIX_2",
                "request_metadata": {"model_identity": "GEM_PIX_2", "reference_images": [r["reference_images"] for r in requests],
                                     "requests": requests},
                "transport_evidence": {"transport_verified": True, "verified_binary_present": True,
                                       "transport_version": transport["binary_version"], "catalog_sha256": transport["catalog_sha256"]},
                "response_evidence": {"response_contract_verified": True, "request_id": request_ids[0],
                                      "response_id": response_ids[0], "request_ids": request_ids, "response_ids": response_ids}, "reference_conditioning": True,
                "generated_at": [record.get("generated_at") for record in records], "output_file_hashes": hashes,
                "catalog_sha256": transport["catalog_sha256"], "binary_sha256": transport["binary_sha256"],
                "binary_version": transport["binary_version"], "model_catalog_evidence": image_model.get("catalog_evidence", {}),
                "evidence_origin": "observed_provider_boundary",
                "test_only": False, "fixture": False}

    async def close(self) -> None:
        await self.client.close()
