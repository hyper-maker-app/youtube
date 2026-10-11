import asyncio
import json
import sys
import urllib.request
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def inspect_video_details():
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

        # Navigate to edit page of BQD-7Kg_uhE
        print("Navigating to video edit page...")
        await call("Page.navigate", {"url": "https://studio.youtube.com/video/BQD-7Kg_uhE/edit"})
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

            const title = document.querySelector('#textbox[aria-label*="Başlık"], #textbox[aria-label*="Title"], ytcp-social-suggestions-textbox #textbox');
            const description = document.querySelectorAll('#textbox[aria-label*="Açıklama"], #textbox[aria-label*="Description"], ytcp-social-suggestions-textbox #textbox')[1];
            const videoUrl = queryAll('a.ytcp-video-info, a[href*="youtu.be"], a[href*="youtube.com/shorts"]')[0];

            return {
                pageTitle: document.title,
                url: location.href,
                videoTitle: title ? title.innerText.trim() : 'N/A',
                videoUrl: videoUrl ? videoUrl.href : 'N/A'
            };
        })()"""
        details = await eval_js(details_js)
        print("Video Details:", json.dumps(details, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(inspect_video_details())
