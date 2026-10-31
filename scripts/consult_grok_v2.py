import json
import os
from pathlib import Path
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY", "").strip()
if not api_key:
    env_path = Path(".env")
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("XAI_API_KEY="):
                api_key = line.split("=", 1)[1].strip()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

handoff_file = Path("sequences/what-if-the-sun-disappeared_handoff.json")
script_data = json.loads(handoff_file.read_text(encoding="utf-8"))

prompt = f"""You are an elite Hollywood Director, Master Cinematographer (DoP), and AI Video (Google Veo / Flow CDP) Technical Supervisor.

We just re-architected our screenplay engine to generate a full 38-scene, 300-second longform film for 'What If The Sun Disappeared' (Genre: Procedural Catastrophe).
Here is the complete newly generated screenplay:

{json.dumps(script_data, indent=2)}

Please provide a ruthlessly honest, rigorous technical and directorial critique of this new 38-scene screenplay:

1. NARRATIVE PACING & RETENTION ARCHITECTURE:
   - Does the 5-act structure hold up across all 38 scenes?
   - Look at Act 5 (Scenes 35 to 38): Is repeating the exact same subscribe call to action ("You must subscribe to the channel...") across 4 consecutive scenes (totaling 34 seconds!) an enormous flaw? How should the climax and aftermath actually resolve?
   - What about Scene 1 vs Scene 2 causality? (Light from the sun takes 8.3 minutes to reach Earth, yet Scene 1 claims darkness slammed within 3 seconds, then Scene 2 talks about the 8.3 minutes).

2. SCIENTIFIC ACCURACY & METRICS PLAUSIBILITY (Catastrophe Logic):
   - Review the thermal drop rate: dropping to -18°C in minutes, -41°C in 12 minutes, liquid nitrogen snow at -67°C (nitrogen liquefies at -196°C!), liquid oxygen rain at -233°C (oxygen freezes at -218°C!). How scientifically broken is this timescale and thermodynamics, and how should it be grounded without losing tension?
   - What about geothermal energy and subterranean survival?

3. AI VIDEO GENERATION (Google Veo / Flow CDP) VISUAL & MOTION AUDIT:
   - Identify every prompt that will trigger AI video artifacts:
     * Face close-ups / mirror reflections (e.g. Scene 7: "close on your face reflected in a broken subway mirror, eyes wide").
     * Digital gauges and text on phones/meters (Scene 8, 15).
     * Asking the AI video model to render UI graphics and text overlays ("subscribe graphic burning through ice", "text locked on screen" in Scenes 35-38).
   - Evaluate camera choreography: Are the motion prompts physical and feasible for Google Veo?

4. CONTINUITY & PERSPECTIVE JUMPS:
   - Scene 33: "POV from above looking down at your own frozen body" (sudden astral projection / death POV). Does this break 2nd-person immersion?

5. ACTIONABLE DIRECTORIAL FIXES:
   - Give 5 concrete, high-impact fixes we should immediately apply to the engine to make this screenplay and prompt set truly cinematic and production-ready.
"""

response = client.chat.completions.create(
    model="grok-4.20-0309-non-reasoning",
    messages=[
        {"role": "system", "content": "You are a master Hollywood Director, DoP, and AI Video Engine Specialist."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.2,
)

analysis_text = response.choices[0].message.content
Path("out/grok_critique_v2.txt").write_text(analysis_text, encoding="utf-8")
print("GROK CRITIQUE v2 SAVED TO out/grok_critique_v2.txt!")
