from __future__ import annotations

import asyncio
import json
import urllib.request
from services.playwright_flow_client import PlaywrightFlowClient


async def check_all() -> None:
    client = PlaywrightFlowClient()
    try:
        await client.connect()
        raw = urllib.request.urlopen(f"http://127.0.0.1:{client.cdp_port}/json/version", timeout=5).read()
        data = json.loads(raw)
        print(f"[OK] Chrome CDP active on port {client.cdp_port}: {data.get('Browser', 'unknown')}")
        fp = await client.read_browser_fingerprint()
        print(f"[OK] Browser Fingerprint: {fp.get('userAgent', '')[:70]}... ({fp.get('platformFull')})")
        token = await client.mint_recaptcha_token("FLOW_GENERATION")
        print(f"[OK] Real Browser reCAPTCHA Enterprise Token Minted: {len(token)} chars ({token[:28]}...)")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_all())
