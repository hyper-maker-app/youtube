import json

def parse_file(filename):
    with open(filename, encoding='utf-16') as f:
        d = json.load(f)
    print(f"\n--- {filename} ---")
    for e in d.get('entries', [])[:10]:
        print(f"- {e.get('title')} | Views: {e.get('view_count')} | Duration: {e.get('duration')}s | URL: {e.get('url')} | id: {e.get('id')}")

import sys
import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

with open('videos_parsed.txt', 'w', encoding='utf-8') as out:
    for filename in ['videos.json', 'shorts.json']:
        try:
            with open(filename, encoding='utf-16') as f:
                d = json.load(f)
            out.write(f"\n--- {filename} ---\n")
            for e in d.get('entries', [])[:10]:
                out.write(f"- {e.get('title')} | Views: {e.get('view_count')} | Duration: {e.get('duration')}s | URL: {e.get('url')} | id: {e.get('id')}\n")
        except Exception as e:
            out.write(f"Error parsing {filename}: {e}\n")
