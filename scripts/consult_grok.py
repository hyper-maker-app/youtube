import json
import os
from pathlib import Path
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY", "").strip()
if not api_key:
    # Read from .env
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

prompt = f"""You are an elite Hollywood Executive Director, Master Cinematographer (DoP), and AI Video Generation (Google Veo / Flow CDP) Technical Supervisor.

Review this AI-generated 8-scene screenplay and visual prompt plan for the YouTube film 'What If The Sun Disappeared' (Genre: Procedural Catastrophe):

{json.dumps(script_data, indent=2)}

Please provide a ruthlessly honest, deep technical critique covering:
1. Duration & Scene Count Mismatch: The user asked for a 300-second (5 min) video, but these 8 scenes only total 70 seconds! How should this be structured to legitimately fill 300 seconds without artificial slow-motion or repetition?
2. AI Video Generation (Veo / Flow) Feasibility & Artifacts:
   - Are visual prompts like 'needle vibrating violently then snapping as pressure drops' or 'thermometer plummeting from 22°C' realistic for AI video, or will they cause severe AI text/gauge morphing hallucinations?
   - How does Scene 6 ('Extreme close-up of your own eyes through frost-covered goggles: capillaries bursting, skin turning blue-black') violate the 'Zero Facial Hallucination' rule?
3. Scientific & Narrative Plausibility vs Absurdity:
   - What happens to solar pressure and atmosphere? Does the atmosphere 'collapse inward at 1,200 km/h' or freeze?
   - Micro-mathematics audit (e.g. 'blood boiling at 63°C below zero' Armstrong limit vs pressure drop).
4. Audio & Foley Synchronization:
   - How well do the cues (172 dB shockwave, cracking glass, nitrogen waterfalls) map to physical foley and sound design?
5. Concrete Actionable Recommendations:
   - How to expand this to 38 scenes across 5 narrative acts for a true 300-second longform YouTube film.
"""

response = client.chat.completions.create(
    model="grok-4.20-0309-non-reasoning",
    messages=[
        {"role": "system", "content": "You are a world-class Film Director, DoP, and AI Video Generation specialist."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.3,
)

analysis_text = response.choices[0].message.content
Path("out/grok_critique.txt").write_text(analysis_text, encoding="utf-8")
print("GROK CRITIQUE COMPLETED!")
print(analysis_text[:1500])
