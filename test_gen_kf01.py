import asyncio
import httpx
from pathlib import Path

async def main():
    prompt = (
        "First-person driver POV inside a car with warm tan leather steering wheel and tan dashboard, "
        "driver bare male forearms with warm natural skin tone gripping the steering wheel, "
        "driving forward on an asphalt road toward a calm blue lake on a clear sunny day with green trees on the horizon, "
        "blue denim jeans visible at bottom, 3D stylized glossy Zack D. Films documentary style, "
        "claymation SSS subsurface scattering, 9:16 vertical portrait, sharp focus, no text, closed mouth"
    )
    payload = {
        "prompt": prompt,
        "model": "narwhal",
        "n": 1,
        "aspect_ratio": "9:16",
        "response_format": "url"
    }
    headers = {
        "Authorization": "Bearer flow",
        "X-Flow-Agent-Session-Token": "flow",
    }
    out_dir = Path("production_3blocks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "kf01.png"
    
    print(f"Requesting kf01 from Flow Agent at http://127.0.0.1:8001...")
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post("http://127.0.0.1:8001/v1/images/generations", json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(f"Response keys: {list(data.keys())}")
        img_url = data["data"][0]["url"]
        print(f"Image URL: {img_url}")
        
        # Download image
        img_resp = await client.get(img_url)
        out_file.write_bytes(img_resp.content)
        print(f"Saved {out_file} ({out_file.stat().st_size} bytes)")

if __name__ == "__main__":
    asyncio.run(main())
