import asyncio
import httpx
from pathlib import Path

BLOCK_CONFIGS = [
    {
        "name": "block01",
        "start_image": "production_20s/kf01.png",
        "prompt": (
            "Car suddenly plunges forward into the lake water, explosive wall of blue lake water and white foam "
            "splashes violently across the exterior windshield glass, driver two bare male arms grip the steering wheel "
            "as the car submerges into murky blue water, cabin interior remains completely dry, camera shakes with impact force, "
            "3D animated documentary style, Zack D. Films aesthetic"
        )
    },
    {
        "name": "block02",
        "start_image": "production_20s/kf02.png",
        "prompt": (
            "Exterior underwater car door view, solid glowing red 3D volumetric conical arrows pulse with intense force "
            "pressing inward against the window glass, trapped driver inside with white t-shirt shoves and pushes frantically "
            "against the locked car door handle, door refuses to open due to external water pressure, streaming bubbles float upward, "
            "3D animated documentary style, Zack D. Films aesthetic"
        )
    },
    {
        "name": "block03",
        "start_image": "production_20s/kf03.png",
        "prompt": (
            "Inside the submerged dim cool-blue car cabin, driver bare arm presses and pulls the black electric power window switch repeatedly, "
            "window glass stays jammed and will not budge, dark water and bubbles visible outside the side window, "
            "camera focuses on the futile switch action, 3D animated documentary style, Zack D. Films aesthetic"
        )
    },
    {
        "name": "block04",
        "start_image": "production_20s/kf04.png",
        "prompt": (
            "First-person underwater swimming POV looking straight up toward the sunlit lake surface, "
            "two bare male arms breaststroke vigorously reaching toward the bright water surface above, "
            "shimmering god rays through deep blue water, rising air bubbles stream past camera, "
            "3D animated documentary style, Zack D. Films aesthetic"
        )
    },
    {
        "name": "block05",
        "start_image": "production_20s/kf05.png",
        "prompt": (
            "Macro close-up cutaway of car door interior panel, cascading blue water surges and shorts out the green PCB circuit board "
            "and yellow gear motor, small electric sparks flicker under water, driver bare finger presses the dead window switch repeatedly "
            "with zero response, 3D animated documentary style, Zack D. Films aesthetic"
        )
    }
]

async def generate_block(client: httpx.AsyncClient, config: dict, out_dir: Path) -> Path:
    name = config["name"]
    out_file = out_dir / f"{name}.mp4"
    if out_file.exists() and out_file.stat().st_size > 100000:
        print(f"[{name}] Already exists ({out_file.stat().st_size} bytes). Skipping.")
        return out_file

    start_img = Path(config["start_image"]).resolve()
    if not start_img.exists():
        raise FileNotFoundError(f"Start image not found: {start_img}")

    print(f"[{name}] Generating 4.0s video via Flow Agent (start: {start_img.name})...")
    payload = {
        "prompt": config["prompt"],
        "aspect": "portrait",
        "duration": "4s",
        "quality": "720p",
        "start_image": str(start_img)
    }
    headers = {
        "Authorization": "Bearer flow",
        "X-Flow-Agent-Session-Token": "flow",
    }
    
    resp = await client.post("http://127.0.0.1:8001/v1/videos/generations", json=payload, headers=headers, timeout=600.0)
    if resp.status_code != 200:
        raise RuntimeError(f"[{name}] Video generation failed {resp.status_code}: {resp.text}")

    data = resp.json()
    video_url = data.get("url") or data["data"][0]["url"]
    print(f"[{name}] Downloading generated video from {video_url}...")
    vid_resp = await client.get(video_url, timeout=120.0)
    out_file.write_bytes(vid_resp.content)
    print(f"[{name}] Successfully saved {out_file} ({out_file.stat().st_size} bytes)")
    return out_file

async def main():
    out_dir = Path("production_20s")
    out_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=700.0) as client:
        for config in BLOCK_CONFIGS:
            await generate_block(client, config, out_dir)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
