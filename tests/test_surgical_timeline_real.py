"""Exercise real FFmpeg assembly and ffprobe media validation."""
from pathlib import Path
import subprocess
import shutil

import pytest

from engine.services.surgical_patcher import surgically_splice_timeline


@pytest.mark.parametrize("use_ffprobe", [False, True])
def test_splice_uses_custom_timeline_assembler(tmp_path: Path, use_ffprobe: bool):
    if use_ffprobe and not shutil.which("ffprobe"):
        pytest.skip("ffprobe is not available")
    import imageio_ffmpeg
    import engine.flow_bridge  # initializes editor/config imports
    import editor

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    paths = [tmp_path / name for name in ("one.mp4", "two.mp4", "replacement.mp4")]
    for path, color in zip(paths, ("red", "blue", "green")):
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color={color}:s=64x64:r=30:d=2", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(path)], check=True)

    def assemble(blocks, output):
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(blocks[0]),
                        "-i", str(blocks[1]), "-filter_complex",
                        "[0:v]trim=duration=1,setpts=PTS-STARTPTS[a];"
                        "[1:v]trim=duration=1,setpts=PTS-STARTPTS[b];"
                        "[a][b]concat=n=2:v=1:a=0,fps=fps=30:eof_action=pass,tpad=stop_mode=clone:stop=15[v]",
                        "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)], check=True)

    master, output = tmp_path / "master.mp4", tmp_path / "patched.mp4"
    assemble(paths[:2], master)

    def metadata(path):
        # ffprobe is absent in the test environment. Duration is read from FFmpeg;
        # these fixed stream fields reflect the explicitly encoded test inputs.
        info = editor.probe(path, ffmpeg)
        return {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 64,
                             "height": 64, "pix_fmt": "yuv420p", "avg_frame_rate": "30/1",
                             "time_base": "1/15360", "duration": info.duration}]}

    surgically_splice_timeline(master, {1: paths[2]}, paths[:2], output,
                               assemble=assemble, probe=None if use_ffprobe else metadata)
    assert abs(editor.probe(output, ffmpeg).duration - 2.5) < 0.05

