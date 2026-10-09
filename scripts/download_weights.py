"""Download the pretrained weights published by the upstream authors.

Weights are fetched from the authors' own Google Drive links (listed in their
READMEs) into models/, which is git-ignored. Nothing is redistributed here.

    python scripts/download_weights.py
"""
from pathlib import Path

import gdown

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

# file name -> (Google Drive id, upstream repo that publishes it)
WEIGHTS = {
    "yolo5_last.pt": ("1UZwiG1jkWgce9lNhxJ2L0NVjX1vGM05U", "abdullahtarek/tennis_analysis (ball detector)"),
    "keypoints_model.pth": ("1QrTOF1ToQ4plsSZbkBs3zOLkVt3MBlta", "abdullahtarek/tennis_analysis (court keypoints)"),
    "tracknet_ball.pt": ("1XEYZ4myUN7QT-NeBYJI0xteLsvs-ZAOl", "yastrebksv/TrackNet (ball tracking)"),
    "court_detector.pt": ("1f-Co64ehgq4uddcQm1aFBDtbnyZhQvgG", "yastrebksv/TennisCourtDetector (court keypoints)"),
}


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    for name, (drive_id, origin) in WEIGHTS.items():
        target = MODELS / name
        if target.exists():
            print(f"[skip] {name} already present")
            continue
        print(f"[get ] {name}  <-  {origin}")
        gdown.download(id=drive_id, output=str(target), quiet=False)
    print("Done. Player detection weights (yolov8x) are downloaded by ultralytics on first run.")


if __name__ == "__main__":
    main()
