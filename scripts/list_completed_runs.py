from pathlib import Path
import json

out_dir = Path("out")
results = []
for p in out_dir.iterdir():
    if p.is_dir():
        script_file = p / "script.json"
        final_file = p / "final.mp4"
        if script_file.exists():
            try:
                with open(script_file, encoding="utf-8") as f:
                    s = json.load(f)
                results.append({
                    "dir": p.name,
                    "topic": s.get("topic"),
                    "mode": s.get("mode"),
                    "has_final": final_file.exists(),
                    "final_size": final_file.stat().st_size if final_file.exists() else 0,
                    "mtime": p.stat().st_mtime
                })
            except Exception as e:
                pass

results.sort(key=lambda x: x["mtime"], reverse=True)
for r in results:
        m = str(r['mode'] or 'unknown')
        t = str(r['topic'] or '')[:60]
        print(f"[{m:<10}] {t:<60} | {r['dir']}")
