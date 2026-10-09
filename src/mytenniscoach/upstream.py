"""Load network definitions from the upstream submodules.

Only the model architectures come from upstream (TrackNet and
TennisCourtDetector, both by yastrebksv). They are imported from
third_party/ at run time; nothing is copied into this package.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THIRD_PARTY = ROOT / "third_party"
MODELS = ROOT / "models"


def _load(name: str, path: Path):
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. Run: git submodule update --init --depth 1"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ball_net():
    """TrackNet: 3 stacked frames in, 256-class heatmap out (640x360)."""
    return _load("_up_tracknet_ball", THIRD_PARTY / "TrackNet" / "model.py").BallTrackerNet()


def court_net():
    """Court detector: 1 frame in, 15 keypoint heatmaps out (640x360)."""
    mod = _load("_up_tracknet_court", THIRD_PARTY / "TennisCourtDetector" / "tracknet.py")
    return mod.BallTrackerNet(out_channels=15)


def weights(name: str) -> Path:
    path = MODELS / name
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run: python scripts/download_weights.py")
    return path
