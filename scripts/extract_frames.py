#!/usr/bin/env python3
"""Extract a bounded number of video frames using local FFmpeg; no upload."""

import argparse
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("video", type=Path)
p.add_argument("--out", type=Path, required=True)
p.add_argument("--fps", type=float, default=0.5)
p.add_argument("--frames", type=int, default=12)
a = p.parse_args()
if a.out.exists():
    p.error("Output exists; use a new directory.")
if not a.video.is_file() or not 0.01 <= a.fps <= 10 or not 2 <= a.frames <= 16:
    p.error("Use an existing video, 0.01–10 fps and 2–16 frames.")
a.out.mkdir(parents=True)
subprocess.run(
    [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(a.video.resolve()),
        "-vf",
        f"fps={a.fps}",
        "-frames:v",
        str(a.frames),
        str(a.out / "view-%03d.png"),
    ],
    check=True,
)
print(f"Frames saved in {a.out}. Use the optional VGGT bridge in its separate environment.")
