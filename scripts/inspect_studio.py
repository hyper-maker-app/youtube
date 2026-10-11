import asyncio
import json
import sys
import urllib.request
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def inspect_shorts_list():
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

        # Navigate to shorts
        print("Navigating to shorts list...")
        await call("Page.navigate", {"url": "https://studio.youtube.com/channel/UCfJBf7-xON6DIATQJW5Av7w/videos/short"})
        await asyncio.sleep(4.0)

        get_videos_js = """(() => {
            function queryAll(selector, root = document) {
                let results = Array.from(root.querySelectorAll(selector));
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                let n;
                while (n = walker.nextNode()) {
                    if (n.shadowRoot) results = results.concat(queryAll(selector, n.shadowRoot));
                }
                return results;
            }

            const rows = queryAll('ytcp-video-row');
            return rows.map(r => {
                const titleEl = queryAll('#video-title', r)[0];
                const visibilityEl = queryAll('.cell-body.visibility', r)[0];
                const dateEl = queryAll('.cell-body.date', r)[0];
                const viewsEl = queryAll('.cell-body.views', r)[0];
                const videoId = r.getAttribute('video-id') || (r.id || '');
                const link = queryAll('a[href*="/video/"]', r)[0];
                return {
                    title: titleEl ? titleEl.innerText.trim() : '',
                    visibility: visibilityEl ? visibilityEl.innerText.trim() : '',
                    date: dateEl ? dateEl.innerText.trim() : '',
                    views: viewsEl ? viewsEl.innerText.trim() : '',
                    videoId: videoId,
                    href: link ? link.href : ''
                };
            });
        })()"""
        videos = await eval_js(get_videos_js)
        print("Found Videos in Studio:")
        print(json.dumps(videos, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(inspect_shorts_list())
