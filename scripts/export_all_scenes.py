import json

data = json.load(open("sequences/what-if-the-sun-disappeared_handoff.json", encoding="utf-8"))
scenes = data["scenes"]

output_lines = [
    f"TITLE: {data.get('title')}",
    f"GENRE: {data.get('genre')}",
    f"DURATION: {data.get('duration')}s (Total scenes: {len(scenes)}, sum duration: {sum(s.get('duration', 0) for s in scenes)}s)",
    "=" * 80,
]

for s in scenes:
    output_lines.append(f"SCENE {s.get('scene_number', s.get('id'))} | Duration: {s.get('duration')}s | Camera: {s.get('camera_scale')}")
    output_lines.append(f"  VO: {s.get('narration')}")
    output_lines.append(f"  Visual Prompt: {s.get('visual_prompt')}")
    output_lines.append(f"  Motion Prompt: {s.get('motion_prompt')}")
    if "micro_math" in s:
        output_lines.append(f"  Micro-Math: {s.get('micro_math')}")
    output_lines.append("-" * 40)

full_text = "\n".join(output_lines)
open("out/all_38_scenes.txt", "w", encoding="utf-8").write(full_text)
print("Saved 38 scenes to out/all_38_scenes.txt")
