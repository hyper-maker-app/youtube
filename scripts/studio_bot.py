"""Bulk unlist legacy videos via YouTube Studio bulk actions."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
import websockets
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class StudioCDP:
    def __init__(self, port: int = 9222):
        self.port = port
        self.ws: Any = None
        self._msg_id = 0

    async def connect(self) -> dict:
        req = urllib.request.Request(f"http://[::1]:{self.port}/json")
        pages = json.loads(urllib.request.urlopen(req).read().decode())
        target = next((p for p in pages if "studio.youtube.com" in p.get("url", "")), None)
        if not target:
            target = next((p for p in pages if p.get("type") == "page"), None)
        self.ws_url = target["webSocketDebuggerUrl"]
        self.ws = await websockets.connect(self.ws_url, max_size=10 * 1024 * 1024)
        return target

    async def call(self, method: str, params: dict | None = None) -> dict:
        self._msg_id += 1
        payload = {"id": self._msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self._msg_id:
                return data

    async def eval_js(self, expression: str, return_by_value: bool = True) -> Any:
        res = await self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": return_by_value,
            "awaitPromise": True,
        })
        if not return_by_value:
            return res
        result = res.get("result", {}).get("result", {})
        return result.get("value")

    async def navigate(self, url: str) -> None:
        await self.call("Page.navigate", {"url": url})
        await asyncio.sleep(4.0)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()


async def check_upload_defaults():
    bot = StudioCDP()
    await bot.connect()

    print("\n--- Opening Settings via #settings-item ---")
    click_js = """(() => {
        function queryAll(selector, root = document) {
            let results = Array.from(root.querySelectorAll(selector));
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
            let n;
            while (n = walker.nextNode()) {
                if (n.shadowRoot) results = results.concat(queryAll(selector, n.shadowRoot));
            }
            return results;
        }
        const btn = queryAll('#settings-item')[0];
        if (btn) {
            btn.click();
            return 'Clicked #settings-item';
        }
        return 'Not found';
    })()"""
    print(await bot.eval_js(click_js))
    await asyncio.sleep(2.5)

    # Inspect dialog tabs
    inspect_tabs_js = """(() => {
        function queryAll(selector, root = document) {
            let results = Array.from(root.querySelectorAll(selector));
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
            let n;
            while (n = walker.nextNode()) {
                if (n.shadowRoot) results = results.concat(queryAll(selector, n.shadowRoot));
            }
            return results;
        }
        const dialog = queryAll('[role="dialog"]').find(d => (d.innerText || '').includes('Genel') || (d.innerText || '').includes('Kanal') || (d.innerText || '').includes('Yükleme'));
        if (!dialog) return { found: false, allDialogs: queryAll('[role="dialog"]').map(d => (d.innerText || '').slice(0, 100)) };

        const items = queryAll('tp-yt-paper-tab, ytcp-navigation-item, .navigation-item, tp-yt-paper-item, [role="tab"]', dialog);
        return {
            found: true,
            tabs: items.map(t => t.innerText.trim()).filter(Boolean)
        };
    })()"""
    dialog_info = await bot.eval_js(inspect_tabs_js)
    print("Settings dialog tabs:", json.dumps(dialog_info, indent=2, ensure_ascii=False))

    await bot.close()


if __name__ == "__main__":
    asyncio.run(check_upload_defaults())


