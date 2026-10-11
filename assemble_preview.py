import os
from pathlib import Path
import editor
import config

def main():
    out_dir = Path("production_3blocks")
    block_paths = [
        out_dir / "block01.mp4",
        out_dir / "block02.mp4",
        out_dir / "block03.mp4",
    ]
    vo_path = out_dir / "narration.wav"
    music_path = out_dir / "audio_bed_tension_pulse.wav"
    captions_path = out_dir / "captions.ass"
    out_path = out_dir / "preview_3blocks.mp4"

    sfx_cues = [
        {
            "cue_id": "water_plunge",
            "local_path": str((out_dir / "foley_water_plunge_mastered.wav").resolve()),
            "start": 1.0,
            "end": 1.8,
        },
        {
            "cue_id": "door_jam",
            "local_path": str((out_dir / "foley_door_handle_jam_mastered.wav").resolve()),
            "start": 5.2,
            "end": 5.9,
        },
        {
            "cue_id": "seatbelt_unbuckle",
            "local_path": str((out_dir / "foley_seatbelt_unbuckle_mastered.wav").resolve()),
            "start": 8.8,
            "end": 9.45,
        },
        {
            "cue_id": "window_button",
            "local_path": str((out_dir / "foley_window_button_mastered.wav").resolve()),
            "start": 10.5,
            "end": 11.1,
        },
    ]

    print("Running editor.render to produce preview_3blocks.mp4...")
    argv, graph = editor.render(
        block_paths=block_paths,
        vo_path=vo_path,
        out_path=out_path,
        punch_times=[],
        music_path=music_path,
        captions_path=captions_path,
        target_len=12.0,
        sfx_cues=sfx_cues,
        final_polish=True,
    )
    print("Render finished successfully!")
    print(f"Output file: {out_path} ({out_path.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
