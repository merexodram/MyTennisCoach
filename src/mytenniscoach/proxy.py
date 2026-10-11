"""Working copy of a recording at analysis size.

The networks look at 640x360 images, so decoding 4K at 60 fps for every
frame is wasted time. The pipeline works on a 720p copy at 25 to 30 fps with
a keyframe every second (cheap to seek in). The original is only needed later
for cutting full-quality technique clips.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import render, video

MAX_HEIGHT = 720
MAX_FPS = 32.0


def needed(info: video.VideoInfo) -> bool:
    return info.height > MAX_HEIGHT or info.fps > MAX_FPS


def make(path: Path, out: Path, log=print) -> Path:
    """Return the file to analyse: the original if it is small enough, else a proxy."""
    info = video.probe(path)
    if not needed(info):
        return path
    if out.exists() and out.stat().st_size > 0:
        log(f"Using existing working copy: {out.name}")
        return out
    ffmpeg = render.find_ffmpeg()
    if ffmpeg is None:
        log("ffmpeg not found: analysing the original file directly (slower).")
        return path
    fps = info.fps / 2.0 if info.fps > MAX_FPS else info.fps      # 60 -> 30, 50 -> 25
    gop = max(1, int(round(fps)))
    vf = f"scale=-2:{min(MAX_HEIGHT, info.height)},fps={fps:g}"
    tmp = out.with_suffix(".part.mp4")
    base = ["-i", str(path), "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0", "-pix_fmt", "yuv420p", str(tmp)]
    log(f"Making a {min(MAX_HEIGHT, info.height)}p / {fps:g} fps working copy of {path.name} ...")
    # Hardware decoding first; fall back to software if the GPU cannot handle the format.
    for pre in (["-hwaccel", "auto"], []):
        if subprocess.call([ffmpeg, "-y", "-v", "error", *pre, *base]) == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(out)
            return out
    log("Could not make a working copy: analysing the original file directly (slower).")
    return path
