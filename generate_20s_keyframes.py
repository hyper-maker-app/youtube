import asyncio
import httpx
from pathlib import Path

KEYFRAME_PROMPTS = {
    "kf01": (
        "First-person driver POV from eye level inside a car, warm tan leather steering wheel and tan dashboard, "
        "driver two bare male forearms with warm natural skin tone gripping the steering wheel, no sleeves, no watch, "
        "driving forward on an asphalt road toward a calm blue lake under a clear blue sky on a sunny day with green trees on the horizon, "
        "blue denim jeans visible at bottom on thighs, 3D stylized glossy Zack D. Films documentary style, "
        "claymation SSS subsurface scattering, 9:16 vertical portrait, sharp focus, closed mouth, no text"
    ),
    "kf02": (
        "Exterior underwater shot of a car side window submerged in deep dark blue lake water, "
        "multiple solid 3D glowing red volumetric arrows with solid conical arrowheads and glowing cylindrical shafts "
        "pointing inward pressing heavily against the glass window, "
        "driver in white crew-neck t-shirt visible through the dim glass inside, dim cool-blue underwater lighting, "
        "3D stylized glossy Zack D. Films documentary style, claymation SSS subsurface scattering, 9:16 vertical portrait, sharp focus, no text"
    ),
    "kf03": (
        "Downward first-person driver POV inside a submerged car cabin with dim cool-blue ambient lighting, "
        "dark blue lake water visible outside the side window, "
        "driver left bare muscular arm with warm natural skin tone reaching down to door armrest pressing black electric power window switch, "
        "warm tan leather door panel and tan steering wheel rim, blue denim jeans on lap, "
        "3D stylized glossy Zack D. Films documentary style, claymation SSS subsurface scattering, 9:16 vertical portrait, sharp focus, no text"
    ),
    "kf04": (
        "First-person underwater swimming POV looking straight up toward the sunlit lake surface from below, "
        "sun rays and air bubbles rising in deep blue water, "
        "two bare male arms reaching upward breaststroking toward the water surface, "
        "3D stylized glossy Zack D. Films documentary style, claymation SSS subsurface scattering, 9:16 vertical portrait, sharp focus, no text"
    ),
    "kf05": (
        "Macro cutaway close-up of a car door interior panel with a circular cross-section cutaway "
        "revealing a bright yellow circular electric power window gear motor and green PCB circuit board flooded with cascading blue water splashing over components, "
        "in the foreground driver bare finger pressing the black electric window switch, warm tan door trim, "
        "3D stylized glossy Zack D. Films documentary style, claymation SSS subsurface scattering, 9:16 vertical portrait, sharp focus, no text"
    )
}

async def generate_keyframe(client: httpx.AsyncClient, name: str, prompt: str, out_dir: Path) -> Path:
    out_file = out_dir / f"{name}.png"
    if out_file.exists() and out_file.stat().st_size > 10000:
        print(f"[{name}] Already exists ({out_file.stat().st_size} bytes). Skipping.")
        return out_file

    print(f"[{name}] Generating via Flow Agent (model: beluga)...")
    payload = {
        "prompt": prompt,
        "model": "beluga",
        "n": 1,
        "aspect_ratio": "9:16",
        "response_format": "url"
    }
    headers = {
        "Authorization": "Bearer flow",
        "X-Flow-Agent-Session-Token": "flow",
    }
    resp = await client.post("http://127.0.0.1:8001/v1/images/generations", json=payload, headers=headers, timeout=180.0)
    if resp.status_code != 200:
        raise RuntimeError(f"[{name}] Generation failed {resp.status_code}: {resp.text}")
    
    data = resp.json()
    img_url = data["data"][0]["url"]
    print(f"[{name}] Downloading from {img_url}...")
    img_resp = await client.get(img_url, timeout=60.0)
    out_file.write_bytes(img_resp.content)
    print(f"[{name}] Saved {out_file} ({out_file.stat().st_size} bytes)")
    return out_file

async def main():
    out_dir = Path("production_20s")
    out_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=300.0) as client:
        for name, prompt in KEYFRAME_PROMPTS.items():
            await generate_keyframe(client, name, prompt, out_dir)
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
