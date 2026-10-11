import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from providers.sfx.elevenlabs import ElevenLabsSfxProvider
from services.audio_bed import generate_audio_bed
import config

async def main():
    out_dir = Path("production_3blocks")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate ambient audio bed (ADR-025)
    print("Generating mood-matched ambient audio bed (tension_pulse, 12.0s)...")
    bed_path = generate_audio_bed("tension_pulse", 12.0, str(out_dir))
    print(f"Audio bed generated at: {bed_path}")

    # 2. Generate ElevenLabs Foley hits
    provider = ElevenLabsSfxProvider()
    cache_dir = out_dir / "sfx_raw"
    cache_dir.mkdir(parents=True, exist_ok=True)

    foley_cues = [
        {
            "asset_id": "foley_water_plunge",
            "prompt": "Deep underwater car plunge splash impact against windshield glass, sudden aquatic surge, ASMR fluid rush",
            "duration": 0.8,
            "tags": ["water", "splash", "impact"]
        },
        {
            "asset_id": "foley_door_handle_jam",
            "prompt": "Car interior door handle heavy mechanical metallic strain and latch resistance click, crisp ASMR tactile metal snap",
            "duration": 0.7,
            "tags": ["door", "metal", "handle", "click"]
        },
        {
            "asset_id": "foley_seatbelt_unbuckle",
            "prompt": "Automotive seatbelt metal tongue release click snap, crisp plastic latch ejection, ASMR tactile click",
            "duration": 0.65,
            "tags": ["seatbelt", "buckle", "click", "release"]
        },
        {
            "asset_id": "foley_window_button",
            "prompt": "Car electric window rocker switch tactile click snap, crisp ASMR toggle button press",
            "duration": 0.6,
            "tags": ["window", "switch", "click"]
        }
    ]

    ffmpeg = config.resolve_ffmpeg()
    print(f"FFmpeg binary: {ffmpeg}")

    processed_sfx = {}

    for cue in foley_cues:
        print(f"Generating SFX cue: {cue['asset_id']}...")
        res = await provider.resolve_asset(cue, cache_dir)
        raw_path = Path(res["local_path"])
        print(f"Raw SFX generated: {raw_path} ({raw_path.stat().st_size} bytes)")

        # Master according to ADR-029:
        # HP 75 Hz, +2.0 dB @ 4.0 kHz, decay envelope 0.55-0.75s, -10.0 dBFS gain staging
        mastered_path = out_dir / f"{cue['asset_id']}_mastered.wav"
        target_dur = cue["duration"]
        fade_start = max(0.1, target_dur - 0.4)
        fade_len = target_dur - fade_start

        # FFmpeg filter: highpass + treble boost + volume staging + afade
        af_chain = (
            f"highpass=f=75,"
            f"equalizer=f=4000:width_type=o:width=1.0:g=2.0,"
            f"afade=t=out:st={fade_start:.2f}:d={fade_len:.2f},"
            f"volume=-10dB"
        )

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(raw_path),
            "-t", str(target_dur),
            "-af", af_chain,
            "-ar", "48000", "-ac", "2",
            str(mastered_path)
        ]
        import subprocess
        subprocess.run(cmd, check=True)
        print(f"Mastered SFX: {mastered_path} ({mastered_path.stat().st_size} bytes)")
        processed_sfx[cue["asset_id"]] = str(mastered_path)

    print("All Foley & audio bed assets generated successfully!")

if __name__ == "__main__":
    asyncio.run(main())
