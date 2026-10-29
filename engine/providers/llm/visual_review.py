"""Shared multimodal review transport; no implicit model or provider selection."""
import json
from pathlib import Path

from providers.base import ProviderError


def review_with_client(client, model, images, contract):
    from google.genai import types
    contents = ["Inspect every supplied image against this authored contract. "
        "Return JSON {accepted: boolean, reasons: string[]}. Reject uncertain identity, wrong geometry, "
        "unrequested text, speaking mouths, deformation or changed countable parts. "
        "Do not reject an authored illustrated style merely because it is not 3D. " + contract]
    for path in images:
        path = Path(path)
        mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        contents.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime))
    try:
        response = client.models.generate_content(model=model, contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"))
        result = getattr(response, "parsed", None) or json.loads(response.text)
    except Exception as exc:
        raise ProviderError("Visual review failed; accepted assets preserved") from exc
    if not isinstance(result, dict) or type(result.get("accepted")) is not bool or not isinstance(result.get("reasons"), list):
        raise ProviderError("Malformed visual review; admission withheld")
    return result
