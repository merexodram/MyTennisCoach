"""Fetch a test clip for local pipeline validation.

Downloads one video with yt-dlp at 720p (the resolution the upstream models
were trained on) and optionally cuts a short section, so the baseline pipeline
can hold it in memory.

    python scripts/fetch_video.py URL --name federer_test1 --start 00:02:10 --end 00:02:40

Footage stays in data/raw/, which is git-ignored. Broadcast footage is
copyrighted: keep it on your own disk for private testing, never commit or
re-share it, and check the terms of the site you download from.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--name", required=True, help="output file name without extension")
    ap.add_argument("--start", help="section start, HH:MM:SS")
    ap.add_argument("--end", help="section end, HH:MM:SS")
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", f"bv*[height<={args.height}][ext=mp4]+ba[ext=m4a]/b[height<={args.height}]",
        "--merge-output-format", "mp4",
        "-o", str(RAW / f"{args.name}.%(ext)s"),
    ]
    if args.start and args.end:
        cmd += ["--download-sections", f"*{args.start}-{args.end}", "--force-keyframes-at-cuts"]
    cmd.append(args.url)
    print(" ".join(cmd))
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
