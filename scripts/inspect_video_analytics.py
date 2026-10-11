import asyncio
import json
import sys
import urllib.request
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def inspect_video_analytics():
    req = urllib.request.Request("http://localhost:9222/json/list")
    pages = json.loads(urllib.request.urlopen(req).read().decode())
    target = next((p for p in pages if "studio.youtube.com" in p.get("url", "")), None)
    if not target:
        print("Studio tab not found!")
        return

    ws_url = target["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=10*1024*1024) as ws:
        msg_id = 0
        async def call(method, params=None):
            nonlocal msg_id
            msg_id += 1
            payload = {"id": msg_id, "method": method, "params": params or {}}
            await ws.send(json.dumps(payload))
            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                if data.get("id") == msg_id:
                    return data

        async def eval_js(expr):
            res = await call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
            return res.get("result", {}).get("result", {}).get("value")

        # Navigate to analytics page of BQD-7Kg_uhE
        print("Navigating to video analytics page...")
        await call("Page.navigate", {"url": "https://studio.youtube.com/video/BQD-7Kg_uhE/analytics/tab-overview/period-default"})
        await asyncio.sleep(4.0)

        details_js = """(() => {
            function queryAll(selector, root = document) {
                let results = Array.from(root.querySelectorAll(selector));
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                let n;
                while (n = walker.nextNode()) {
                    if (n.shadowRoot) results = results.concat(queryAll(selector, n.shadowRoot));
                }
                return results;
            }

            const cards = queryAll('.metric-card, ytcp-metric-card, #metric-header, .align-header');
            return {
                pageTitle: document.title,
                url: location.href,
                bodyText: document.body.innerText.slice(0, 2000)
            };
        })()"""
        details = await eval_js(details_js)
        print("Video Analytics:", json.dumps(details, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(inspect_video_analytics())
