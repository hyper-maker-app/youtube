import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DEEPGRAM_API_KEY", "ce2760bb259ce84c50f1dcf48a8179f120cd0295")

url = "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true"
headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "audio/wav"
}

with open("ref_audio.wav", "rb") as f:
    resp = requests.post(url, headers=headers, data=f.read())

data = resp.json()
transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
print("FULL TRANSCRIPT:")
print(transcript)
print("\n--- FIRST 15 SECONDS WORDS ---")
words = data["results"]["channels"][0]["alternatives"][0]["words"]
for w in words:
    if w["end"] <= 22.0:
        print(f"{w['start']:.2f}-{w['end']:.2f}: {w['word']}")
