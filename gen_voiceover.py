import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DEEPGRAM_API_KEY", "ce2760bb259ce84c50f1dcf48a8179f120cd0295")

text = "Imagine you drive into a lake and you try to push the door open, but the water pressure outside pins it shut. So you unbuckle and try rolling the window down."

# Deepgram Aura TTS API
url = "https://api.deepgram.com/v1/speak?model=aura-2-hermes-en&encoding=linear16&sample_rate=48000"
headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "application/json"
}
payload = {"text": text}

print("Requesting Deepgram TTS...")
resp = requests.post(url, headers=headers, json=payload)
if resp.status_code != 200:
    print(f"Error {resp.status_code}: {resp.text}")
    exit(1)

out_dir = "production_3blocks"
os.makedirs(out_dir, exist_ok=True)
audio_path = os.path.join(out_dir, "narration.wav")
with open(audio_path, "wb") as f:
    f.write(resp.content)
print(f"Saved narration to {audio_path}")

# Now get word timestamps with Deepgram nova-3
listen_url = "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true"
listen_headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "audio/wav"
}
with open(audio_path, "rb") as f:
    listen_resp = requests.post(listen_url, headers=listen_headers, data=f.read())

listen_data = listen_resp.json()
words = listen_data["results"]["channels"][0]["alternatives"][0]["words"]
print(f"Transcription got {len(words)} words:")
for w in words:
    print(f"{w['start']:.2f} - {w['end']:.2f}: {w['word']}")

with open(os.path.join(out_dir, "words.json"), "w", encoding="utf-8") as f:
    json.dump(words, f, indent=2)
print("Saved words.json")
