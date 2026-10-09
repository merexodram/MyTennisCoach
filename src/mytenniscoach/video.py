"""Streaming video access: frames are never all held in memory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


@dataclass
class VideoInfo:
    path: Path
    fps: float
    width: int
    height: int
    frames: int

    @property
    def duration_s(self) -> float:
        return self.frames / self.fps if self.fps else 0.0


def probe(path: str | Path) -> VideoInfo:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    info = VideoInfo(
        Path(path),
        cap.get(cv2.CAP_PROP_FPS) or 25.0,
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    )
    cap.release()
    return info


def frames(path: str | Path) -> Iterator[tuple[int, np.ndarray]]:
    cap = cv2.VideoCapture(str(path))
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield i, frame
            i += 1
    finally:
        cap.release()
