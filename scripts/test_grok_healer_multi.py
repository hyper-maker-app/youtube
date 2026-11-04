import os, json, urllib.request
from pathlib import Path

api_key = os.getenv("XAI_API_KEY", "")
if not api_key:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("XAI_API_KEY="):
            api_key = line.split("=", 1)[1].strip()

prompt = """You are the Lead Screenplay Director.
The following scenes have defects identified by dual-judge adversarial review:
- Scene 9: Viewport prompt contains gauge/dial terms that cause text hallucination in Veo.
- Scene 21: Visual prompt requests an analog medical thermometer which causes numbers to generate.
- Scene 38: CTA is non-diegetic.

CRITICAL REQUIREMENT:
You MUST rewrite ALL 3 defective scenes (Scene 9, Scene 21, Scene 38).
Your 'repaired_scenes' list MUST contain exactly 3 items, one for each defective scene.

Respond ONLY with valid JSON:
{
  "repaired_scenes": [
    {
      "scene_id": 9,
      "narration": "Updated narration starting with You...",
      "visual_prompt": "Updated visual prompt...",
      "camera": {"angle": "low-angle", "movement": "static"},
      "micro_math": "100 lux drop...",
      "sfx": "ash falling"
    },
    {
      "scene_id": 21,
      "narration": "Updated narration starting with You...",
      "visual_prompt": "Updated visual prompt...",
      "camera": {"angle": "macro", "movement": "pan"},
      "micro_math": "-15 C drop...",
      "sfx": "frost cracking"
    },
    {
      "scene_id": 38,
      "narration": "Updated narration starting with You...",
      "visual_prompt": "Updated visual prompt...",
      "camera": {"angle": "wide", "movement": "tilt"},
      "micro_math": "final cliffhanger...",
      "sfx": "distant boom"
    }
  ]
}
"""

payload = {
    "model": "grok-4.20-0309-non-reasoning",
    "messages": [
        {"role": "system", "content": "You are a master cinematic screenwriter. Always repair all requested scenes."},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.2
}
req = urllib.request.Request(
    "https://api.x.ai/v1/chat/completions",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    data=json.dumps(payload).encode("utf-8")
)
with urllib.request.urlopen(req, timeout=30) as r:
    res = json.loads(r.read().decode("utf-8"))
    txt = res["choices"][0]["message"]["content"]
    print("Raw response length:", len(txt))
    parsed = json.loads(txt[txt.find("{"):txt.rfind("}")+1])
    scenes = [s.get("scene_id") for s in parsed.get("repaired_scenes", [])]
    print("Repaired scene IDs returned:", scenes)
