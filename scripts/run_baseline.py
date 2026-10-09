"""Run the unmodified upstream baseline (abdullahtarek/tennis_analysis) on one clip.

The upstream main.py hard-codes its input path, reads cached detections
("stubs") made for its own sample video, and loads every frame into RAM.
This wrapper runs that same code against your clip without editing the
submodule: it patches those three things in memory and executes it.

    python scripts/run_baseline.py data/raw/federer_test1.mp4

Output: outputs/<clip name>_baseline.avi
Detections are cached in outputs/cache/, so a second run of the same clip is fast.

Limits inherited from upstream (this is why it is only the Phase 0 check):
  * keep clips short (about 30-60 s at 720p), all frames are held in memory
  * speed figures assume 24 fps
  * the court is detected on the first frame only, so the clip must be one
    continuous main-camera shot with no cuts or replays
"""
import argparse
import os
import runpy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "tennis_analysis"
MODELS = ROOT / "models"
OUT = ROOT / "outputs"
CACHE = OUT / "cache"


PREAMBLE = (
    "# The court model's ImageNet weights are overwritten by keypoints_model.pth,\n"
    "# so skip that 100 MB download.\n"
    "import torchvision.models as _tvm\n"
    "_resnet50 = _tvm.resnet50\n"
    "_tvm.resnet50 = lambda *a, **k: _resnet50(weights=None)\n"
    "\n"
    "# Upstream assumes the two players carry track ids 1 and 2, which only holds\n"
    "# when nobody else is in frame. Renumber the chosen pair: 1 = near player.\n"
    "def _renumber(detections):\n"
    "    ids = sorted(detections[0], key=lambda i: -detections[0][i][3])\n"
    "    m = {old: new for new, old in enumerate(ids, start=1)}\n"
    "    return [{m[i]: b for i, b in d.items() if i in m} for d in detections]\n"
)


def patched_source(video: Path, out_file: Path) -> str:
    """Return upstream main.py with paths redirected and detections cached per clip."""
    src = (UPSTREAM / "main.py").read_text(encoding="utf-8")
    players_pkl = CACHE / f"{video.stem}_players.pkl"
    ball_pkl = CACHE / f"{video.stem}_ball.pkl"
    replacements = {
        '"input_videos/input_video.mp4"': repr(str(video)),
        "'models/yolo5_last.pt'": repr(str(MODELS / "yolo5_last.pt")),
        '"models/keypoints_model.pth"': repr(str(MODELS / "keypoints_model.pth")),
        '"output_videos/output_video.avi"': repr(str(out_file)),
        # Detection is the slow part: cache it per clip, outside the submodule.
        'read_from_stub=True,\n                                                     stub_path="tracker_stubs/player_detections.pkl"':
            f"read_from_stub={players_pkl.exists()}, stub_path={str(players_pkl)!r}",
        'read_from_stub=True,\n                                                     stub_path="tracker_stubs/ball_detections.pkl"':
            f"read_from_stub={ball_pkl.exists()}, stub_path={str(ball_pkl)!r}",
    }
    for old, new in replacements.items():
        if old not in src:
            raise SystemExit(f"Upstream main.py changed, cannot find: {old[:60]}")
        src = src.replace(old, new)
    anchor = "choose_and_filter_players(court_keypoints, player_detections)\n"
    if anchor not in src:
        raise SystemExit("Upstream main.py changed, cannot find the player filter call")
    src = src.replace(anchor, anchor + "    player_detections = _renumber(player_detections)\n")
    return PREAMBLE + src


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    if not (UPSTREAM / "main.py").exists():
        raise SystemExit("Submodules missing. Run: git submodule update --init --depth 1")
    for w in ("yolo5_last.pt", "keypoints_model.pth"):
        if not (MODELS / w).exists():
            raise SystemExit(f"Missing models/{w}. Run: python scripts/download_weights.py")

    CACHE.mkdir(parents=True, exist_ok=True)
    out_file = OUT / f"{video.stem}_baseline.avi"

    with tempfile.NamedTemporaryFile("w", suffix="_main.py", delete=False, encoding="utf-8") as fh:
        fh.write(patched_source(video, out_file))
        tmp = fh.name
    try:
        os.chdir(UPSTREAM)
        sys.path.insert(0, str(UPSTREAM))
        runpy.run_path(tmp, run_name="__main__")
    finally:
        os.unlink(tmp)
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
