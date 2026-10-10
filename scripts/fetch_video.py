"""Download match videos with yt-dlp (https://github.com/yt-dlp/yt-dlp).

    python scripts/fetch_video.py                      # every new link in data/links.txt
    python scripts/fetch_video.py URL [URL ...]        # these links
    python scripts/fetch_video.py URL --start 00:12:30 --end 00:13:05 --name rally1

Videos land in data/raw/ at up to 1080p, highest frame rate available.
Links already downloaded are skipped (data/raw/downloaded.txt keeps track).

data/links.txt holds one link per line; anything after the link is ignored,
and lines starting with # are comments.

Footage stays on this disk (data/ is git-ignored). Broadcast footage is
copyrighted: keep it for private analysis, never commit or re-share it, and
check the terms of the site you download from.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RAW = ROOT / "data" / "raw"
LINKS = ROOT / "data" / "links.txt"


def read_links() -> list[str]:
    if not LINKS.exists():
        return []
    out = []
    for line in LINKS.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split()[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--height", type=int, default=1080, help="maximum resolution (default 1080)")
    ap.add_argument("--name", help="output file name without extension (single link only)")
    ap.add_argument("--start", help="cut: section start, HH:MM:SS")
    ap.add_argument("--end", help="cut: section end, HH:MM:SS")
    ap.add_argument("--again", action="store_true", help="download even if it was downloaded before")
    args = ap.parse_args()

    urls = args.urls or read_links()
    if not urls:
        print(f"No links. Put them in {LINKS} (one per line) or pass them on the command line.")
        raise SystemExit(1)
    if args.name and len(urls) != 1:
        raise SystemExit("--name works with exactly one link")

    RAW.mkdir(parents=True, exist_ok=True)
    template = f"{args.name}.%(ext)s" if args.name else "%(title).80s [%(id)s].%(ext)s"
    h = args.height
    cmd = [
        sys.executable, "-m", "yt_dlp",
        # AV1 is left out because OpenCV often cannot decode it.
        "-f", f"bv*[height<={h}][vcodec!^=av01]+ba/b[height<={h}]/bv*[height<={h}]+ba",
        "-S", f"res:{h},fps",
        "--merge-output-format", "mp4",
        "--windows-filenames", "--no-playlist", "--no-mtime",
        "-P", str(RAW), "-o", template,
    ]
    if not args.again and not (args.start and args.end):
        cmd += ["--download-archive", str(RAW / "downloaded.txt")]
    if args.start and args.end:
        cmd += ["--download-sections", f"*{args.start}-{args.end}", "--force-keyframes-at-cuts"]

    try:
        from mytenniscoach.render import find_ffmpeg
        ffmpeg = find_ffmpeg()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
    else:
        print("Warning: ffmpeg not found; high-resolution video and audio cannot be merged.")
    # YouTube needs a JavaScript runtime; yt-dlp looks for deno by itself.
    if not shutil.which("deno") and shutil.which("node"):
        cmd += ["--js-runtimes", "node"]

    print(f"Downloading {len(urls)} link(s) to {RAW}")
    raise SystemExit(subprocess.call(cmd + urls))


if __name__ == "__main__":
    main()
